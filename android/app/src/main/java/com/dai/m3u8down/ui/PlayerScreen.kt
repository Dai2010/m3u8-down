package com.dai2010.m3u8down.ui

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
import com.dai2010.m3u8down.filter.AdFilter
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

@OptIn(UnstableApi::class)
@Composable
fun PlayerScreen(url: String, referer: String, adFilterEnabled: Boolean, keywords: List<String>, onBack: () -> Unit) {
    val context = LocalContext.current
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

    val parsed = M3U8Parser.parse(fetchText(url), url)
    val media = if (parsed.isMaster) {
        val variant = parsed.bestVariant() ?: error("master playlist has no variants")
        M3U8Parser.parse(fetchText(variant.url), variant.url)
    } else parsed
    val filtered = AdFilter.filterPlaylist(media, keywords)
    val output = File(cacheDir, "filtered-stream.m3u8")
    output.writeText(M3U8Parser.serialize(filtered), Charsets.UTF_8)
    return output.toURI().toString()
}
