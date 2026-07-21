package com.dai2010.m3u8down.download

import com.dai2010.m3u8down.filter.AdFilter
import com.dai2010.m3u8down.media.MediaInfo
import com.dai2010.m3u8down.media.MediaKind
import com.dai2010.m3u8down.media.MediaTypeDetector
import com.dai2010.m3u8down.network.isBilibiliUrl
import com.dai2010.m3u8down.network.BilibiliStreamResolver
import com.dai2010.m3u8down.network.prepareBilibiliHeaders
import com.dai2010.m3u8down.network.prepareBilibiliUrl
import com.dai2010.m3u8down.network.throttleBilibiliRequest
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
        bilibiliQualityId: Int? = null,
        bilibiliSaveSubtitles: Boolean = true,
        bilibiliSaveCover: Boolean = true,
        bilibiliSaveDanmaku: Boolean = false,
        bilibiliSaveChapters: Boolean = true,
        bilibiliSaveInfo: Boolean = true,
    ): Flow<DownloadProgress> = flow {
        val effectiveBilibiliCompat = bilibiliCompatEnabled || isBilibiliUrl(url)
        val requestUrl = prepareBilibiliUrl(url, effectiveBilibiliCompat)
        val requestHeaders = prepareBilibiliHeaders(requestUrl, headers, effectiveBilibiliCompat)
        val isBilibiliPage = effectiveBilibiliCompat && BilibiliStreamResolver.isBilibiliPageUrl(url)
        emit(DownloadProgress(0, 0, "Detecting media type"))
        val mediaInfo = if (isBilibiliPage) {
            MediaInfo(MediaKind.DASH, "bilibili-dash", "application/dash+xml")
        } else {
            detectedInfo ?: MediaTypeDetector.detect(url, requestHeaders, client, effectiveBilibiliCompat)
        }
        emit(DownloadProgress(0, 0, "Detected ${mediaInfo.kind.displayName}"))
        if (isBilibiliPage) {
            emit(DownloadProgress(0, 2, "解析 B 站页面和分 P"))
            val stream = BilibiliStreamResolver.resolvePage(url, requestHeaders, client, bilibiliQualityId)
            val videoFile = File(cacheDir, "bilibili-video.m4s")
            val audioFile = stream.audio?.let { File(cacheDir, "bilibili-audio.m4s") }
            DirectDownloader(client, requestHeaders, effectiveBilibiliCompat).download(stream.video.url, videoFile, stream.video.backupUrls)
            emit(DownloadProgress(1, 2, "视频轨道下载完成"))
            if (stream.audio != null && audioFile != null) {
                DirectDownloader(client, requestHeaders, effectiveBilibiliCompat).download(stream.audio.url, audioFile, stream.audio.backupUrls)
            }
            emit(DownloadProgress(2, 2, "正在合并 B 站音视频"))
            check(Merger.mergeBilibiliTracks(videoFile, audioFile, outputFile)) { "B 站音视频合并失败" }
            emit(DownloadProgress(2, 2, "已保存 ${outputFile.absolutePath}"))
            return@flow
        }
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
        val effectiveConcurrency = if (effectiveBilibiliCompat) {
            minOf(concurrency.coerceAtLeast(1), 2)
        } else {
            concurrency.coerceAtLeast(1)
        }
        val semaphore = Semaphore(effectiveConcurrency)
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
            throttleBilibiliRequest(requestUrl)
            client.newCall(builder.build()).execute().use { response ->
                if (!response.isSuccessful) error("HTTP ${response.code}: $requestUrl")
                response.body?.string() ?: error("empty response body: $requestUrl")
            }
        }.await()
    }
}
