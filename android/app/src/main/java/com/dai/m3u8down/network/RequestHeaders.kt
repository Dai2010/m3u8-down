package com.dai2010.m3u8down.network

import android.net.Uri
import android.os.SystemClock

const val DEFAULT_USER_AGENT = "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Mobile Safari/537.36"

private const val BILIBILI_FALLBACK_HOST = "upos-sz-mirrorcoso1.bilivideo.com"

fun isBilibiliUrl(url: String): Boolean {
    val host = runCatching { Uri.parse(url).host.orEmpty().lowercase().trimEnd('.') }.getOrDefault("")
    return BILIBILI_HOST_SUFFIXES.any { host == it || host.endsWith(".$it") }
}

private val bilibiliRequestLock = Any()
private var nextBilibiliRequestAt = 0L

fun throttleBilibiliRequest(url: String, intervalMs: Long = 400L) {
    if (!isBilibiliUrl(url)) return
    val waitMs = synchronized(bilibiliRequestLock) {
        val now = SystemClock.elapsedRealtime()
        val start = maxOf(now, nextBilibiliRequestAt)
        nextBilibiliRequestAt = start + intervalMs.coerceAtLeast(0L)
        start - now
    }
    if (waitMs > 0L) Thread.sleep(waitMs)
}

fun prepareBilibiliUrl(url: String, enabled: Boolean = false): String {
    if (!enabled && !isBilibiliUrl(url)) return url
    if (!isBilibiliUrl(url)) return url
    val parsed = Uri.parse(url)
    val host = parsed.host.orEmpty().lowercase().trimEnd('.')
    if (!isBilivideoHost(host)) return url
    if (!parsed.scheme.equals("https", ignoreCase = true)) return url
    if (host.contains("-cmcc")) return url
    if (usesAndroidPlatform(url)) return url
    if (host.endsWith(".mcdn.bilivideo.cn") && parsed.port != -1) return url
    return parsed.buildUpon().scheme("http").build().toString()
}

fun prepareBilibiliHeaders(url: String, headers: Map<String, String> = emptyMap(), enabled: Boolean = false): Map<String, String> {
    val output = headers.filterValues { it.isNotBlank() }.toMutableMap()
    if (!enabled && !isBilibiliUrl(url)) return output
    if (output.keys.none { it.equals("User-Agent", ignoreCase = true) }) output["User-Agent"] = "Mozilla/5.0"
    if (!usesAndroidPlatform(url) && output.keys.none { it.equals("Referer", ignoreCase = true) }) output["Referer"] = "https://www.bilibili.com"
    if (isBilibiliUrl(url) && output.keys.none { it.equals("Origin", ignoreCase = true) }) output["Origin"] = "https://www.bilibili.com"
    if (isBilibiliMediaUrl(url)) {
        if (output.keys.none { it.equals("Accept", ignoreCase = true) }) output["Accept"] = "*/*"
        if (output.keys.none { it.equals("Accept-Encoding", ignoreCase = true) }) output["Accept-Encoding"] = "identity"
    }
    return output
}

fun bilibiliMediaUrlVariants(url: String): List<String> {
    if (!isBilibiliMediaUrl(url)) return listOf(url)
    val parsed = runCatching { Uri.parse(url) }.getOrNull() ?: return listOf(url)
    val host = parsed.host.orEmpty().lowercase().trimEnd('.')
    return buildList {
        add(url)
        if (parsed.scheme.equals("https", ignoreCase = true) && shouldTryHttp(host, url)) {
            add(parsed.buildUpon().scheme("http").build().toString())
        }
        if (host.startsWith("upos-sz-") && !host.equals(BILIBILI_FALLBACK_HOST, ignoreCase = true)) {
            add(parsed.buildUpon().authority(BILIBILI_FALLBACK_HOST).build().toString())
            if (parsed.scheme.equals("https", ignoreCase = true) && shouldTryHttp(BILIBILI_FALLBACK_HOST, url)) {
                add(parsed.buildUpon().scheme("http").authority(BILIBILI_FALLBACK_HOST).build().toString())
            }
        }
    }.distinct()
}

fun mediaRequestHeaders(referer: String, url: String = "", bilibiliCompatEnabled: Boolean = false, cookie: String = ""): Map<String, String> {
    val base = buildMap {
        put("User-Agent", DEFAULT_USER_AGENT)
        if (referer.isNotBlank()) put("Referer", referer)
        if (cookie.isNotBlank() && isBilibiliUrl(url)) put("Cookie", cookie)
    }
    return prepareBilibiliHeaders(url, base, bilibiliCompatEnabled)
}

private val BILIBILI_HOST_SUFFIXES = listOf("bilibili.com", "bilibili.tv", "bilivideo.com", "bilivideo.cn", "b23.tv", "bili2233.cn")

private fun isBilivideoHost(host: String): Boolean =
    host == "bilivideo.com" || host.endsWith(".bilivideo.com") || host == "bilivideo.cn" || host.endsWith(".bilivideo.cn")

private fun isBilibiliMediaUrl(url: String): Boolean {
    if (!isBilibiliUrl(url)) return false
    val path = runCatching { Uri.parse(url).path.orEmpty() }.getOrDefault("")
    return path.endsWith(".m4s", ignoreCase = true)
}

private fun shouldTryHttp(host: String, url: String): Boolean =
    !host.contains("-cmcc") && !usesAndroidPlatform(url) && !(host.endsWith(".mcdn.bilivideo.cn") && Uri.parse(url).port != -1)

private fun usesAndroidPlatform(url: String): Boolean {
    val lowered = url.lowercase()
    return "platform=android_tv_yst" in lowered || "platform=android" in lowered
}
