package com.dai2010.m3u8down.filter

import com.dai2010.m3u8down.parser.Playlist
import com.dai2010.m3u8down.parser.Segment

object AdFilter {
    fun isAdSegment(segment: Segment, keywords: List<String>, useRegex: Boolean = false): Boolean {
        val haystack = "${segment.url}\n${segment.title}"
        return if (useRegex) {
            keywords.any { Regex(it, RegexOption.IGNORE_CASE).containsMatchIn(haystack) }
        } else {
            val lowered = haystack.lowercase()
            keywords.any { lowered.contains(it.lowercase()) }
        }
    }

    fun filterPlaylist(playlist: Playlist, keywords: List<String>, useRegex: Boolean = false): Playlist {
        if (playlist.isMaster || keywords.isEmpty()) return playlist
        return playlist.copy(segments = playlist.segments.filterNot { isAdSegment(it, keywords, useRegex) })
    }
}
