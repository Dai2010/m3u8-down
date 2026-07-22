package com.dai2010.m3u8down.download

import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.ReturnCode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

object Merger {
    suspend fun mergeBilibiliTracks(videoFile: File, audioFile: File?, outputFile: File): Boolean = withContext(Dispatchers.IO) {
        require(videoFile.exists()) { "B 站视频轨道不存在" }
        if (audioFile != null) require(audioFile.exists()) { "B 站音频轨道不存在" }
        outputFile.parentFile?.mkdirs()
        val command = mutableListOf("-y", "-i", videoFile.absolutePath)
        if (audioFile != null) command += listOf("-i", audioFile.absolutePath)
        command += listOf("-map", "0:v:0")
        if (audioFile != null) command += listOf("-map", "1:a:0")
        command += listOf("-c:v", "copy")
        if (audioFile != null) command += listOf("-c:a", "copy")
        command += listOf("-movflags", "faststart", "-strict", "unofficial", "-strict", "-2", "-f", "mp4")
        command += outputFile.absolutePath
        val session = FFmpegKit.executeWithArguments(command.toTypedArray())
        ReturnCode.isSuccess(session.returnCode)
    }

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
