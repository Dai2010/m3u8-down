package com.dai2010.m3u8down.network

const val DEFAULT_USER_AGENT = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36"

fun mediaRequestHeaders(referer: String): Map<String, String> = buildMap {
    put("User-Agent", DEFAULT_USER_AGENT)
    if (referer.isNotBlank()) put("Referer", referer)
}
