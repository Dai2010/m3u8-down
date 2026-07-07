package com.dai2010.m3u8down.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.documentfile.provider.DocumentFile
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
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
    var url by rememberSaveable { mutableStateOf("") }
    var referer by rememberSaveable { mutableStateOf("") }
    var keywords by rememberSaveable { mutableStateOf("adjump\nad\nbanner") }
    var outputName by rememberSaveable { mutableStateOf("video.mp4") }
    var threadText by rememberSaveable { mutableStateOf("8") }
    var downloadTreeUri by rememberSaveable { mutableStateOf("") }
    var status by rememberSaveable { mutableStateOf("Idle") }
    var progress by rememberSaveable { mutableStateOf(0f) }
    var screen by rememberSaveable { mutableStateOf("home") }
    val directoryLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
            downloadTreeUri = uri.toString()
        }
    }

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
                            try {
                                val manager = DownloadManager()
                                val headers = mapOf("Referer" to referer)
                                val fileName = outputName.ifBlank { "video.mp4" }
                                val finalOutput = if (downloadTreeUri.isBlank()) {
                                    File(context.getExternalFilesDir(null), fileName)
                                } else {
                                    File(context.cacheDir, "exports/$fileName")
                                }
                                val cache = File(context.cacheDir, "segments")
                                val threads = threadText.toIntOrNull()?.coerceIn(1, 64) ?: 8
                                finalOutput.parentFile?.mkdirs()
                                manager.download(url, finalOutput, cache, headers, keywords.lines().filter { it.isNotBlank() }, threads).collect { update ->
                                    status = update.message
                                    progress = if (update.total == 0) 0f else update.done.toFloat() / update.total.toFloat()
                                }
                                if (downloadTreeUri.isNotBlank()) {
                                    copyToTree(context, finalOutput, Uri.parse(downloadTreeUri), fileName)
                                    finalOutput.delete()
                                    status = "Saved $fileName to selected folder"
                                }
                            } catch (exc: Exception) {
                                status = "Failed: ${exc.message ?: exc.javaClass.simpleName}"
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
                TextButton(onClick = { status = currentSavePath(context, downloadTreeUri) }) {
                    Icon(Icons.Default.Settings, contentDescription = null)
                }
            }

            LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
            Text(status)
            Spacer(Modifier.height(8.dp))
            SettingsScreen(
                threadText = threadText,
                onThreadTextChange = { threadText = it },
                savePath = currentSavePath(context, downloadTreeUri),
                onChooseSavePath = { directoryLauncher.launch(null) },
            )
        }
    }
}

private fun currentSavePath(context: Context, treeUri: String): String =
    if (treeUri.isBlank()) context.getExternalFilesDir(null)?.absolutePath.orEmpty() else Uri.parse(treeUri).lastPathSegment ?: treeUri

private fun copyToTree(context: Context, source: File, treeUri: Uri, fileName: String) {
    val directory = DocumentFile.fromTreeUri(context, treeUri) ?: error("selected folder is unavailable")
    directory.findFile(fileName)?.delete()
    val target = directory.createFile("video/mp4", fileName) ?: error("cannot create output file")
    context.contentResolver.openOutputStream(target.uri)?.use { output ->
        source.inputStream().use { input -> input.copyTo(output) }
    } ?: error("cannot open output file")
}
