package com.dai2010.m3u8down.media

import okhttp3.OkHttpClient
import okhttp3.Request
import com.dai2010.m3u8down.network.prepareBilibiliUrl
import com.dai2010.m3u8down.network.throttleBilibiliRequest
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
        ".m4s",
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

    fun detect(url: String, headers: Map<String, String> = emptyMap(), client: OkHttpClient = OkHttpClient(), bilibiliCompatEnabled: Boolean = false): MediaInfo {
        val byUrl = fromUrl(url)
        if (byUrl.kind != MediaKind.UNKNOWN) return byUrl

        val requestUrl = prepareBilibiliUrl(url, bilibiliCompatEnabled)

        runCatching {
            val request = Request.Builder().url(requestUrl).head().applyHeaders(headers).build()
            throttleBilibiliRequest(requestUrl)
            client.newCall(request).execute().use { response ->
                val byType = fromContentType(response.header("Content-Type").orEmpty())
                if (byType.kind != MediaKind.UNKNOWN) return byType
            }
        }

        return runCatching {
            val request = Request.Builder().url(requestUrl).header("Range", "bytes=0-4095").applyHeaders(headers).build()
            throttleBilibiliRequest(requestUrl)
            client.newCall(request).execute().use { response ->
                val byType = fromContentType(response.header("Content-Type").orEmpty())
                if (byType.kind != MediaKind.UNKNOWN) return byType
                val stream = response.body?.byteStream() ?: return@use MediaInfo(MediaKind.UNKNOWN)
                val buffer = ByteArray(4096)
                val bytesRead = stream.read(buffer)
                fromBytes(buffer, bytesRead.coerceAtLeast(0), response.header("Content-Type").orEmpty())
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
            normalized in setOf("application/mp4", "application/fmp4") || normalized.startsWith("video/") || normalized.startsWith("audio/") -> MediaInfo(MediaKind.PROGRESSIVE, "content-type", contentType)
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

    fun fromBytes(bytes: ByteArray, length: Int, contentType: String = ""): MediaInfo {
        val safeLength = length.coerceIn(0, bytes.size)
        val textInfo = fromBody(String(bytes, 0, safeLength, Charsets.UTF_8))
        if (textInfo.kind != MediaKind.UNKNOWN) return textInfo
        if (looksLikeProgressiveBytes(bytes, safeLength)) return MediaInfo(MediaKind.PROGRESSIVE, "body", progressiveContentType(bytes, safeLength, contentType))
        return MediaInfo(MediaKind.UNKNOWN, "body", contentType)
    }

    private fun looksLikeProgressiveBytes(bytes: ByteArray, length: Int): Boolean {
        if (length >= 8 && bytes.copyOfRange(4, 8).contentEquals(byteArrayOf('f'.code.toByte(), 't'.code.toByte(), 'y'.code.toByte(), 'p'.code.toByte()))) return true
        if (length >= 4 && (bytes.copyOfRange(0, 4).contentEquals(byteArrayOf(0x1A, 0x45.toByte(), 0xDF.toByte(), 0xA3.toByte())) ||
                bytes.copyOfRange(0, 4).contentEquals("OggS".toByteArray()) ||
                bytes.copyOfRange(0, 4).contentEquals("RIFF".toByteArray()))) return true
        if (length >= 3 && bytes.copyOfRange(0, 3).contentEquals("ID3".toByteArray())) return true
        if (length >= 2 && (bytes[0].toInt() and 0xFF) == 0xFF && (bytes[1].toInt() and 0xE0) == 0xE0) return true
        if (length >= 2 && (bytes[0].toInt() and 0xFF) == 0xFF && (bytes[1].toInt() and 0xF6) == 0xF0) return true
        return listOf(0, 188, 376).any { it < length && (bytes[it].toInt() and 0xFF) == 0x47 }
    }

    private fun progressiveContentType(bytes: ByteArray, length: Int, contentType: String): String {
        val normalized = contentType.substringBefore(';').trim().lowercase(Locale.ROOT)
        if (normalized.isNotBlank() && normalized != "application/octet-stream") return contentType
        if (length >= 8 && bytes.copyOfRange(4, 8).contentEquals(byteArrayOf('f'.code.toByte(), 't'.code.toByte(), 'y'.code.toByte(), 'p'.code.toByte()))) return "video/mp4"
        if (listOf(0, 188, 376).any { it < length && (bytes[it].toInt() and 0xFF) == 0x47 }) return "video/mp2t"
        return contentType
    }

    private fun Request.Builder.applyHeaders(headers: Map<String, String>): Request.Builder = apply {
        headers.forEach { (name, value) -> if (value.isNotBlank()) header(name, value) }
    }
}
