package com.dai2010.m3u8down.download

import com.dai2010.m3u8down.filter.AdFilter
import com.dai2010.m3u8down.media.MediaInfo
import com.dai2010.m3u8down.media.MediaKind
import com.dai2010.m3u8down.media.MediaTypeDetector
import com.dai2010.m3u8down.network.isBilibiliUrl
import com.dai2010.m3u8down.network.prepareBilibiliHeaders
import com.dai2010.m3u8down.network.prepareBilibiliUrl
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
        detectedInfo: MediaInfo? = null,
        bilibiliCompatEnabled: Boolean = false,
    ): Flow<DownloadProgress> = flow {
        val effectiveBilibiliCompat = bilibiliCompatEnabled || isBilibiliUrl(url)
        val requestUrl = prepareBilibiliUrl(url, effectiveBilibiliCompat)
        val requestHeaders = prepareBilibiliHeaders(requestUrl, headers, effectiveBilibiliCompat)
        emit(DownloadProgress(0, 0, "Detecting media type"))
        val mediaInfo = detectedInfo ?: MediaTypeDetector.detect(url, requestHeaders, client, effectiveBilibiliCompat)
        emit(DownloadProgress(0, 0, "Detected ${mediaInfo.kind.displayName}"))
        if (mediaInfo.kind == MediaKind.PROGRESSIVE) {
            emit(DownloadProgress(0, 1, "Downloading direct media"))
            DirectDownloader(client, requestHeaders, effectiveBilibiliCompat).download(requestUrl, outputFile)
            emit(DownloadProgress(1, 1, "Saved ${outputFile.absolutePath}"))
            return@flow
        }

        if (mediaInfo.kind != MediaKind.HLS) {
            emit(DownloadProgress(0, 1, "Downloading with FFmpeg"))
            check(Merger.saveMediaUrl(requestUrl, outputFile, requestHeaders)) { "ffmpeg download failed" }
            emit(DownloadProgress(1, 1, "Saved ${outputFile.absolutePath}"))
            return@flow
        }

        emit(DownloadProgress(0, 0, "Loading playlist"))
        val content = fetchText(requestUrl, requestHeaders, effectiveBilibiliCompat)
        val parsed = M3U8Parser.parse(content, requestUrl)
        val mediaPlaylist = if (parsed.isMaster) {
            val variant = parsed.bestVariant() ?: error("master playlist has no variants")
            val variantUrl = prepareBilibiliUrl(variant.url, effectiveBilibiliCompat)
            M3U8Parser.parse(fetchText(variantUrl, requestHeaders, effectiveBilibiliCompat), variantUrl)
        } else parsed
        val playlist = AdFilter.filterPlaylist(mediaPlaylist, keywords)
        val segments = playlist.segments
        require(segments.isNotEmpty()) { "no playable segments after filtering" }

        val downloader = SegmentDownloader(client, requestHeaders, effectiveBilibiliCompat)
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

    private suspend fun fetchText(url: String, headers: Map<String, String>, bilibiliCompatEnabled: Boolean): String = coroutineScope {
        async(Dispatchers.IO) {
            val requestUrl = prepareBilibiliUrl(url, bilibiliCompatEnabled || isBilibiliUrl(url))
            val requestHeaders = prepareBilibiliHeaders(requestUrl, headers, bilibiliCompatEnabled)
            val builder = Request.Builder().url(requestUrl)
            requestHeaders.forEach { (name, value) -> if (value.isNotBlank()) builder.header(name, value) }
            client.newCall(builder.build()).execute().use { response ->
                if (!response.isSuccessful) error("HTTP ${response.code}: $requestUrl")
                response.body?.string() ?: error("empty response body: $requestUrl")
            }
        }.await()
    }
}
