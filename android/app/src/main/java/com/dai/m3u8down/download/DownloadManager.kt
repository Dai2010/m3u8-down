package com.dai2010.m3u8down.download

import com.dai2010.m3u8down.filter.AdFilter
import com.dai2010.m3u8down.media.MediaKind
import com.dai2010.m3u8down.media.MediaTypeDetector
import com.dai2010.m3u8down.parser.M3U8Parser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File

data class DownloadProgress(val done: Int, val total: Int, val message: String)

class DownloadManager(
    private val client: OkHttpClient = OkHttpClient(),
) {
    fun download(
        url: String,
        outputFile: File,
        cacheDir: File,
        headers: Map<String, String>,
        keywords: List<String>,
        concurrency: Int = 8,
    ): Flow<DownloadProgress> = flow {
        emit(DownloadProgress(0, 0, "Detecting media type"))
        val mediaInfo = MediaTypeDetector.detect(url, headers, client)
        emit(DownloadProgress(0, 0, "Detected ${mediaInfo.kind.displayName}"))
        if (mediaInfo.kind != MediaKind.HLS) {
            emit(DownloadProgress(0, 1, "Downloading with FFmpeg"))
            check(Merger.saveMediaUrl(url, outputFile, headers)) { "ffmpeg download failed" }
            emit(DownloadProgress(1, 1, "Saved ${outputFile.absolutePath}"))
            return@flow
        }

        emit(DownloadProgress(0, 0, "Loading playlist"))
        val content = fetchText(url, headers)
        val parsed = M3U8Parser.parse(content, url)
        val mediaPlaylist = if (parsed.isMaster) {
            val variant = parsed.bestVariant() ?: error("master playlist has no variants")
            M3U8Parser.parse(fetchText(variant.url, headers), variant.url)
        } else parsed
        val playlist = AdFilter.filterPlaylist(mediaPlaylist, keywords)
        val segments = playlist.segments
        require(segments.isNotEmpty()) { "no playable segments after filtering" }

        val downloader = SegmentDownloader(client, headers)
        val semaphore = Semaphore(concurrency.coerceAtLeast(1))
        var done = 0
        val tsFiles = coroutineScope {
            segments.mapIndexed { index, segment ->
                async(Dispatchers.IO) {
                    semaphore.withPermit { downloader.download(index, segment, cacheDir) }
                }
            }.map { deferred ->
                val file = deferred.await()
                done += 1
                emit(DownloadProgress(done, segments.size, "Downloaded $done/${segments.size}"))
                file
            }
        }
        emit(DownloadProgress(done, segments.size, "Merging"))
        check(Merger.mergeTsFiles(tsFiles, outputFile)) { "ffmpeg merge failed" }
        emit(DownloadProgress(segments.size, segments.size, "Saved ${outputFile.absolutePath}"))
    }

    private suspend fun fetchText(url: String, headers: Map<String, String>): String = coroutineScope {
        async(Dispatchers.IO) {
            val builder = Request.Builder().url(url)
            headers.forEach { (name, value) -> if (value.isNotBlank()) builder.header(name, value) }
            client.newCall(builder.build()).execute().use { response ->
                if (!response.isSuccessful) error("HTTP ${response.code}: $url")
                response.body?.string() ?: error("empty response body: $url")
            }
        }.await()
    }
}
