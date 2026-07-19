package com.dai2010.m3u8down.network

import android.net.Uri

const val DEFAULT_USER_AGENT = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36"

fun isBilibiliUrl(url: String): Boolean {
    val host = runCatching { Uri.parse(url).host.orEmpty().lowercase().trimEnd('.') }.getOrDefault("")
    return BILIBILI_HOST_SUFFIXES.any { host == it || host.endsWith(".$it") }
}

fun prepareBilibiliUrl(url: String, enabled: Boolean = false): String {
    if (!enabled && !isBilibiliUrl(url)) return url
    if (!isBilibiliUrl(url)) return url
    val parsed = Uri.parse(url)
    val host = parsed.host.orEmpty().lowercase().trimEnd('.')
    if (!isBilivideoHost(host)) return url
    return url
}

fun prepareBilibiliHeaders(url: String, headers: Map<String, String> = emptyMap(), enabled: Boolean = false): Map<String, String> {
    val output = headers.filterValues { it.isNotBlank() }.toMutableMap()
    if (!enabled && !isBilibiliUrl(url)) return output
    if (output.keys.none { it.equals("User-Agent", ignoreCase = true) }) output["User-Agent"] = "Mozilla/5.0"
    if (!usesAndroidPlatform(url) && output.keys.none { it.equals("Referer", ignoreCase = true) }) output["Referer"] = "https://www.bilibili.com"
    return output
}

fun mediaRequestHeaders(referer: String, url: String = "", bilibiliCompatEnabled: Boolean = false): Map<String, String> {
    val base = buildMap {
        put("User-Agent", DEFAULT_USER_AGENT)
        if (referer.isNotBlank()) put("Referer", referer)
    }
    return prepareBilibiliHeaders(url, base, bilibiliCompatEnabled)
}

private val BILIBILI_HOST_SUFFIXES = listOf("bilibili.com", "bilibili.tv", "bilivideo.com", "bilivideo.cn")

private fun isBilivideoHost(host: String): Boolean =
    host == "bilivideo.com" || host.endsWith(".bilivideo.com") || host == "bilivideo.cn" || host.endsWith(".bilivideo.cn")

private fun usesAndroidPlatform(url: String): Boolean {
    val lowered = url.lowercase()
    return "platform=android_tv_yst" in lowered || "platform=android" in lowered
}
