package com.dai2010.m3u8down.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.dai2010.m3u8down.download.DownloadManager
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun HomeScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var url by remember { mutableStateOf("") }
    var referer by remember { mutableStateOf("") }
    var keywords by remember { mutableStateOf("adjump\nad\nbanner") }
    var outputName by remember { mutableStateOf("video.mp4") }
    var status by remember { mutableStateOf("Idle") }
    var progress by remember { mutableFloatStateOf(0f) }
    var screen by remember { mutableStateOf("home") }

    if (screen == "player") {
        PlayerScreen(url = url, referer = referer, keywords = keywords.lines().filter { it.isNotBlank() }, onBack = { screen = "home" })
        return
    }

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            OutlinedTextField(value = url, onValueChange = { url = it }, label = { Text("M3U8 URL") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(value = referer, onValueChange = { referer = it }, label = { Text("Referer") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(value = outputName, onValueChange = { outputName = it }, label = { Text("Output file") }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(value = keywords, onValueChange = { keywords = it }, label = { Text("Filter keywords") }, minLines = 3, modifier = Modifier.fillMaxWidth())

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        scope.launch {
                            val manager = DownloadManager()
                            val headers = mapOf("Referer" to referer)
                            val output = File(context.getExternalFilesDir(null), outputName.ifBlank { "video.mp4" })
                            val cache = File(context.cacheDir, "segments")
                            manager.download(url, output, cache, headers, keywords.lines().filter { it.isNotBlank() }).collect { update ->
                                status = update.message
                                progress = if (update.total == 0) 0f else update.done.toFloat() / update.total.toFloat()
                            }
                        }
                    },
                    enabled = url.isNotBlank(),
                ) {
                    Icon(Icons.Default.Download, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Download")
                }
                Button(onClick = { screen = "player" }, enabled = url.isNotBlank()) {
                    Icon(Icons.Default.PlayArrow, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("Play")
                }
                TextButton(onClick = { status = "Downloads are saved under app external files" }) {
                    Icon(Icons.Default.Settings, contentDescription = null)
                }
            }

            LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
            Text(status)
            Spacer(Modifier.height(8.dp))
            SettingsScreen(threadText = "8", savePath = context.getExternalFilesDir(null)?.absolutePath.orEmpty())
        }
    }
}
