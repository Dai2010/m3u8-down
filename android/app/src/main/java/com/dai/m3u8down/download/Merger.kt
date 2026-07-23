package com.dai2010.m3u8down.download

import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.ReturnCode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File
import java.io.FileInputStream
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.Locale

enum class MergeFailureCategory {
    NONE,
    MERGE_INPUT,
    MERGE_FFMPEG,
    MERGE_OUTPUT,
}

data class MergeResult(
    val success: Boolean,
    val category: MergeFailureCategory,
    val returnCode: ReturnCode? = null,
    val videoBytes: Long = 0L,
    val audioBytes: Long = 0L,
    val outputBytes: Long = 0L,
    val diagnostics: String = "",
)

object Merger {
    suspend fun mergeBilibiliTracks(videoFile: File, audioFile: File?, outputFile: File): MergeResult = withContext(Dispatchers.IO) {
        val videoError = validateInput(videoFile, "视频")
        if (videoError != null) return@withContext videoError
        val audioError = audioFile?.let { validateInput(it, "音频") }
        if (audioError != null) return@withContext audioError
        outputFile.parentFile?.mkdirs()
        val temporaryOutput = File("${outputFile.absolutePath}.part")
        temporaryOutput.delete()
        try {
            val command = buildBilibiliMergeArguments(videoFile, audioFile, temporaryOutput)
            val session = FFmpegKit.executeWithArguments(command.toTypedArray())
            val returnCode = session.returnCode
            val diagnostics = sanitizeDiagnostics(
                session.failStackTrace.orEmpty().ifBlank { session.output.orEmpty() }.takeLast(MAX_DIAGNOSTICS_LENGTH),
            )
            if (!ReturnCode.isSuccess(returnCode)) {
                return@withContext MergeResult(
                    success = false,
                    category = MergeFailureCategory.MERGE_FFMPEG,
                    returnCode = returnCode,
                    videoBytes = videoFile.length(),
                    audioBytes = audioFile?.length() ?: 0L,
                    diagnostics = diagnostics,
                )
            }
            if (!isValidMp4File(temporaryOutput)) {
                return@withContext MergeResult(
                    success = false,
                    category = MergeFailureCategory.MERGE_OUTPUT,
                    returnCode = returnCode,
                    videoBytes = videoFile.length(),
                    audioBytes = audioFile?.length() ?: 0L,
                    outputBytes = temporaryOutput.length(),
                    diagnostics = "FFmpeg 返回成功，但输出 MP4 不可探测",
                )
            }
            moveAtomically(temporaryOutput, outputFile)
            MergeResult(
                success = true,
                category = MergeFailureCategory.NONE,
                returnCode = returnCode,
                videoBytes = videoFile.length(),
                audioBytes = audioFile?.length() ?: 0L,
                outputBytes = outputFile.length(),
                diagnostics = diagnostics,
            )
        } catch (exc: Exception) {
            MergeResult(
                success = false,
                category = MergeFailureCategory.MERGE_FFMPEG,
                videoBytes = videoFile.length(),
                audioBytes = audioFile?.length() ?: 0L,
                outputBytes = temporaryOutput.length(),
                diagnostics = exc.message.orEmpty().takeLast(MAX_DIAGNOSTICS_LENGTH),
            )
        } finally {
            temporaryOutput.delete()
        }
    }

    fun buildBilibiliMergeArguments(videoFile: File, audioFile: File?, outputFile: File): List<String> = buildList {
        addAll(listOf("-y", "-i", videoFile.absolutePath))
        if (audioFile != null) addAll(listOf("-i", audioFile.absolutePath))
        addAll(listOf("-map", "0:v:0"))
        if (audioFile != null) addAll(listOf("-map", "1:a:0"))
        addAll(listOf("-c:v", "copy"))
        if (audioFile != null) addAll(listOf("-c:a", "copy"))
        addAll(listOf("-movflags", "faststart", "-f", "mp4", outputFile.absolutePath))
    }

    fun isValidMp4File(file: File): Boolean {
        if (!file.isFile || !file.canRead() || file.length() < 12L) return false
        val prefix = ByteArray(128)
        val read = runCatching { FileInputStream(file).use { it.read(prefix) } }.getOrDefault(-1)
        if (read < 12) return false
        return (0..read - 8).any { index ->
            prefix[index + 4] == 'f'.code.toByte() &&
                prefix[index + 5] == 't'.code.toByte() &&
                prefix[index + 6] == 'y'.code.toByte() &&
                prefix[index + 7] == 'p'.code.toByte()
        }
    }

    private fun validateInput(file: File, label: String): MergeResult? {
        if (!file.isFile || !file.canRead() || file.length() <= 0L) {
            return MergeResult(false, MergeFailureCategory.MERGE_INPUT, diagnostics = "B 站${label}轨道不存在、不可读或为空")
        }
        val prefix = ByteArray(256)
        val read = runCatching { FileInputStream(file).use { it.read(prefix) } }.getOrDefault(-1)
        val text = if (read > 0) prefix.copyOf(read).toString(Charsets.UTF_8).trimStart().lowercase(Locale.US) else ""
        if (text.startsWith("<html") || text.startsWith("<!doctype") || text.startsWith("{") || text.startsWith("[")) {
            return MergeResult(false, MergeFailureCategory.MERGE_INPUT, diagnostics = "B 站${label}轨道疑似 HTTP 错误页")
        }
        return null
    }

    private fun moveAtomically(source: File, target: File) {
        try {
            Files.move(source.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE)
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(source.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING)
        }
    }

    private fun sanitizeDiagnostics(value: String): String = value
        .replace(Regex("https?://\\S+", RegexOption.IGNORE_CASE), "<url>")
        .replace(Regex("(?i)cookie\\s*[:=]\\s*\\S+"), "Cookie=<redacted>")
        .takeLast(MAX_DIAGNOSTICS_LENGTH)

    private const val MAX_DIAGNOSTICS_LENGTH = 2000

    suspend fun mergeTsFiles(tsFiles: List<File>, outputFile: File): Boolean = withContext(Dispatchers.IO) {
        require(tsFiles.isNotEmpty()) { "no ts files to merge" }
        outputFile.parentFile?.mkdirs()
        val listFile = File.createTempFile("m3u8-concat-", ".txt")
        try {
            listFile.writeText(tsFiles.joinToString("\n") { "file '${it.absolutePath.replace("'", "'\\''")}'" })
            val command = "-y -f concat -safe 0 -i \"${listFile.absolutePath}\" -c copy -bsf:a aac_adtstoasc \"${outputFile.absolutePath}\""
            val session = FFmpegKit.execute(command)
            ReturnCode.isSuccess(session.returnCode)
        } finally {
            listFile.delete()
        }
    }

    suspend fun saveMediaUrl(url: String, outputFile: File, headers: Map<String, String> = emptyMap()): Boolean = withContext(Dispatchers.IO) {
        outputFile.parentFile?.mkdirs()
        val command = mutableListOf("-y")
        val headerBlock = headers
            .filterValues { it.isNotBlank() }
            .map { (name, value) -> "${name}: ${value}\r\n" }
            .joinToString("")
        if (headerBlock.isNotBlank()) command += listOf("-headers", headerBlock)
        command += listOf("-i", url, "-c", "copy", outputFile.absolutePath)
        val session = FFmpegKit.executeWithArguments(command.toTypedArray())
        ReturnCode.isSuccess(session.returnCode)
    }

}
