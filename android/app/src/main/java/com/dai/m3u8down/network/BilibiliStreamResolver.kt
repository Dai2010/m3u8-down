package com.dai2010.m3u8down.network

import android.net.Uri
import org.json.JSONArray
import org.json.JSONObject
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.IOException
import java.security.MessageDigest

data class BilibiliDashTrack(
    val url: String,
    val backupUrls: List<String>,
    val id: Int,
    val bandwidth: Long,
    val codecId: Int,
    val codecs: String,
    val width: Int,
    val height: Int,
    val isAudio: Boolean,
)

data class BilibiliResolvedStream(
    val video: BilibiliDashTrack,
    val audio: BilibiliDashTrack?,
    val durationMs: Long,
    val page: BilibiliPageInfo? = null,
)

data class BilibiliPageInfo(
    val page: Int,
    val cid: String,
    val title: String,
    val durationMs: Long,
)

data class BilibiliPageCollection(
    val aid: String,
    val bvid: String,
    val title: String,
    val pages: List<BilibiliPageInfo>,
)

class BilibiliResolverException(
    val category: String,
    message: String,
    val apiCode: Int? = null,
    val httpStatus: Int? = null,
) : RuntimeException(message)

object BilibiliStreamResolver {
    private const val API_HOST = "api.bilibili.com"
    private const val BACKUP_HOST = "upos-sz-mirrorcoso1.bilivideo.com"
    private const val WBI_KEY_TTL_MS = 10 * 60 * 1000L
    private val mixinKeyEncTab = intArrayOf(
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
        27, 43, 5, 49, 33, 9, 19, 29, 7, 39, 13, 42, 20, 37, 34, 14,
        4, 17, 48, 22, 30, 11, 24, 28, 55, 54, 51, 56, 1, 21, 44, 12,
        25, 16, 36, 38, 40, 6, 52, 62, 26, 0, 41, 57, 63, 60, 61, 59,
    )

    @Volatile
    private var cachedWbiKey: String? = null

    @Volatile
    private var cachedWbiKeyExpiresAt = 0L

    fun isBilibiliPageUrl(url: String): Boolean {
        if (!isBilibiliUrl(url)) return false
        val parsed = runCatching { Uri.parse(url) }.getOrNull() ?: return false
        val host = parsed.host.orEmpty().lowercase().trimEnd('.')
        val path = parsed.path.orEmpty()
        if (path.substringBefore('?').lowercase().endsWith(".m4s")) return false
        return extractIdentity(url) != null || host == "b23.tv" || host.endsWith(".b23.tv") || host == "bili2233.cn" || host.endsWith(".bili2233.cn") || path.startsWith("/s/")
    }

    fun resolvePage(
        url: String,
        headers: Map<String, String> = emptyMap(),
        client: OkHttpClient = OkHttpClient(),
        maximumQualityId: Int? = null,
        pageNumber: Int? = null,
    ): BilibiliResolvedStream {
        val normalizedUrl = normalizePageUrl(url, headers, client)
        val identity = extractIdentity(normalizedUrl) ?: error("未识别 B 站视频链接")
        val requestHeaders = prepareBilibiliHeaders(normalizedUrl, headers, enabled = true)
        val pageCollection = resolvePages(normalizedUrl, headers, client)
        val aid = pageCollection.aid
        val requestedPage = pageNumber ?: Uri.parse(normalizedUrl).getQueryParameter("p")?.toIntOrNull() ?: 1
        val page = pageCollection.pages.firstOrNull { it.page == requestedPage }
            ?: error("B 站页面没有分 P $requestedPage")
        val cid = page.cid
        require(aid.isNotBlank() && cid.isNotBlank()) { "B 站视频缺少 aid 或 cid" }
        return resolveTrack(requestHeaders, client, aid, page, maximumQualityId)
    }

    fun resolvePages(
        url: String,
        headers: Map<String, String> = emptyMap(),
        client: OkHttpClient = OkHttpClient(),
    ): BilibiliPageCollection {
        val normalizedUrl = normalizePageUrl(url, headers, client)
        val identity = extractIdentity(normalizedUrl) ?: error("未识别 B 站视频链接")
        val requestHeaders = prepareBilibiliHeaders(normalizedUrl, headers, enabled = true)
        val viewParams = linkedMapOf<String, String>()
        identity.bvid?.let { viewParams["bvid"] = it }
        identity.aid?.let { viewParams["aid"] = it }
        val view = fetchJson(client, buildApiUrl("/x/web-interface/view", viewParams), requestHeaders)
        val data = view.getJSONObject("data")
        val aid = data.optString("aid").ifBlank { identity.aid.orEmpty() }
        val bvid = data.optString("bvid").ifBlank { identity.bvid.orEmpty() }
        val rawPages = data.optJSONArray("pages")
        val pageItems = buildList {
            if (rawPages != null) {
                for (index in 0 until rawPages.length()) {
                    val item = rawPages.optJSONObject(index) ?: continue
                    val cid = item.optString("cid")
                    if (cid.isBlank()) continue
                    add(BilibiliPageInfo(item.optInt("page", index + 1), cid, item.optString("part"), item.optLong("duration") * 1000))
                }
            }
            if (isEmpty() && data.optString("cid").isNotBlank()) {
                add(BilibiliPageInfo(1, data.optString("cid"), data.optString("title"), data.optLong("duration") * 1000))
            }
        }
        require(aid.isNotBlank() && pageItems.isNotEmpty()) { "B 站视频缺少 aid 或 cid" }
        return BilibiliPageCollection(aid, bvid, data.optString("title"), pageItems)
    }

