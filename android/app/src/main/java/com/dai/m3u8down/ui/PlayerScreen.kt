package com.dai2010.m3u8down.ui

import android.app.Activity
import android.net.Uri
import android.os.Build
import android.view.View
import android.view.WindowInsets
import android.view.WindowInsetsController
import android.view.WindowManager
import androidx.annotation.OptIn
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowCompat
import com.dai2010.m3u8down.media.MediaKind
import com.dai2010.m3u8down.media.MediaInfo
import com.dai2010.m3u8down.media.MediaTypeDetector
import com.dai2010.m3u8down.network.BilibiliResolvedStream
import com.dai2010.m3u8down.network.BilibiliFallbackDataSource
import com.dai2010.m3u8down.network.BilibiliResolverException
import com.dai2010.m3u8down.network.BilibiliStreamResolver
import com.dai2010.m3u8down.network.mediaRequestHeaders
import com.dai2010.m3u8down.network.prepareBilibiliUrl
import com.dai2010.m3u8down.parser.M3U8Parser
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.DataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.exoplayer.source.MergingMediaSource
import androidx.media3.ui.PlayerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.net.URI

@OptIn(UnstableApi::class)
@Composable
fun PlayerScreen(url: String, referer: String, adFilterEnabled: Boolean, keywords: List<String>, detectedInfo: MediaInfo?, bilibiliCompatEnabled: Boolean, bilibiliCookie: String, onPlaybackCompleted: () -> Unit, onBack: () -> Unit) {
    val context = LocalContext.current
    DisposableEffect(Unit) {
        val activity = context as? Activity
        val window = activity?.window
        val decor = window?.decorView
        val previousFlags = decor?.systemUiVisibility ?: 0
        window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        if (window != null) WindowCompat.setDecorFitsSystemWindows(window, false)
        decor?.systemUiVisibility = previousFlags or
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            window?.insetsController?.systemBarsBehavior = WindowInsetsController.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
            window?.insetsController?.hide(WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars())
        }
        onDispose {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                window?.insetsController?.show(WindowInsets.Type.statusBars() or WindowInsets.Type.navigationBars())
            }
            window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
            if (window != null) WindowCompat.setDecorFitsSystemWindows(window, true)
            decor?.systemUiVisibility = previousFlags
        }
    }
    var playbackPosition by rememberSaveable(url) { mutableLongStateOf(0L) }
    var shouldPlay by rememberSaveable(url) { mutableStateOf(true) }
    var mediaUri by rememberSaveable(url, adFilterEnabled, keywords, bilibiliCompatEnabled) { mutableStateOf("") }
    var mediaKind by rememberSaveable(url, adFilterEnabled, keywords, bilibiliCompatEnabled) { mutableStateOf(MediaKind.UNKNOWN.name) }
    var mediaContentType by rememberSaveable(url, adFilterEnabled, keywords, bilibiliCompatEnabled) { mutableStateOf("") }
    var status by rememberSaveable(url, adFilterEnabled, keywords, bilibiliCompatEnabled) { mutableStateOf("正在识别媒体类型") }
    var bilibiliStream by remember(url, referer, bilibiliCompatEnabled) { mutableStateOf<BilibiliResolvedStream?>(null) }

    LaunchedEffect(url, referer, adFilterEnabled, keywords, detectedInfo, bilibiliCompatEnabled) {
        try {
            val headers = mediaRequestHeaders(referer, url, bilibiliCompatEnabled, bilibiliCookie)
            mediaUri = ""
            bilibiliStream = null
            if (bilibiliCompatEnabled && BilibiliStreamResolver.isBilibiliPageUrl(url)) {
                status = "正在解析 B 站 DASH M4S 轨道"
                bilibiliStream = withContext(Dispatchers.IO) {
                    BilibiliStreamResolver.resolvePage(url, headers)
                }
                mediaKind = MediaKind.DASH.name
                mediaContentType = MimeTypes.APPLICATION_MPD
                status = ""
                return@LaunchedEffect
            }
            val info = detectedInfo ?: withContext(Dispatchers.IO) { MediaTypeDetector.detect(url, headers, bilibiliCompatEnabled = bilibiliCompatEnabled) }
            mediaKind = info.kind.name
            mediaContentType = info.contentType
            status = "已识别：${info.kind.displayName}"
            mediaUri = if (adFilterEnabled && info.kind == MediaKind.HLS) {
                status = "正在准备过滤播放列表"
                withContext(Dispatchers.IO) { createFilteredPlaylist(context.cacheDir, url, referer, keywords, bilibiliCompatEnabled, bilibiliCookie) }
            } else {
                prepareBilibiliUrl(url, bilibiliCompatEnabled)
            }
            status = ""
        } catch (exc: Exception) {
            status = if (exc is BilibiliResolverException && exc.category == "auth") {
                "B站鉴权失败：请填写有效 Cookie，当前 URL 可能已过期"
            } else {
                "播放准备失败：${exc.message ?: exc.javaClass.simpleName}"
            }
        }
    }

    val player = remember(mediaUri, bilibiliStream, referer, mediaKind, mediaContentType, bilibiliCompatEnabled, bilibiliCookie) {
        val stream = bilibiliStream
        if (mediaUri.isBlank() && stream == null) return@remember null
        val requestHeaders = mediaRequestHeaders(referer, url, bilibiliCompatEnabled, bilibiliCookie)
        val dataSourceFactory: DataSource.Factory = if (stream != null) {
            BilibiliFallbackDataSource.Factory(
                requestHeaders,
                buildMap {
                    put(stream.video.url, stream.video.backupUrls)
                    stream.audio?.let { put(it.url, it.backupUrls) }
                },
            )
        } else {
            val httpFactory = DefaultHttpDataSource.Factory()
            httpFactory.setDefaultRequestProperties(requestHeaders)
            DefaultDataSource.Factory(context, httpFactory)
        }
        val mediaSourceFactory = DefaultMediaSourceFactory(dataSourceFactory)
        ExoPlayer.Builder(context).build().apply {
            if (stream != null) {
                val videoItem = MediaItem.Builder()
                    .setUri(stream.video.url)
                    .setMimeType(MimeTypes.VIDEO_MP4)
                    .build()
                val videoSource = mediaSourceFactory.createMediaSource(videoItem)
                val audio = stream.audio
                if (audio == null) {
                    setMediaSource(videoSource)
                } else {
                    val audioItem = MediaItem.Builder()
                        .setUri(audio.url)
                        .setMimeType(MimeTypes.AUDIO_MP4)
                        .build()
                    val audioSource = mediaSourceFactory.createMediaSource(audioItem)
                    setMediaSource(MergingMediaSource(videoSource, audioSource))
                }
            } else {
                val kind = runCatching { MediaKind.valueOf(mediaKind) }.getOrDefault(MediaKind.UNKNOWN)
                val item = MediaItem.Builder()
                    .setUri(mediaUri)
                    .setMimeType(MediaInfo(kind, contentType = mediaContentType).mimeType(mediaUri))
                    .build()
                setMediaSource(mediaSourceFactory.createMediaSource(item))
            }
            prepare()
            seekTo(playbackPosition)
            playWhenReady = shouldPlay
        }
    }
    DisposableEffect(player) {
        onDispose {
            if (player != null) {
                playbackPosition = player.currentPosition
                shouldPlay = player.playWhenReady
                player.release()
            }
        }
    }
    val latestOnPlaybackCompleted = rememberUpdatedState(onPlaybackCompleted)
    DisposableEffect(player) {
        if (player == null) return@DisposableEffect onDispose { }
        var reported = false
        val listener = object : Player.Listener {
            override fun onPlaybackStateChanged(playbackState: Int) {
                if (!reported && playbackState == Player.STATE_ENDED) {
                    reported = true
                    latestOnPlaybackCompleted.value()
                }
            }
        }
        player.addListener(listener)
        onDispose { player.removeListener(listener) }
    }

    Box(modifier = Modifier.fillMaxSize()) {
        if (player == null) {
            Column(modifier = Modifier.align(Alignment.Center).padding(24.dp)) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                Text(status)
            }
        } else {
            AndroidView(
                factory = { PlayerView(it).apply { this.player = player } },
                modifier = Modifier.fillMaxSize(),
            )
        }
        Button(onClick = onBack, modifier = Modifier.align(Alignment.TopStart).padding(12.dp)) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
            Text("返回")
        }
    }
}

