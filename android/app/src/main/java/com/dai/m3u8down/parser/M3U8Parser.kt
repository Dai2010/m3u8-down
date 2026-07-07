package com.dai2010.m3u8down.parser

import java.net.URI

data class Segment(
    val duration: Double,
    val url: String,
    val title: String = "",
    val discontinuity: Boolean = false,
)

data class Variant(
    val bandwidth: Int = 0,
    val resolution: String = "",
    val codecs: String = "",
    val url: String = "",
)

data class Playlist(
    val version: Int = 0,
    val targetDuration: Double = 0.0,
    val mediaSequence: Int = 0,
    val playlistType: String = "",
    val segments: List<Segment> = emptyList(),
    val variants: List<Variant> = emptyList(),
) {
    val isMaster: Boolean get() = variants.isNotEmpty()
    fun bestVariant(): Variant? = variants.maxByOrNull { it.bandwidth }
}

object M3U8Parser {
    fun parse(content: String, baseUrl: String): Playlist {
        val lines = content.lineSequence().map { it.trim() }.filter { it.isNotEmpty() }.toList()
        require(lines.firstOrNull() == "#EXTM3U") { "playlist must start with #EXTM3U" }

        var version = 0
        var targetDuration = 0.0
        var mediaSequence = 0
        var playlistType = ""
        var pendingDuration: Double? = null
        var pendingTitle = ""
        var pendingDiscontinuity = false
        var pendingVariant: Map<String, String>? = null
        val segments = mutableListOf<Segment>()
        val variants = mutableListOf<Variant>()

        for (line in lines.drop(1)) {
            when {
                line.startsWith("#EXT-X-VERSION:") -> version = line.substringAfter(":").toInt()
                line.startsWith("#EXT-X-TARGETDURATION:") -> targetDuration = line.substringAfter(":").toDouble()
                line.startsWith("#EXT-X-MEDIA-SEQUENCE:") -> mediaSequence = line.substringAfter(":").toInt()
                line.startsWith("#EXT-X-PLAYLIST-TYPE:") -> playlistType = line.substringAfter(":").uppercase()
                line == "#EXT-X-DISCONTINUITY" -> pendingDiscontinuity = true
                line.startsWith("#EXT-X-STREAM-INF:") -> pendingVariant = parseAttributes(line.substringAfter(":"))
                line.startsWith("#EXTINF:") -> {
                    val value = line.substringAfter(":")
                    pendingDuration = value.substringBefore(",").toDouble()
                    pendingTitle = value.substringAfter(",", "").trim()
                }
                line.startsWith("#") -> Unit
                pendingVariant != null -> {
                    val attrs = pendingVariant.orEmpty()
                    variants += Variant(
                        bandwidth = attrs["BANDWIDTH"]?.toIntOrNull() ?: 0,
                        resolution = attrs["RESOLUTION"].orEmpty(),
                        codecs = attrs["CODECS"].orEmpty(),
                        url = resolveUrl(baseUrl, line),
                    )
                    pendingVariant = null
                }
                pendingDuration != null -> {
                    segments += Segment(
                        duration = pendingDuration ?: 0.0,
                        url = resolveUrl(baseUrl, line),
                        title = pendingTitle,
                        discontinuity = pendingDiscontinuity,
                    )
                    pendingDuration = null
                    pendingTitle = ""
                    pendingDiscontinuity = false
                }
                else -> error("URI without matching tag: $line")
            }
        }

        return Playlist(version, targetDuration, mediaSequence, playlistType, segments, variants)
    }

    fun serialize(playlist: Playlist): String = buildString {
        appendLine("#EXTM3U")
        if (playlist.version > 0) appendLine("#EXT-X-VERSION:${playlist.version}")
        if (playlist.isMaster) {
            playlist.variants.forEach { variant ->
                val attrs = buildList {
                    if (variant.bandwidth > 0) add("BANDWIDTH=${variant.bandwidth}")
                    if (variant.resolution.isNotBlank()) add("RESOLUTION=${variant.resolution}")
                    if (variant.codecs.isNotBlank()) add("CODECS=\"${variant.codecs}\"")
                }.joinToString(",")
                appendLine("#EXT-X-STREAM-INF:$attrs")
                appendLine(variant.url)
            }
            return@buildString
        }
        if (playlist.targetDuration > 0) appendLine("#EXT-X-TARGETDURATION:${playlist.targetDuration.toInt()}")
        if (playlist.mediaSequence > 0) appendLine("#EXT-X-MEDIA-SEQUENCE:${playlist.mediaSequence}")
        if (playlist.playlistType.isNotBlank()) appendLine("#EXT-X-PLAYLIST-TYPE:${playlist.playlistType}")
        playlist.segments.forEach { segment ->
            if (segment.discontinuity) appendLine("#EXT-X-DISCONTINUITY")
            appendLine("#EXTINF:${trimNumber(segment.duration)},${segment.title}")
            appendLine(segment.url)
        }
        appendLine("#EXT-X-ENDLIST")
    }

    fun resolveUrl(baseUrl: String, relative: String): String = URI(baseUrl).resolve(relative).toString()

    private fun parseAttributes(value: String): Map<String, String> {
        val result = mutableMapOf<String, String>()
        val current = StringBuilder()
        var inQuote = false
        val items = mutableListOf<String>()
        value.forEach { char ->
            if (char == '"') inQuote = !inQuote
            if (char == ',' && !inQuote) {
                items += current.toString()
                current.clear()
            } else {
                current.append(char)
            }
        }
        if (current.isNotEmpty()) items += current.toString()
        items.forEach { item ->
            val key = item.substringBefore("=").trim().uppercase()
            val raw = item.substringAfter("=", "").trim().trim('"')
            if (key.isNotBlank()) result[key] = raw
        }
        return result
    }

    private fun trimNumber(value: Double): String = if (value % 1.0 == 0.0) value.toInt().toString() else value.toString().trimEnd('0').trimEnd('.')
}
