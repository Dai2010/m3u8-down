package com.dai2010.m3u8down.download

import com.dai2010.m3u8down.network.BilibiliResolvedStream
import com.dai2010.m3u8down.network.prepareBilibiliHeaders
import java.io.File
import java.security.MessageDigest

class BilibiliPlaybackPreparationException(
    val category: String = "playback",
    message: String,
    cause: Throwable? = null,
) : RuntimeException(message, cause)

suspend fun prepareBilibiliPlayback(
    cacheDir: File,
    stream: BilibiliResolvedStream,
    headers: Map<String, String>,
): File {
    val playbackDir = File(cacheDir, "bilibili-playback-${bilibiliPlaybackKey(stream)}")
    val outputFile = File(playbackDir, "playback.mp4")
    val completeMarker = File(playbackDir, ".complete")
    if (outputFile.isFile && completeMarker.isFile && Merger.isValidMp4File(outputFile)) return outputFile

    playbackDir.deleteRecursively()
    check(playbackDir.mkdirs()) { "无法创建 B 站播放缓存目录" }
    try {
        val requestHeaders = prepareBilibiliHeaders(stream.video.url, headers, enabled = true)
        val client = okhttp3.OkHttpClient()
        val downloader = DirectDownloader(
            client = client,
            headers = requestHeaders,
            bilibiliCompatEnabled = true,
            preserveBilibiliMediaUrl = true,
        )
        val videoFile = File(playbackDir, "video.m4s")
        downloader.download(stream.video.url, videoFile, stream.video.backupUrls)
        val audioFile = stream.audio?.let { audio ->
            val file = File(playbackDir, "audio.m4s")
            downloader.download(audio.url, file, audio.backupUrls)
            file
        }
        val mergeResult = Merger.mergeBilibiliTracks(videoFile, audioFile, outputFile)
        if (!mergeResult.success) {
            throw BilibiliPlaybackPreparationException(
                category = mergeResult.category.name.lowercase(),
                message = "${mergeResult.category.name.lowercase()}：${mergeResult.diagnostics.ifBlank { "B 站 M4S 封装失败" }}（FFmpeg ${mergeResult.returnCode ?: "unknown"}，输入 ${mergeResult.videoBytes}/${mergeResult.audioBytes} bytes，输出 ${mergeResult.outputBytes} bytes）",
            )
        }
        check(Merger.isValidMp4File(outputFile)) { "B 站播放文件无法探测" }
        completeMarker.writeText("complete\n")
        return outputFile
    } catch (exc: BilibiliPlaybackPreparationException) {
        playbackDir.deleteRecursively()
        throw exc
    } catch (exc: DirectDownloadException) {
        playbackDir.deleteRecursively()
        throw BilibiliPlaybackPreparationException(
            category = "download_${exc.category.name.lowercase()}",
            message = "B 站轨道下载失败：${exc.message.orEmpty()}（HTTP ${exc.statusCode ?: "unknown"}，Content-Type ${exc.contentType ?: "unknown"}，长度 ${exc.actualBytes ?: "unknown"}）",
            cause = exc,
        )
    } catch (exc: Exception) {
        playbackDir.deleteRecursively()
        throw BilibiliPlaybackPreparationException("playback", "B 站 M4S 轨道下载或封装失败：${exc.message.orEmpty()}", exc)
    }
}

private fun bilibiliPlaybackKey(stream: BilibiliResolvedStream): String {
    val source = buildString {
        append(stream.page?.cid.orEmpty())
        append('\u0000')
        append(stream.page?.page ?: 0)
        append('\u0000')
        append(trackKey(stream.video))
        append('\u0000')
        append(trackKey(stream.audio))
    }
    return MessageDigest.getInstance("SHA-256")
        .digest(source.toByteArray(Charsets.UTF_8))
        .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
        .take(24)
}

private fun trackKey(track: com.dai2010.m3u8down.network.BilibiliDashTrack?): String = track?.let {
    buildString {
        append(it.url)
        append('\u0000')
        append(it.id)
        append('\u0000')
        append(it.codecId)
        append('\u0000')
        append(it.codecs)
        append('\u0000')
        append(it.width)
        append('x')
        append(it.height)
        append('\u0000')
        append(it.bandwidth)
    }
}.orEmpty()