private fun createFilteredPlaylist(cacheDir: File, url: String, referer: String, keywords: List<String>, bilibiliCompatEnabled: Boolean, bilibiliCookie: String): String {
    val client = OkHttpClient()
    val requestUrl = prepareBilibiliUrl(url, bilibiliCompatEnabled)
    val headers = mediaRequestHeaders(referer, url, bilibiliCompatEnabled, bilibiliCookie)
    fun fetchText(target: String): String {
        val requestTarget = prepareBilibiliUrl(target, bilibiliCompatEnabled)
        val builder = Request.Builder().url(requestTarget)
        headers.forEach { (name, value) -> if (value.isNotBlank()) builder.header(name, value) }
        client.newCall(builder.build()).execute().use { response ->
            if (!response.isSuccessful) error("HTTP ${response.code}: $requestTarget")
            return response.body?.string() ?: error("empty response body: $requestTarget")
        }
    }

    val initialText = fetchText(requestUrl)
    val parsed = M3U8Parser.parse(initialText, requestUrl)
    val media = if (parsed.isMaster) {
        val variant = parsed.bestVariant() ?: error("master playlist has no variants")
        val variantUrl = prepareBilibiliUrl(variant.url, bilibiliCompatEnabled)
        variantUrl to fetchText(variantUrl)
    } else requestUrl to initialText
    val output = File(cacheDir, "filtered-stream.m3u8")
    output.writeText(filterMediaPlaylist(media.second, media.first, keywords, bilibiliCompatEnabled), Charsets.UTF_8)
    return output.toURI().toString()
}

