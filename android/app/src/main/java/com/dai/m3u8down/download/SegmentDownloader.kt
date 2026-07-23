package com.dai2010.m3u8down.download

import com.dai2010.m3u8down.parser.Segment
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File

class SegmentDownloader(
    private val client: OkHttpClient,
    private val headers: Map<String, String> = emptyMap(),
) {
    suspend fun download(index: Int, segment: Segment, outputDir: File): File = withContext(Dispatchers.IO) {
        outputDir.mkdirs()
        val output = File(outputDir, "%05d.ts".format(index))
        if (output.exists() && output.length() > 0) return@withContext output

        val part = File(outputDir, "%05d.ts.part".format(index))
        val requestBuilder = Request.Builder().url(segment.url)
        headers.forEach { (name, value) -> if (value.isNotBlank()) requestBuilder.header(name, value) }
        client.newCall(requestBuilder.build()).execute().use { response ->
            if (!response.isSuccessful) error("HTTP ${response.code}: ${segment.url}")
            response.body?.byteStream()?.use { input ->
                part.outputStream().use { outputStream -> input.copyTo(outputStream) }
            } ?: error("empty response body: ${segment.url}")
        }
        part.renameTo(output)
        output
    }
}
