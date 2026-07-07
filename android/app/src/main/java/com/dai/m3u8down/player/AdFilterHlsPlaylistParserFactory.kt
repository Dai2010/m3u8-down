package com.dai2010.m3u8down.player

import com.dai2010.m3u8down.filter.AdFilter
import com.dai2010.m3u8down.parser.M3U8Parser

class AdFilterHlsPlaylistParserFactory(
    private val keywords: List<String>,
) {
    fun filterPlaylistText(content: String, baseUrl: String): String {
        val playlist = M3U8Parser.parse(content, baseUrl)
        return M3U8Parser.serialize(AdFilter.filterPlaylist(playlist, keywords))
    }
}
