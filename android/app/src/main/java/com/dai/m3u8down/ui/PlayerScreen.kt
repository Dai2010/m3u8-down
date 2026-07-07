package com.dai2010.m3u8down.ui

import androidx.annotation.OptIn
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.media3.common.MediaItem
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.hls.HlsMediaSource
import androidx.media3.ui.PlayerView

@OptIn(UnstableApi::class)
@Composable
fun PlayerScreen(url: String, referer: String, keywords: List<String>, onBack: () -> Unit) {
    val context = LocalContext.current
    var playbackPosition by rememberSaveable(url) { mutableLongStateOf(0L) }
    var shouldPlay by rememberSaveable(url) { mutableStateOf(true) }
    val player = remember(url, referer, keywords) {
        val httpFactory = DefaultHttpDataSource.Factory()
        if (referer.isNotBlank()) httpFactory.setDefaultRequestProperties(mapOf("Referer" to referer))
        val mediaSource = HlsMediaSource.Factory(httpFactory)
            .createMediaSource(MediaItem.fromUri(url))
        ExoPlayer.Builder(context).build().apply {
            setMediaSource(mediaSource)
            prepare()
            seekTo(playbackPosition)
            playWhenReady = shouldPlay
        }
    }
    DisposableEffect(player) {
        onDispose {
            playbackPosition = player.currentPosition
            shouldPlay = player.playWhenReady
            player.release()
        }
    }

    Column(modifier = Modifier.fillMaxSize()) {
        Button(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Back") }
        AndroidView(factory = { PlayerView(it).apply { this.player = player } }, modifier = Modifier.fillMaxSize())
    }
}