private fun filterMediaPlaylist(content: String, baseUrl: String, keywords: List<String>, bilibiliCompatEnabled: Boolean): String {
    val lines = content.lineSequence().map { it.trim() }.filter { it.isNotEmpty() }.toList()
    require(lines.firstOrNull() == "#EXTM3U") { "playlist must start with #EXTM3U" }

    val output = mutableListOf<String>()
    val pendingSegmentTags = mutableListOf<String>()
    var pendingTitle = ""
    var hasEndList = false

    for (line in lines) {
        when {
            line == "#EXTM3U" -> output += line
            line == "#EXT-X-ENDLIST" -> hasEndList = true
            line.startsWith("#EXTINF:") -> {
                pendingSegmentTags += line
                pendingTitle = line.substringAfter(",", "").trim()
            }
            isSegmentScopedTag(line) -> pendingSegmentTags += rewriteTagUris(line, baseUrl, bilibiliCompatEnabled)
            line.startsWith("#") -> output += rewriteTagUris(line, baseUrl, bilibiliCompatEnabled)
            else -> {
                val absoluteUrl = prepareBilibiliUrl(M3U8Parser.resolveUrl(baseUrl, line), bilibiliCompatEnabled)
                val haystack = "$absoluteUrl\n$pendingTitle"
                val isAd = keywords.any { haystack.contains(it, ignoreCase = true) }
                if (!isAd) {
                    output += pendingSegmentTags
                    output += absoluteUrl
                }
                pendingSegmentTags.clear()
                pendingTitle = ""
            }
        }
    }

    if (hasEndList) output += "#EXT-X-ENDLIST"
    return output.joinToString("\n", postfix = "\n")
}

private fun isSegmentScopedTag(line: String): Boolean = line == "#EXT-X-DISCONTINUITY" ||
    line.startsWith("#EXT-X-BYTERANGE") ||
    line.startsWith("#EXT-X-PROGRAM-DATE-TIME") ||
    line.startsWith("#EXT-X-DATERANGE") ||
    line.startsWith("#EXT-X-GAP") ||
    line.startsWith("#EXT-X-MAP") ||
    line.startsWith("#EXT-X-PART") ||
    line.startsWith("#EXT-X-PRELOAD-HINT")

private fun rewriteTagUris(line: String, baseUrl: String, bilibiliCompatEnabled: Boolean): String =
    Regex("URI=\"([^\"]+)\"").replace(line) { match ->
        val uri = match.groupValues[1]
        val resolved = prepareBilibiliUrl(if (URI(uri).isAbsolute) uri else M3U8Parser.resolveUrl(baseUrl, uri), bilibiliCompatEnabled)
        "URI=\"$resolved\""
    }

private fun MediaKind.mimeType(): String? = when (this) {
    MediaKind.HLS -> MimeTypes.APPLICATION_M3U8
    MediaKind.DASH -> MimeTypes.APPLICATION_MPD
    MediaKind.SMOOTH -> MimeTypes.APPLICATION_SS
    MediaKind.RTSP, MediaKind.PROGRESSIVE, MediaKind.UNKNOWN -> null
}

private fun MediaInfo.mimeType(url: String): String? {
    val normalizedContentType = contentType.substringBefore(';').trim().lowercase()
    return when {
        normalizedContentType == "video/mp2t" -> MimeTypes.VIDEO_MP2T
        normalizedContentType == "video/mp4" || normalizedContentType == "application/mp4" || normalizedContentType == "application/fmp4" -> MimeTypes.VIDEO_MP4
        normalizedContentType == "audio/mp4" -> MimeTypes.AUDIO_MP4
        kind == MediaKind.PROGRESSIVE && Uri.parse(url).path.orEmpty().lowercase().endsWith(".ts") -> MimeTypes.VIDEO_MP2T
        kind == MediaKind.PROGRESSIVE && Uri.parse(url).path.orEmpty().lowercase().endsWith(".m4s") -> MimeTypes.VIDEO_MP4
        else -> kind.mimeType()
    }
}
