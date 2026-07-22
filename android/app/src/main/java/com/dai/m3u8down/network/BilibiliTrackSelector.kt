package com.dai2010.m3u8down.network

import android.net.Uri
import android.media.MediaCodecList

private const val VIDEO_AVC_MIME = "video/avc"
private const val VIDEO_HEVC_MIME = "video/hevc"
private const val VIDEO_AV1_MIME = "video/av01"
private const val AUDIO_AAC_MIME = "audio/mp4a-latm"
private const val AUDIO_AC3_MIME = "audio/ac3"
private const val AUDIO_EAC3_MIME = "audio/eac3"
private const val AUDIO_AC4_MIME = "audio/ac4"
private const val AUDIO_OPUS_MIME = "audio/opus"
private const val AUDIO_VORBIS_MIME = "audio/vorbis"

fun selectBilibiliTracks(stream: BilibiliResolvedStream): BilibiliResolvedStream {
    val videoCandidates = stream.videoTracks.ifEmpty { listOf(stream.video) }
    val supportedVideos = videoCandidates.filter { isTrackSupported(it, isAudio = false) }
    if (supportedVideos.isEmpty()) {
        throw BilibiliResolverException(
            "unsupported_codec",
            "当前 Android 解码器不支持 B 站视频编码：${stream.video.codecs.ifBlank { stream.video.codecId.toString() }}",
        )
    }
    val selectedVideo = supportedVideos.maxWithOrNull(compareBy<BilibiliDashTrack> { codecPriority(it.codecId) }
        .thenBy { it.id }
        .thenBy { it.bandwidth }) ?: stream.video

    val audioCandidates = stream.audioTracks.ifEmpty { listOfNotNull(stream.audio) }
    val supportedAudios = audioCandidates.filter { isTrackSupported(it, isAudio = true) }
    val selectedAudio = if (audioCandidates.isEmpty()) {
        null
    } else {
        supportedAudios.maxWithOrNull(compareBy<BilibiliDashTrack> { it.bandwidth }.thenBy { it.id })
            ?: throw BilibiliResolverException(
                "unsupported_codec",
                "当前 Android 解码器不支持 B 站音频编码：${stream.audio?.codecs.orEmpty().ifBlank { "unknown" }}",
            )
    }
    return stream.copy(video = selectedVideo, audio = selectedAudio)
}

fun unsupportedBilibiliProtocols(stream: BilibiliResolvedStream): List<String> =
    listOfNotNull(stream.video, stream.audio)
        .flatMap { track -> listOf(track.url) + track.backupUrls }
        .map { url -> runCatching { Uri.parse(url).scheme?.lowercase().orEmpty() }.getOrDefault("") }
        .map { protocol -> protocol.ifBlank { "<missing>" } }
        .filter { protocol -> protocol !in setOf("http", "https") }
        .distinct()

private fun isTrackSupported(track: BilibiliDashTrack, isAudio: Boolean): Boolean {
    val mimeType = trackMimeType(track, isAudio) ?: return true
    return runCatching {
        MediaCodecList(MediaCodecList.REGULAR_CODECS).codecInfos
            .asSequence()
            .filterNot { it.isEncoder }
            .mapNotNull { codecInfo ->
                if (!codecInfo.supportedTypes.any { it.equals(mimeType, ignoreCase = true) }) return@mapNotNull null
                runCatching { codecInfo.getCapabilitiesForType(mimeType) }.getOrNull()
            }
            .any { capabilities ->
                val videoCapabilities = capabilities.videoCapabilities
                videoCapabilities == null || track.width <= 0 || track.height <= 0 || videoCapabilities.isSizeSupported(track.width, track.height)
            }
    }.getOrDefault(true)
}

private fun trackMimeType(track: BilibiliDashTrack, isAudio: Boolean): String? {
    val codecs = track.codecs.lowercase()
    if (isAudio) {
        return when {
            codecs.contains("mp4a") -> AUDIO_AAC_MIME
            codecs.contains("ac-4") -> AUDIO_AC4_MIME
            codecs.contains("ec-3") -> AUDIO_EAC3_MIME
            codecs.contains("ac-3") -> AUDIO_AC3_MIME
            codecs.contains("opus") -> AUDIO_OPUS_MIME
            codecs.contains("vorbis") -> AUDIO_VORBIS_MIME
            else -> null
        }
    }
    return when {
        track.codecId == 7 || codecs.contains("avc") -> VIDEO_AVC_MIME
        track.codecId == 12 || codecs.contains("hev") || codecs.contains("hvc") -> VIDEO_HEVC_MIME
        track.codecId == 13 || codecs.contains("av01") -> VIDEO_AV1_MIME
        else -> null
    }
}

private fun codecPriority(codecId: Int): Int = when (codecId) {
    7 -> 3
    12 -> 2
    13 -> 1
    else -> 0
}
