package com.dai2010.m3u8down.ui

import android.app.Activity
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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.view.WindowCompat
import com.dai2010.m3u8down.media.MediaKind
import com.dai2010.m3u8down.media.MediaTypeDetector
import com.dai2010.m3u8down.network.mediaRequestHeaders
import com.dai2010.m3u8down.parser.M3U8Parser
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.ui.PlayerView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File
import java.net.URI

@OptIn(UnstableApi::class)
@Composable
fun PlayerScreen(url: String, referer: String, adFilterEnabled: Boolean, keywords: List<String>, onBack: () -> Unit) {
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
    var mediaUri by rememberSaveable(url, adFilterEnabled, keywords) { mutableStateOf("") }
    var mediaKind by rememberSaveable(url, adFilterEnabled, keywords) { mutableStateOf(MediaKind.UNKNOWN.name) }
    var status by rememberSaveable(url, adFilterEnabled, keywords) { mutableStateOf("正在识别媒体类型") }

    LaunchedEffect(url, referer, adFilterEnabled, keywords) {
        try {
            val headers = mediaRequestHeaders(referer)
            val info = withContext(Dispatchers.IO) { MediaTypeDetector.detect(url, headers) }
            mediaKind = info.kind.name
            status = "已识别：${info.kind.displayName}"
            mediaUri = if (adFilterEnabled && info.kind == MediaKind.HLS) {
                status = "正在准备过滤播放列表"
                withContext(Dispatchers.IO) { createFilteredPlaylist(context.cacheDir, url, referer, keywords) }
            } else {
                url
            }
            status = ""
        } catch (exc: Exception) {
            status = "播放准备失败：${exc.message ?: exc.javaClass.simpleName}"
        }
    }

    val player = remember(mediaUri, referer, mediaKind) {
        if (mediaUri.isBlank()) return@remember null
        val httpFactory = DefaultHttpDataSource.Factory()
        httpFactory.setDefaultRequestProperties(mediaRequestHeaders(referer))
        val dataSourceFactory = DefaultDataSource.Factory(context, httpFactory)
        val kind = runCatching { MediaKind.valueOf(mediaKind) }.getOrDefault(MediaKind.UNKNOWN)
        val item = MediaItem.Builder().setUri(mediaUri).setMimeType(kind.mimeType()).build()
        val mediaSource = DefaultMediaSourceFactory(dataSourceFactory).createMediaSource(item)
        ExoPlayer.Builder(context).build().apply {
            setMediaSource(mediaSource)
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

private fun createFilteredPlaylist(cacheDir: File, url: String, referer: String, keywords: List<String>): String {
    val client = OkHttpClient()
    val headers = mediaRequestHeaders(referer)
    fun fetchText(target: String): String {
        val builder = Request.Builder().url(target)
        headers.forEach { (name, value) -> if (value.isNotBlank()) builder.header(name, value) }
        client.newCall(builder.build()).execute().use { response ->
            if (!response.isSuccessful) error("HTTP ${response.code}: $target")
            return response.body?.string() ?: error("empty response body: $target")
        }
    }

    val initialText = fetchText(url)
    val parsed = M3U8Parser.parse(initialText, url)
    val media = if (parsed.isMaster) {
        val variant = parsed.bestVariant() ?: error("master playlist has no variants")
        variant.url to fetchText(variant.url)
    } else url to initialText
    val output = File(cacheDir, "filtered-stream.m3u8")
    output.writeText(filterMediaPlaylist(media.second, media.first, keywords), Charsets.UTF_8)
    return output.toURI().toString()
}

private fun filterMediaPlaylist(content: String, baseUrl: String, keywords: List<String>): String {
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
            isSegmentScopedTag(line) -> pendingSegmentTags += rewriteTagUris(line, baseUrl)
            line.startsWith("#") -> output += rewriteTagUris(line, baseUrl)
            else -> {
                val absoluteUrl = M3U8Parser.resolveUrl(baseUrl, line)
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

private fun rewriteTagUris(line: String, baseUrl: String): String =
    Regex("URI=\"([^\"]+)\"").replace(line) { match ->
        val uri = match.groupValues[1]
        val resolved = if (URI(uri).isAbsolute) uri else M3U8Parser.resolveUrl(baseUrl, uri)
        "URI=\"$resolved\""
    }

private fun MediaKind.mimeType(): String? = when (this) {
    MediaKind.HLS -> MimeTypes.APPLICATION_M3U8
    MediaKind.DASH -> MimeTypes.APPLICATION_MPD
    MediaKind.SMOOTH -> MimeTypes.APPLICATION_SS
    MediaKind.RTSP, MediaKind.PROGRESSIVE, MediaKind.UNKNOWN -> null
}
