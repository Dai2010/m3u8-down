package com.dai.m3u8down.download

import com.dai2010.m3u8down.network.BilibiliResolvedStream
import com.dai2010.m3u8down.network.prepareBilibiliHeaders
import java.io.File
import java.security.MessageDigest

class BilibiliPlaybackPreparationException(
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
    if (outputFile.isFile && outputFile.length() > 0L && completeMarker.isFile) return outputFile

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
        check(Merger.mergeBilibiliTracks(videoFile, audioFile, outputFile)) { "FFmpeg 无法封装 B 站 M4S 轨道" }
        check(outputFile.isFile && outputFile.length() > 0L) { "B 站播放文件为空" }
        completeMarker.writeText("complete\n")
        return outputFile
    } catch (exc: BilibiliPlaybackPreparationException) {
        playbackDir.deleteRecursively()
        throw exc
    } catch (exc: Exception) {
        playbackDir.deleteRecursively()
        throw BilibiliPlaybackPreparationException("B 站 M4S 轨道下载或封装失败", exc)
    }
}

private fun bilibiliPlaybackKey(stream: BilibiliResolvedStream): String {
    val source = buildString {
        append(stream.page?.cid.orEmpty())
        append('\u0000')
        append(stream.video.url)
        append('\u0000')
        append(stream.audio?.url.orEmpty())
    }
    return MessageDigest.getInstance("SHA-256")
        .digest(source.toByteArray(Charsets.UTF_8))
        .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }
        .take(24)
}
