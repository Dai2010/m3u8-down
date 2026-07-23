package com.dai2010.m3u8down.download

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File

class DirectDownloader(
    private val client: OkHttpClient,
    private val headers: Map<String, String> = emptyMap(),
) {
    suspend fun download(url: String, outputFile: File): File = withContext(Dispatchers.IO) {
        outputFile.parentFile?.mkdirs()
        val part = File("${outputFile.absolutePath}.part")
        try {
            val requestBuilder = Request.Builder().url(url)
            headers.forEach { (name, value) -> if (value.isNotBlank()) requestBuilder.header(name, value) }
            client.newCall(requestBuilder.build()).execute().use { response ->
                if (!response.isSuccessful) error("HTTP ${response.code}: $url")
                response.body?.byteStream()?.use { input ->
                    part.outputStream().use { output -> input.copyTo(output) }
                } ?: error("empty response body: $url")
            }
            if (outputFile.exists()) outputFile.delete()
            check(part.renameTo(outputFile)) { "cannot move downloaded file" }
        } catch (exc: Exception) {
            part.delete()
            throw exc
        }
        outputFile
    }
}