    private fun normalizePageUrl(url: String, headers: Map<String, String>, client: OkHttpClient): String {
        if (extractIdentity(url) != null) return url
        val requestUrl = prepareBilibiliUrl(url, enabled = true)
        val requestHeaders = prepareBilibiliHeaders(requestUrl, headers, enabled = true)
        val builder = Request.Builder().url(requestUrl)
        requestHeaders.forEach { (name, value) -> if (value.isNotBlank()) builder.header(name, value) }
        throttleBilibiliRequest(requestUrl)
        return client.newCall(builder.build()).execute().use { response ->
            if (!response.isSuccessful) error("B 站短链接跳转失败 HTTP ${response.code}")
            response.request.url.toString()
        }
    }

    private fun resolveTrack(
        requestHeaders: Map<String, String>,
        client: OkHttpClient,
        aid: String,
        page: BilibiliPageInfo,
        maximumQualityId: Int?,
    ): BilibiliResolvedStream {
        val cid = page.cid

        val wbiKey = loadWbiKey(client, requestHeaders)
        val playParams = linkedMapOf(
            "avid" to aid,
            "cid" to cid,
            "fnval" to "4048",
            "fnver" to "0",
            "fourk" to "1",
            "from_client" to "BROWSER",
            "otype" to "json",
            "qn" to "0",
            "support_multi_audio" to "true",
            "wts" to (System.currentTimeMillis() / 1000).toString(),
        )
        if (requestHeaders.none { (name, value) -> name.equals("Cookie", ignoreCase = true) && value.isNotBlank() }) {
            playParams["try_look"] = "1"
        }
        val unsignedQuery = buildQuery(playParams)
        val signedQuery = "$unsignedQuery&w_rid=${md5Hex(unsignedQuery + wbiKey)}"
        val play = fetchJson(client, buildApiUrl("/x/player/wbi/playurl", signedQuery), requestHeaders)
        val playData = play.optJSONObject("data") ?: error("B 站未返回播放数据")
        val dash = playData.optJSONObject("dash") ?: error("B 站未返回 DASH M4S 轨道")
        val videos = parseTracks(dash.optJSONArray("video"), isAudio = false)
        val audios = parseTracks(dash.optJSONArray("audio"), isAudio = true)
        val selectedVideo = chooseVideo(videos, maximumQualityId) ?: error("B 站未返回符合画质要求的视频轨道")
        val selectedAudio = audios.maxWithOrNull(compareBy<BilibiliDashTrack> { it.bandwidth }.thenBy { it.id })
        val durationMs = when {
            playData.has("timelength") -> playData.optLong("timelength")
            playData.has("duration") -> playData.optLong("duration") * 1000
            else -> 0L
        }
        return BilibiliResolvedStream(selectedVideo, selectedAudio, durationMs, page)
    }

    private fun extractIdentity(url: String): BilibiliIdentity? {
        val path = runCatching { Uri.parse(url).path.orEmpty() }.getOrDefault("")
        val bvid = Regex("(?i)(BV[0-9A-Za-z]+)").find(path)?.value
        val aid = Regex("(?i)(?:^|/)av(\\d+)").find(path)?.groupValues?.getOrNull(1)
        return if (bvid.isNullOrBlank() && aid.isNullOrBlank()) null else BilibiliIdentity(bvid, aid)
    }

    private fun loadWbiKey(client: OkHttpClient, headers: Map<String, String>): String {
        val now = System.currentTimeMillis()
        cachedWbiKey?.let { key ->
            if (cachedWbiKeyExpiresAt > now) return key
        }
        val navUrl = buildApiUrl("/x/web-interface/nav", emptyMap())
        val nav = fetchJson(client, navUrl, headers, allowAnonymous = true)
        val wbiImage = nav.getJSONObject("data").getJSONObject("wbi_img")
        val imgKey = extractImageKey(wbiImage.getString("img_url"))
        val subKey = extractImageKey(wbiImage.getString("sub_url"))
        val rawKey = imgKey + subKey
        require(rawKey.length > mixinKeyEncTab.maxOrNull()!!) { "B 站 WBI key 无效" }
        val key = buildString(32) { mixinKeyEncTab.take(32).forEach { append(rawKey[it]) } }
        cachedWbiKey = key
        cachedWbiKeyExpiresAt = now + WBI_KEY_TTL_MS
        return key
    }

