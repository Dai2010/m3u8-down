package com.dai2010.m3u8down.download

import com.arthenica.ffmpegkit.FFmpegKit
import com.arthenica.ffmpegkit.ReturnCode
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

object Merger {
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
}
