package com.dai2010.m3u8down.download

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

private class BilibiliRequestStopException(message: String) : IOException(message)

class DirectDownloader(
    private val client: OkHttpClient,
    private val headers: Map<String, String> = emptyMap(),
    private val bilibiliCompatEnabled: Boolean = false,
) {
    suspend fun download(url: String, outputFile: File, backupUrls: List<String> = emptyList(), retries: Int = 3): File = withContext(Dispatchers.IO) {
        outputFile.parentFile?.mkdirs()
        val part = File("${outputFile.absolutePath}.part")
        val sources = (listOf(url) + backupUrls).distinct()
        var lastError: Throwable? = null
        repeat(retries.coerceAtLeast(1)) {
            for (source in sources) {
                try {
                    val enabled = bilibiliCompatEnabled || isBilibiliUrl(source)
                    val requestUrl = prepareBilibiliUrl(source, enabled)
                    val requestHeaders = prepareBilibiliHeaders(requestUrl, headers, enabled).toMutableMap()
                    val partSize = if (part.exists()) part.length() else 0L
                    if (partSize > 0L) requestHeaders["Range"] = "bytes=$partSize-"
                    val requestBuilder = Request.Builder().url(requestUrl)
                    requestHeaders.forEach { (name, value) -> if (value.isNotBlank()) requestBuilder.header(name, value) }
                    throttleBilibiliRequest(requestUrl)
                    client.newCall(requestBuilder.build()).execute().use { response ->
                        if (!response.isSuccessful) {
                            if (isBilibiliUrl(requestUrl) && response.code in setOf(401, 403, 404, 410, 429)) {
                                throw BilibiliRequestStopException("B 站请求失败 HTTP ${response.code}: $source")
                            }
                            error("HTTP ${response.code}: $source")
                        }
                        val append = partSize > 0L && response.code == 206
                        response.body?.byteStream()?.use { input ->
                            FileOutputStream(part, append).use { output -> input.copyTo(output) }
                        } ?: error("empty response body: $source")
                    }
                    if (outputFile.exists()) outputFile.delete()
                    check(part.renameTo(outputFile)) { "cannot move downloaded file" }
                    return@withContext outputFile
                } catch (exc: Exception) {
                    if (exc is BilibiliRequestStopException) throw exc
                    lastError = exc
                }
            }
        }
        throw lastError ?: IOException("download failed: $url")
    }
}
