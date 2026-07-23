package com.dai2010.m3u8down.download

import android.net.Uri
import com.dai2010.m3u8down.network.bilibiliMediaUrlVariants
import com.dai2010.m3u8down.network.isBilibiliUrl
import com.dai2010.m3u8down.network.prepareBilibiliHeaders
import com.dai2010.m3u8down.network.prepareBilibiliUrl
import com.dai2010.m3u8down.network.throttleBilibiliRequest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.security.MessageDigest
import java.util.Locale

enum class DirectDownloadFailureCategory {
    HTTP,
    BODY,
    IO,
}

data class DirectDownloadAttempt(
    val index: Int,
    val scheme: String,
    val host: String,
    val port: Int?,
    val statusCode: Int?,
    val contentType: String?,
    val expectedBytes: Long?,
    val actualBytes: Long?,
    val contentRange: String?,
    val resumed: Boolean,
    val hasCookie: Boolean,
    val hasRange: Boolean,
    val responseSha256: String?,
) {
    fun redactedDescription(): String = buildString {
        append('#').append(index).append(' ')
        append(scheme.ifBlank { "?" }).append("://")
        append(host.ifBlank { "?" })
        port?.let { append(':').append(it) }
        append(" status=").append(statusCode ?: "unknown")
        append(" type=").append(contentType ?: "unknown")
        append(" length=").append(expectedBytes ?: "unknown")
        append(" actual=").append(actualBytes ?: "unknown")
        append(" range=").append(contentRange ?: "none")
        append(" resumed=").append(if (resumed) "yes" else "no")
        append(" cookie=").append(if (hasCookie) "yes" else "no")
        append(" request_range=").append(if (hasRange) "yes" else "no")
        append(" sha256=").append(responseSha256 ?: "unknown")
    }
}

class DirectDownloadException(
    val category: DirectDownloadFailureCategory,
    message: String,
    val statusCode: Int? = null,
    val contentType: String? = null,
    val expectedBytes: Long? = null,
    val actualBytes: Long? = null,
    val resumed: Boolean = false,
    val attempts: List<DirectDownloadAttempt> = emptyList(),
    cause: Throwable? = null,
) : IOException(message, cause)

private data class ResponseBodySummary(
    val actualBytes: Long,
    val sha256: String,
)