    private fun extractImageKey(url: String): String =
        url.substringAfterLast('/').substringBeforeLast('.')

    private fun parseTracks(array: JSONArray?, isAudio: Boolean): List<BilibiliDashTrack> {
        if (array == null) return emptyList()
        return buildList {
            for (index in 0 until array.length()) {
                val item = array.optJSONObject(index) ?: continue
                val baseUrl = item.optString("base_url").ifBlank { item.optString("baseUrl") }
                if (baseUrl.isBlank()) continue
                val backups = item.optJSONArray("backup_url") ?: item.optJSONArray("backupUrl")
                val sourceUrls = buildList {
                    add(baseUrl)
                    if (backups != null) {
                        for (backupIndex in 0 until backups.length()) {
                            val backup = backups.optString(backupIndex)
                            if (backup.isNotBlank()) add(backup)
                        }
                    }
                }
                val preferredUrl = sourceUrls.firstOrNull { !hasExplicitPort(it) } ?: sourceUrls.first()
                val selectedUrl = replacePcdnHost(preferredUrl)
                val backupUrls = sourceUrls.filter { it != preferredUrl }.map(::replacePcdnHost)
                add(
                    BilibiliDashTrack(
                        url = selectedUrl,
                        backupUrls = backupUrls,
                        id = item.optInt("id"),
                        bandwidth = item.optLong("bandwidth"),
                        codecId = item.optInt("codecid"),
                        codecs = item.optString("codecs"),
                        width = item.optInt("width"),
                        height = item.optInt("height"),
                        isAudio = isAudio,
                    ),
                )
            }
        }
    }

    private fun chooseVideo(tracks: List<BilibiliDashTrack>, maximumQualityId: Int? = null): BilibiliDashTrack? = tracks
        .filter { maximumQualityId == null || it.id <= maximumQualityId }
        .maxWithOrNull(
        compareBy<BilibiliDashTrack> { codecPriority(it.codecId) }
            .thenBy { it.id }
            .thenBy { it.bandwidth },
    )

    private fun codecPriority(codecId: Int): Int = when (codecId) {
        7 -> 3
        12 -> 2
        13 -> 1
        else -> 0
    }

    private fun hasExplicitPort(url: String): Boolean = runCatching { Uri.parse(url).port != -1 }.getOrDefault(false)

    private fun replacePcdnHost(url: String): String = runCatching {
        val parsed = Uri.parse(url)
        if (parsed.port == -1) url else parsed.buildUpon().authority(BACKUP_HOST).build().toString()
    }.getOrDefault(url)

    private fun fetchJson(
        client: OkHttpClient,
        url: String,
        headers: Map<String, String>,
        allowAnonymous: Boolean = false,
    ): JSONObject {
        var lastError: Throwable? = null
        repeat(3) { attempt ->
            try {
                val builder = Request.Builder().url(url)
                headers.forEach { (name, value) -> if (value.isNotBlank()) builder.header(name, value) }
                throttleBilibiliRequest(url)
                client.newCall(builder.build()).execute().use { response ->
                    if (!response.isSuccessful) {
                        val category = when (response.code) {
                            401, 403 -> "auth"
                            429 -> "rate_limit"
                            else -> "http"
                        }
                        throw BilibiliResolverException(category, "B 站请求失败 HTTP ${response.code}", httpStatus = response.code)
                    }
                    val body = response.body?.string().orEmpty()
                    val json = JSONObject(body)
                    val code = json.optInt("code")
                    if (code != 0 && !(allowAnonymous && code == -101)) {
                        val category = if (code == -101) "auth" else "api"
                        throw BilibiliResolverException(category, "B 站接口错误 $code：${json.optString("message")}", apiCode = code)
                    }
                    return json
                }
            } catch (exc: BilibiliResolverException) {
                throw exc
            } catch (exc: IOException) {
                lastError = exc
            }
            if (attempt < 2) Thread.sleep(minOf(8000L, 750L shl attempt))
        }
        throw BilibiliResolverException("network", "B 站网络请求失败",).also { it.initCause(lastError) }
    }

    private fun buildApiUrl(path: String, params: Map<String, String>): String =
        buildApiUrl(path, buildQuery(params))

    private fun buildApiUrl(path: String, query: String): String =
        "https://$API_HOST$path${if (query.isBlank()) "" else "?$query"}"

    private fun buildQuery(params: Map<String, String>): String = params.toSortedMap().entries.joinToString("&") { (key, value) ->
        "${Uri.encode(key)}=${Uri.encode(value.replace(Regex("[!'()*]"), ""))}"
    }

    private fun md5Hex(value: String): String = MessageDigest.getInstance("MD5")
        .digest(value.toByteArray(Charsets.UTF_8))
        .joinToString("") { byte -> "%02x".format(byte.toInt() and 0xff) }

    private data class BilibiliIdentity(val bvid: String?, val aid: String?)
}
