package com.dai2010.m3u8down.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.documentfile.provider.DocumentFile
import com.dai2010.m3u8down.download.DownloadManager
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun HomeScreen() {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var screen by rememberSaveable { mutableStateOf("home") }
    var url by rememberSaveable { mutableStateOf("") }
    var referer by rememberSaveable { mutableStateOf("") }
    var streamAdFilterEnabled by rememberSaveable { mutableStateOf(false) }
    var streamKeywords by rememberSaveable { mutableStateOf("adjump\nad\nbanner") }
    var downloadAdFilterEnabled by rememberSaveable { mutableStateOf(false) }
    var downloadKeywords by rememberSaveable { mutableStateOf("adjump\nad\nbanner") }
    var outputName by rememberSaveable { mutableStateOf("video.mp4") }
    var threadText by rememberSaveable { mutableStateOf("8") }
    var downloadTreeUri by rememberSaveable { mutableStateOf("") }
    var status by rememberSaveable { mutableStateOf("等待操作") }
    var progress by rememberSaveable { mutableStateOf(0f) }

    val directoryLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
            downloadTreeUri = uri.toString()
        }
    }

    when (screen) {
        "stream" -> StreamScreen(
            url = url,
            onUrlChange = { url = it },
            referer = referer,
            onRefererChange = { referer = it },
            adFilterEnabled = streamAdFilterEnabled,
            onAdFilterEnabledChange = { streamAdFilterEnabled = it },
            keywords = streamKeywords,
            onKeywordsChange = { streamKeywords = it },
            onPlay = { screen = "player" },
            onBack = { screen = "home" },
        )
        "download" -> DownloadScreen(
            url = url,
            onUrlChange = { url = it },
            referer = referer,
            onRefererChange = { referer = it },
            adFilterEnabled = downloadAdFilterEnabled,
            onAdFilterEnabledChange = { downloadAdFilterEnabled = it },
            keywords = downloadKeywords,
            onKeywordsChange = { downloadKeywords = it },
            outputName = outputName,
            onOutputNameChange = { outputName = it },
            threadText = threadText,
            onThreadTextChange = { value -> threadText = value.filter { it.isDigit() }.take(2) },
            savePath = currentSavePath(context, downloadTreeUri),
            status = status,
            progress = progress,
            onChooseSavePath = { directoryLauncher.launch(null) },
            onBack = { screen = "home" },
            onDownload = {
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
                        val filterWords = if (downloadAdFilterEnabled) downloadKeywords.lines().filter { it.isNotBlank() } else emptyList()
                        finalOutput.parentFile?.mkdirs()
                        manager.download(url, finalOutput, cache, headers, filterWords, threads).collect { update ->
                            status = update.message
                            progress = if (update.total == 0) 0f else update.done.toFloat() / update.total.toFloat()
                        }
                        if (downloadTreeUri.isNotBlank()) {
                            copyToTree(context, finalOutput, Uri.parse(downloadTreeUri), fileName)
                            finalOutput.delete()
                            status = "已保存到选择的目录：$fileName"
                        }
                    } catch (exc: Exception) {
                        status = "失败：${exc.message ?: exc.javaClass.simpleName}"
                    }
                }
            },
        )
        "player" -> PlayerScreen(
            url = url,
            referer = referer,
            adFilterEnabled = streamAdFilterEnabled,
            keywords = streamKeywords.lines().filter { it.isNotBlank() },
            onBack = { screen = "stream" },
        )
        else -> DirectoryScreen(onStream = { screen = "stream" }, onDownload = { screen = "download" })
    }
}

@Composable
private fun DirectoryScreen(onStream: () -> Unit, onDownload: () -> Unit) {
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(padding)
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(18.dp),
        ) {
            Text("m3u8 Downloader", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text("选择要做的事情", color = MaterialTheme.colorScheme.onSurfaceVariant)
            EntryCard(title = "流播", description = "直接播放 m3u8，可按需开启去广告过滤。", icon = Icons.Default.PlayArrow, onClick = onStream)
            EntryCard(title = "下载", description = "保存为 MP4，可按需开启去广告过滤。", icon = Icons.Default.Download, onClick = onDownload)
        }
    }
}