class DirectDownloader(
    private val client: OkHttpClient,
    private val headers: Map<String, String> = emptyMap(),
    private val bilibiliCompatEnabled: Boolean = false,
    private val preserveBilibiliMediaUrl: Boolean = false,
) {
    suspend fun download(url: String, outputFile: File, backupUrls: List<String> = emptyList(), retries: Int = 3): File = withContext(Dispatchers.IO) {
        outputFile.parentFile?.mkdirs()
        val part = File("${outputFile.absolutePath}.part")
        val sourceUrls = (listOf(url) + backupUrls).distinct()
        val sources = if (preserveBilibiliMediaUrl) {
            sourceUrls.flatMap(::bilibiliMediaUrlVariants).distinct()
        } else {
            sourceUrls
        }
        val attempts = mutableListOf<DirectDownloadAttempt>()
        var lastError: Throwable? = null
        var stopRetries = false
        repeat(retries.coerceAtLeast(1)) {
            if (stopRetries) return@repeat
            sources.forEachIndexed { sourceIndex, source ->
                try {
                    val enabled = bilibiliCompatEnabled || isBilibiliUrl(source)
                    val requestUrl = if (preserveBilibiliMediaUrl && isBilibiliUrl(source)) {
                        source
                    } else {
                        prepareBilibiliUrl(source, enabled)
                    }
                    downloadSource(
                        requestUrl,
                        part,
                        prepareBilibiliHeaders(requestUrl, headers, enabled),
                        sourceIndex + 1,
                        attempts,
                    )
                    movePartFile(part, outputFile)
                    return@withContext outputFile
                } catch (exc: DirectDownloadException) {
                    lastError = exc.withAttempts(attempts)
                } catch (exc: Exception) {
                    lastError = DirectDownloadException(
                        DirectDownloadFailureCategory.IO,
                        "下载 I/O 失败（${describeUrl(source)}）",
                        attempts = attempts.toList(),
                        cause = exc,
                    )
                }
            }
            if (lastError is DirectDownloadException && (lastError as DirectDownloadException).category == DirectDownloadFailureCategory.HTTP) {
                val statusCode = (lastError as DirectDownloadException).statusCode
                if (statusCode in setOf(401, 403, 404, 410, 429)) {
                    stopRetries = true
                }
            }
        }
        throw lastError ?: IOException("下载失败（${describeUrl(url)}）")
    }

    private fun downloadSource(
        requestUrl: String,
        part: File,
        headers: Map<String, String>,
        sourceIndex: Int,
        attempts: MutableList<DirectDownloadAttempt>,
    ) {
        var cleanRetryUsed = false
        while (true) {
            val partSize = if (part.isFile) part.length() else 0L
            val requestHeaders = headers.toMutableMap()
            if (partSize > 0L) requestHeaders["Range"] = "bytes=$partSize-"
            val requestBuilder = Request.Builder().url(requestUrl)
            requestHeaders.forEach { (name, value) -> if (value.isNotBlank()) requestBuilder.header(name, value) }
            throttleBilibiliRequest(requestUrl)
            client.newCall(requestBuilder.build()).execute().use { response ->
                val contentType = response.body?.contentType()?.toString()
                val expectedBytes = response.body?.contentLength()?.takeIf { it >= 0L }
                val contentRange = response.header("Content-Range")
                if (response.code == 416 && partSize > 0L && !cleanRetryUsed) {
                    val bodySummary = response.body?.let(::readBodySummary)
                    attempts += buildAttempt(
                        sourceIndex,
                        requestUrl,
                        response.code,
                        contentType,
                        expectedBytes,
                        bodySummary?.actualBytes,
                        contentRange,
                        partSize,
                        requestHeaders,
                        bodySummary?.sha256,
                    )
                    part.delete()
                    cleanRetryUsed = true
                    return@use
                }
                if (!response.isSuccessful) {
                    val bodySummary = response.body?.let(::readBodySummary)
                    attempts += buildAttempt(
                        sourceIndex,
                        requestUrl,
                        response.code,
                        contentType,
                        expectedBytes,
                        bodySummary?.actualBytes,
                        contentRange,
                        partSize,
                        requestHeaders,
                        bodySummary?.sha256,
                    )
                    throw DirectDownloadException(
                        DirectDownloadFailureCategory.HTTP,
                        "HTTP ${response.code}（${describeUrl(requestUrl)}）",
                        statusCode = response.code,
                        contentType = contentType,
                        expectedBytes = expectedBytes,
                        actualBytes = bodySummary?.actualBytes,
                        resumed = partSize > 0L,
                    )
                }
                val body = response.body ?: throw DirectDownloadException(
                    DirectDownloadFailureCategory.BODY,
                    "响应没有媒体内容（${describeUrl(requestUrl)}）",
                    statusCode = response.code,
                    resumed = partSize > 0L,
                )
                validateContentType(body.contentType()?.toString(), requestUrl, response.code, partSize > 0L)
                val chunk = File("${part.absolutePath}.chunk")
                try {
                    if (chunk.exists()) chunk.delete()
                    val bodySummary = body.byteStream().use { input ->
                        FileOutputStream(chunk).use { output -> copyWithDigest(input, output) }
                    }
                    attempts += buildAttempt(
                        sourceIndex,
                        requestUrl,
                        response.code,
                        contentType,
                        expectedBytes,
                        bodySummary.actualBytes,
                        contentRange,
                        partSize,
                        requestHeaders,
                        bodySummary.sha256,
                    )
                    validateResponseLength(response, bodySummary.actualBytes, partSize, requestUrl)
                    validateBodyPrefix(chunk, requestUrl, response.code, partSize > 0L)
                    if (partSize > 0L && response.code == 206) {
                        FileOutputStream(part, true).use { output -> chunk.inputStream().use { input -> input.copyTo(output) } }
                    } else {
                        chunk.copyTo(part, overwrite = true)
                    }
                    if (!part.isFile || part.length() <= 0L) {
                        throw DirectDownloadException(
                            DirectDownloadFailureCategory.BODY,
                            "下载文件为空（${describeUrl(requestUrl)}）",
                            statusCode = response.code,
                            actualBytes = part.length(),
                            resumed = partSize > 0L,
                        )
                    }
                } finally {
                    chunk.delete()
                }
            }
            if (cleanRetryUsed && part.length() > 0L) return
            if (part.length() > 0L) return
        }
    }

    private fun validateContentType(contentType: String?, requestUrl: String, statusCode: Int, resumed: Boolean) {
        val normalized = contentType?.substringBefore(';')?.trim()?.lowercase(Locale.US).orEmpty()
        if (normalized in setOf("text/html", "text/plain", "application/json", "application/xml", "text/xml")) {
            throw DirectDownloadException(
                DirectDownloadFailureCategory.BODY,
                "响应不是媒体（Content-Type $normalized，${describeUrl(requestUrl)}）",
                statusCode = statusCode,
                contentType = normalized,
                resumed = resumed,
            )
        }
    }

    private fun validateResponseLength(response: okhttp3.Response, actualBytes: Long, partSize: Long, requestUrl: String) {
        val expectedBytes = response.body?.contentLength()?.takeIf { it >= 0L }
        if (expectedBytes != null && expectedBytes != actualBytes) {
            throw DirectDownloadException(
                DirectDownloadFailureCategory.BODY,
                "响应长度不完整（期望 $expectedBytes，实际 $actualBytes，${describeUrl(requestUrl)}）",
                statusCode = response.code,
                expectedBytes = expectedBytes,
                actualBytes = actualBytes,
                resumed = partSize > 0L,
            )
        }
        if (response.code == 206) {
            val contentRange = response.header("Content-Range")
                ?: throw DirectDownloadException(
                    DirectDownloadFailureCategory.BODY,
                    "206 响应缺少 Content-Range（${describeUrl(requestUrl)}）",
                    statusCode = response.code,
                    actualBytes = actualBytes,
                    resumed = partSize > 0L,
                )
            val match = CONTENT_RANGE.matchEntire(contentRange.trim())
                ?: throw DirectDownloadException(
                    DirectDownloadFailureCategory.BODY,
                    "206 响应的 Content-Range 无效（${describeUrl(requestUrl)}）",
                    statusCode = response.code,
                    actualBytes = actualBytes,
                    resumed = partSize > 0L,
                )
            val start = match.groupValues[1].toLong()
            val end = match.groupValues[2].toLong()
            val total = match.groupValues[3].toLongOrNull()
            if (start != partSize || end < start || end - start + 1L != actualBytes || (total != null && end >= total)) {
                throw DirectDownloadException(
                    DirectDownloadFailureCategory.BODY,
                    "206 响应与残片位置不一致（${describeUrl(requestUrl)}）",
                    statusCode = response.code,
                    expectedBytes = end - start + 1L,
                    actualBytes = actualBytes,
                    resumed = partSize > 0L,
                )
            }
            if (total != null && partSize + actualBytes != total) {
                throw DirectDownloadException(
                    DirectDownloadFailureCategory.BODY,
                    "206 响应未覆盖完整媒体（${describeUrl(requestUrl)}）",
                    statusCode = response.code,
                    expectedBytes = total - partSize,
                    actualBytes = actualBytes,
                    resumed = partSize > 0L,
                )
            }
        }
    }

    private fun validateBodyPrefix(chunk: File, requestUrl: String, statusCode: Int, resumed: Boolean) {
        val prefix = chunk.inputStream().use { input -> ByteArray(256).also { input.read(it) } }
            .toString(Charsets.UTF_8)
            .trimStart()
            .lowercase(Locale.US)
        if (prefix.startsWith("<html") || prefix.startsWith("<!doctype") || prefix.startsWith("{") || prefix.startsWith("[")) {
            throw DirectDownloadException(
                DirectDownloadFailureCategory.BODY,
                "响应正文疑似错误页（${describeUrl(requestUrl)}）",
                statusCode = statusCode,
                resumed = resumed,
            )
        }
    }

    private fun movePartFile(part: File, outputFile: File) {
        try {
            Files.move(
                part.toPath(),
                outputFile.toPath(),
                StandardCopyOption.REPLACE_EXISTING,
                StandardCopyOption.ATOMIC_MOVE,
            )
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(part.toPath(), outputFile.toPath(), StandardCopyOption.REPLACE_EXISTING)
        } catch (exc: IOException) {
            throw DirectDownloadException(DirectDownloadFailureCategory.IO, "无法保存下载文件", cause = exc)
        }
    }

    private fun describeUrl(url: String): String = runCatching {
        val parsed = Uri.parse(url)
        buildString {
            append(parsed.scheme.orEmpty())
            append("://")
            append(parsed.host.orEmpty())
            parsed.port.takeIf { it != -1 }?.let { append(":").append(it) }
            append(parsed.path.orEmpty())
        }
    }.getOrDefault("media-url")

    private fun buildAttempt(
        index: Int,
        requestUrl: String,
        statusCode: Int?,
        contentType: String?,
        expectedBytes: Long?,
        actualBytes: Long?,
        contentRange: String?,
        partSize: Long,
        requestHeaders: Map<String, String>,
        responseSha256: String?,
    ): DirectDownloadAttempt {
        val parsed = Uri.parse(requestUrl)
        return DirectDownloadAttempt(
            index = index,
            scheme = parsed.scheme.orEmpty(),
            host = parsed.host.orEmpty(),
            port = parsed.port.takeIf { it != -1 },
            statusCode = statusCode,
            contentType = contentType?.substringBefore(';')?.trim()?.lowercase(Locale.US),
            expectedBytes = expectedBytes,
            actualBytes = actualBytes,
            contentRange = contentRange,
            resumed = partSize > 0L,
            hasCookie = requestHeaders.keys.any { it.equals("Cookie", ignoreCase = true) },
            hasRange = requestHeaders.keys.any { it.equals("Range", ignoreCase = true) },
            responseSha256 = responseSha256,
        )
    }

    private fun copyWithDigest(input: java.io.InputStream, output: FileOutputStream): ResponseBodySummary {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(8192)
        var actualBytes = 0L
        while (true) {
            val read = input.read(buffer)
            if (read < 0) break
            if (read == 0) continue
            digest.update(buffer, 0, read)
            output.write(buffer, 0, read)
            actualBytes += read
        }
        return ResponseBodySummary(actualBytes, digest.toHex())
    }

    private fun readBodySummary(body: okhttp3.ResponseBody): ResponseBodySummary {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(8192)
        var actualBytes = 0L
        body.byteStream().use { input ->
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                if (read == 0) continue
                digest.update(buffer, 0, read)
                actualBytes += read
            }
        }
        return ResponseBodySummary(actualBytes, digest.toHex())
    }

    private fun MessageDigest.toHex(): String = digest().joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }

    private fun DirectDownloadException.withAttempts(value: List<DirectDownloadAttempt>): DirectDownloadException = DirectDownloadException(
        category = category,
        message = message.orEmpty(),
        statusCode = statusCode,
        contentType = contentType,
        expectedBytes = expectedBytes,
        actualBytes = actualBytes,
        resumed = resumed,
        attempts = value,
        cause = cause,
    )

    private companion object {
        val CONTENT_RANGE = Regex("bytes (\\d+)-(\\d+)/(\\d+|\\*)", RegexOption.IGNORE_CASE)
    }
}
