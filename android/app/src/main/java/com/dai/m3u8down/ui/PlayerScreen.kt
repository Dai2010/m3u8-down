package com.dai2010.m3u8down.ui

import android.app.Activity
import android.view.View
import androidx.annotation.OptIn
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.dai2010.m3u8down.parser.M3U8Parser
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.hls.HlsMediaSource
import androidx.media3.ui.PlayerView
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
        val decor = activity?.window?.decorView
        val previousFlags = decor?.systemUiVisibility ?: 0
        decor?.systemUiVisibility = previousFlags or
            View.SYSTEM_UI_FLAG_FULLSCREEN or
            View.SYSTEM_UI_FLAG_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY or
            View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN or
            View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION or
            View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        onDispose { decor?.systemUiVisibility = previousFlags }
    }
    var playbackPosition by rememberSaveable(url) { mutableLongStateOf(0L) }
    var shouldPlay by rememberSaveable(url) { mutableStateOf(true) }
    var mediaUri by rememberSaveable(url, adFilterEnabled, keywords) { mutableStateOf(if (adFilterEnabled) "" else url) }
    var status by rememberSaveable(url, adFilterEnabled, keywords) { mutableStateOf(if (adFilterEnabled) "正在准备过滤播放列表" else "") }

    LaunchedEffect(url, referer, adFilterEnabled, keywords) {
        if (!adFilterEnabled) {
            mediaUri = url
            status = ""
            return@LaunchedEffect
        }
        try {
            mediaUri = withContext(Dispatchers.IO) { createFilteredPlaylist(context.cacheDir, url, referer, keywords) }
            status = ""
        } catch (exc: Exception) {
            status = "过滤失败：${exc.message ?: exc.javaClass.simpleName}"
        }
    }

    val player = remember(mediaUri, referer) {
        if (mediaUri.isBlank()) return@remember null
        val httpFactory = DefaultHttpDataSource.Factory()
        if (referer.isNotBlank()) httpFactory.setDefaultRequestProperties(mapOf("Referer" to referer))
        val mediaSource = HlsMediaSource.Factory(httpFactory)
            .createMediaSource(MediaItem.fromUri(mediaUri))
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

    Column(modifier = Modifier.fillMaxSize()) {
        Button(onClick = onBack, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = null)
            Text("返回流播")
        }
        if (player == null) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            Text(status)
        } else {
            AndroidView(factory = { PlayerView(it).apply { this.player = player } }, modifier = Modifier.fillMaxSize())
        }
    }
}

private fun createFilteredPlaylist(cacheDir: File, url: String, referer: String, keywords: List<String>): String {
    val client = OkHttpClient()
    fun fetchText(target: String): String {
        val builder = Request.Builder().url(target)
        if (referer.isNotBlank()) builder.header("Referer", referer)
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
    line.startsWith("#EXT-X-PART") ||
    line.startsWith("#EXT-X-PRELOAD-HINT")

private fun rewriteTagUris(line: String, baseUrl: String): String =
    Regex("URI=\"([^\"]+)\"").replace(line) { match ->
        val uri = match.groupValues[1]
        val resolved = if (URI(uri).isAbsolute) uri else M3U8Parser.resolveUrl(baseUrl, uri)
        "URI=\"$resolved\""
    }
