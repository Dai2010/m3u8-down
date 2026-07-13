package com.dai2010.m3u8down.media

import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.Locale

enum class MediaKind(val displayName: String) {
    HLS("HLS/m3u8"),
    DASH("MPEG-DASH/mpd"),
    SMOOTH("Smooth Streaming"),
    RTSP("RTSP stream"),
    PROGRESSIVE("direct media"),
    UNKNOWN("unknown media"),
}

data class MediaInfo(val kind: MediaKind, val source: String = "unknown", val contentType: String = "")

object MediaTypeDetector {
    private val progressiveExtensions = setOf(
        ".mp4",
        ".m4v",
        ".mov",
        ".mkv",
        ".webm",
        ".flv",
        ".avi",
        ".ts",
        ".m2ts",
        ".mp3",
        ".m4a",
        ".aac",
        ".ogg",
        ".opus",
        ".wav",
    )

    fun detect(url: String, headers: Map<String, String> = emptyMap(), client: OkHttpClient = OkHttpClient()): MediaInfo {
        val byUrl = fromUrl(url)
        if (byUrl.kind != MediaKind.UNKNOWN) return byUrl

        runCatching {
            val request = Request.Builder().url(url).head().applyHeaders(headers).build()
            client.newCall(request).execute().use { response ->
                val byType = fromContentType(response.header("Content-Type").orEmpty())
                if (byType.kind != MediaKind.UNKNOWN) return byType
            }
        }

        return runCatching {
            val request = Request.Builder().url(url).header("Range", "bytes=0-4095").applyHeaders(headers).build()
            client.newCall(request).execute().use { response ->
                val byType = fromContentType(response.header("Content-Type").orEmpty())
                if (byType.kind != MediaKind.UNKNOWN) return byType
                val stream = response.body?.byteStream() ?: return@use MediaInfo(MediaKind.UNKNOWN)
                val buffer = ByteArray(4096)
                val bytesRead = stream.read(buffer)
                val preview = if (bytesRead > 0) String(buffer, 0, bytesRead, Charsets.UTF_8) else ""
                fromBody(preview)
            }
        }.getOrElse { MediaInfo(MediaKind.UNKNOWN) }
    }

    fun fromUrl(url: String): MediaInfo {
        val path = url.substringBefore('?').substringBefore('#').lowercase(Locale.ROOT)
        return when {
            path.startsWith("rtsp://") -> MediaInfo(MediaKind.RTSP, "url")
            path.endsWith(".m3u8") || path.endsWith(".m3u") -> MediaInfo(MediaKind.HLS, "url")
            path.endsWith(".mpd") -> MediaInfo(MediaKind.DASH, "url")
            path.endsWith("/manifest") && ".ism" in path -> MediaInfo(MediaKind.SMOOTH, "url")
            progressiveExtensions.any { path.endsWith(it) } -> MediaInfo(MediaKind.PROGRESSIVE, "url")
            else -> MediaInfo(MediaKind.UNKNOWN)
        }
    }

    fun fromContentType(contentType: String): MediaInfo {
        val normalized = contentType.substringBefore(';').trim().lowercase(Locale.ROOT)
        return when {
            normalized in setOf("application/vnd.apple.mpegurl", "application/x-mpegurl", "audio/mpegurl") -> MediaInfo(MediaKind.HLS, "content-type", contentType)
            normalized == "application/dash+xml" -> MediaInfo(MediaKind.DASH, "content-type", contentType)
            normalized == "application/vnd.ms-sstr+xml" -> MediaInfo(MediaKind.SMOOTH, "content-type", contentType)
            normalized.startsWith("video/") || normalized.startsWith("audio/") -> MediaInfo(MediaKind.PROGRESSIVE, "content-type", contentType)
            else -> MediaInfo(MediaKind.UNKNOWN, "content-type", contentType)
        }
    }

    fun fromBody(body: String): MediaInfo {
        val preview = body.trimStart('\ufeff', '\n', '\r', '\t', ' ')
        return when {
            preview.startsWith("#EXTM3U") -> MediaInfo(MediaKind.HLS, "body")
            preview.startsWith("<MPD") || preview.take(256).contains("<MPD") -> MediaInfo(MediaKind.DASH, "body")
            preview.startsWith("<SmoothStreamingMedia") || preview.take(256).contains("<SmoothStreamingMedia") -> MediaInfo(MediaKind.SMOOTH, "body")
            else -> MediaInfo(MediaKind.UNKNOWN, "body")
        }
    }

    private fun Request.Builder.applyHeaders(headers: Map<String, String>): Request.Builder = apply {
        headers.forEach { (name, value) -> if (value.isNotBlank()) header(name, value) }
    }
}