@Composable
private fun EntryCard(title: String, description: String, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    ElevatedCard(
        onClick = onClick,
        colors = CardDefaults.elevatedCardColors(containerColor = MaterialTheme.colorScheme.surface),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(modifier = Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) {
                Icon(icon, contentDescription = null, modifier = Modifier.padding(12.dp).size(30.dp), tint = MaterialTheme.colorScheme.onPrimaryContainer)
            }
            Spacer(Modifier.width(16.dp))
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                Text(description, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun StreamScreen(
    url: String,
    onUrlChange: (String) -> Unit,
    referer: String,
    onRefererChange: (String) -> Unit,
    adFilterEnabled: Boolean,
    onAdFilterEnabledChange: (Boolean) -> Unit,
    keywords: String,
    onKeywordsChange: (String) -> Unit,
    onPlay: () -> Unit,
    onBack: () -> Unit,
) {
    FormScreen(title = "流播", onBack = onBack) {
        LabeledField("m3u8 地址") { OutlinedTextField(value = url, onValueChange = onUrlChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("Referer，可留空") { OutlinedTextField(value = referer, onValueChange = onRefererChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        FilterSwitch(adFilterEnabled, onAdFilterEnabledChange)
        if (adFilterEnabled) {
            LabeledField("过滤关键词，每行一个") { OutlinedTextField(value = keywords, onValueChange = onKeywordsChange, minLines = 3, modifier = Modifier.fillMaxWidth()) }
        }
        Button(onClick = onPlay, enabled = url.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.PlayArrow, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("开始播放")
        }
    }
}

@Composable
private fun DownloadScreen(
    url: String,
    onUrlChange: (String) -> Unit,
    referer: String,
    onRefererChange: (String) -> Unit,
    adFilterEnabled: Boolean,
    onAdFilterEnabledChange: (Boolean) -> Unit,
    keywords: String,
    onKeywordsChange: (String) -> Unit,
    outputName: String,
    onOutputNameChange: (String) -> Unit,
    threadText: String,
    onThreadTextChange: (String) -> Unit,
    savePath: String,
    status: String,
    progress: Float,
    onChooseSavePath: () -> Unit,
    onDownload: () -> Unit,
    onBack: () -> Unit,
) {
    FormScreen(title = "下载", onBack = onBack) {
        LabeledField("m3u8 地址") { OutlinedTextField(value = url, onValueChange = onUrlChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("Referer，可留空") { OutlinedTextField(value = referer, onValueChange = onRefererChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("输出文件名") { OutlinedTextField(value = outputName, onValueChange = onOutputNameChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("并发线程数") {
            OutlinedTextField(
                value = threadText,
                onValueChange = onThreadTextChange,
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
            )
        }
        LabeledField("保存目录") {
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(value = savePath, onValueChange = {}, readOnly = true, modifier = Modifier.weight(1f))
                Spacer(Modifier.width(8.dp))
                Button(onClick = onChooseSavePath) { Icon(Icons.Default.Folder, contentDescription = null) }
            }
        }
        FilterSwitch(adFilterEnabled, onAdFilterEnabledChange)
        if (adFilterEnabled) {
            LabeledField("过滤关键词，每行一个") { OutlinedTextField(value = keywords, onValueChange = onKeywordsChange, minLines = 3, modifier = Modifier.fillMaxWidth()) }
        }
        Button(onClick = onDownload, enabled = url.isNotBlank(), modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.Download, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("开始下载")
        }
        LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
        Text(status, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun FormScreen(title: String, onBack: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .background(MaterialTheme.colorScheme.background)
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "返回") }
                Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            }
            content()
        }
    }
}

@Composable
private fun LabeledField(label: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurface)
        content()
    }
}

@Composable
private fun FilterSwitch(enabled: Boolean, onEnabledChange: (Boolean) -> Unit) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(modifier = Modifier.weight(1f)) {
            Text("去广告过滤", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text("关闭后不使用关键词过滤", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = enabled, onCheckedChange = onEnabledChange)
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
