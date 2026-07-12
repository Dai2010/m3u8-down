package com.dai2010.m3u8down.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.compose.BackHandler
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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
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
import com.dai2010.m3u8down.config.DEFAULT_FILTER_KEYWORDS_TEXT
import com.dai2010.m3u8down.config.DownloadProfile
import com.dai2010.m3u8down.config.ProfileStore
import com.dai2010.m3u8down.config.ThemeMode
import com.dai2010.m3u8down.download.DownloadManager
import kotlinx.coroutines.launch
import java.io.File

data class DownloadItem(val id: Int, val url: String = "", val outputName: String = "video.mp4")

@Composable
fun HomeScreen(themeMode: ThemeMode, onThemeModeChange: (ThemeMode) -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var screen by rememberSaveable { mutableStateOf("home") }
    var url by rememberSaveable { mutableStateOf("") }
    var referer by rememberSaveable { mutableStateOf("") }
    var streamAdFilterEnabled by rememberSaveable { mutableStateOf(false) }
    var streamKeywords by rememberSaveable { mutableStateOf(DEFAULT_FILTER_KEYWORDS_TEXT) }
    var downloadAdFilterEnabled by rememberSaveable { mutableStateOf(false) }
    var downloadKeywords by rememberSaveable { mutableStateOf(DEFAULT_FILTER_KEYWORDS_TEXT) }
    var threadText by rememberSaveable { mutableStateOf("8") }
    var downloadTreeUri by rememberSaveable { mutableStateOf("") }
    var savePathLabel by rememberSaveable { mutableStateOf(currentSavePath(context, "")) }
    var status by rememberSaveable { mutableStateOf("等待操作") }
    var progress by rememberSaveable { mutableStateOf(0f) }
    var nextItemId by rememberSaveable { mutableIntStateOf(2) }
    val downloadItems = remember { mutableStateListOf(DownloadItem(1, outputName = "video-001.mp4")) }
    var profiles by remember { mutableStateOf(ProfileStore.load(context)) }
    var selectedProfileIndex by rememberSaveable { mutableIntStateOf(0) }

    fun goBack() {
        screen = when (screen) {
            "player" -> "stream"
            "stream", "downloadMode", "profiles", "about" -> "home"
            "download" -> "downloadMode"
            else -> "home"
        }
    }

    BackHandler(enabled = screen != "home") { goBack() }

    fun applyProfile(profile: DownloadProfile) {
        downloadAdFilterEnabled = profile.adFilterEnabled
        downloadKeywords = profile.keywords
        threadText = profile.threads
        downloadTreeUri = profile.treeUri
        savePathLabel = if (profile.treeUri.isBlank()) currentSavePath(context, "") else profile.savePathLabel
    }

    val directoryLauncher = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        if (uri != null) {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
            downloadTreeUri = uri.toString()
            savePathLabel = Uri.parse(uri.toString()).lastPathSegment ?: uri.toString()
        }
    }

    when (screen) {
        "stream" -> StreamScreen(url, { url = it }, referer, { referer = it }, streamAdFilterEnabled, { streamAdFilterEnabled = it }, streamKeywords, { streamKeywords = it }, { screen = "player" }, { goBack() })
        "downloadMode" -> DownloadModeScreen(
            profiles = profiles,
            selectedIndex = selectedProfileIndex,
            onSelectedIndexChange = { selectedProfileIndex = it },
            onUseProfile = {
                profiles.getOrNull(selectedProfileIndex)?.let(::applyProfile)
                screen = "download"
            },
            onGuided = { screen = "download" },
            onBack = { goBack() },
        )
        "download" -> DownloadScreen(
            items = downloadItems,
            onItemChange = { item ->
                val itemIndex = downloadItems.indexOfFirst { it.id == item.id }
                if (itemIndex >= 0) downloadItems[itemIndex] = item
            },
            onAddItem = {
                downloadItems += DownloadItem(nextItemId, outputName = "video-${nextItemId.toString().padStart(3, '0')}.mp4")
                nextItemId += 1
            },
            onRemoveItem = { item -> if (downloadItems.size > 1) downloadItems.remove(item) },
            referer = referer,
            onRefererChange = { referer = it },
            adFilterEnabled = downloadAdFilterEnabled,
            onAdFilterEnabledChange = { downloadAdFilterEnabled = it },
            keywords = downloadKeywords,
            onKeywordsChange = { downloadKeywords = it },
            threadText = threadText,
            onThreadTextChange = { value -> threadText = value.filter { it.isDigit() }.take(2) },
            savePath = savePathLabel,
            status = status,
            progress = progress,
            onChooseSavePath = { directoryLauncher.launch(null) },
            onBack = { goBack() },
            onDownload = {
                scope.launch {
                    val tasks = downloadItems.filter { it.url.isNotBlank() }
                    if (tasks.isEmpty()) {
                        status = "请至少添加一个 m3u8 URL"
                        return@launch
                    }
                    try {
                        val manager = DownloadManager()
                        val headers = mapOf("Referer" to referer)
                        val batchCache = File(context.cacheDir, "segments/batch-${System.currentTimeMillis()}")
                        val threads = threadText.toIntOrNull()?.coerceIn(1, 64) ?: 8
                        val filterWords = if (downloadAdFilterEnabled) downloadKeywords.lines().filter { it.isNotBlank() } else emptyList()
                        try {
                            tasks.forEachIndexed { index, item ->
                                val fileName = item.outputName.ifBlank { "video-${(index + 1).toString().padStart(3, '0')}.mp4" }
                                val finalOutput = if (downloadTreeUri.isBlank()) File(context.getExternalFilesDir(null), fileName) else File(context.cacheDir, "exports/$fileName")
                                val taskCache = File(batchCache, "url-${index + 1}")
                                taskCache.deleteRecursively()
                                finalOutput.parentFile?.mkdirs()
                                manager.download(item.url, finalOutput, taskCache, headers, filterWords, threads).collect { update ->
                                    status = "${index + 1}/${tasks.size} ${update.message}"
                                    progress = if (update.total == 0) 0f else update.done.toFloat() / update.total.toFloat()
                                }
                                if (downloadTreeUri.isNotBlank()) {
                                    copyToTree(context, finalOutput, Uri.parse(downloadTreeUri), fileName)
                                    finalOutput.delete()
                                }
                            }
                        } finally {
                            batchCache.deleteRecursively()
                        }
                        status = "已完成 ${tasks.size} 个任务"
                    } catch (exc: Exception) {
                        status = "失败：${exc.message ?: exc.javaClass.simpleName}"
                    }
                }
            },
        )
        "profiles" -> ProfileScreen(
            profiles = profiles,
            savePath = savePathLabel,
            treeUri = downloadTreeUri,
            onChooseSavePath = { directoryLauncher.launch(null) },
            onProfilesChange = {
                val next = it.ifEmpty { listOf(DownloadProfile()) }
                profiles = next
                selectedProfileIndex = selectedProfileIndex.coerceIn(0, next.lastIndex)
                ProfileStore.save(context, next)
            },
            onBack = { goBack() },
        )
        "about" -> AboutScreen(onBack = { goBack() })
        "player" -> PlayerScreen(url, referer, streamAdFilterEnabled, streamKeywords.lines().filter { it.isNotBlank() }, { goBack() })
        else -> DirectoryScreen(
            themeMode = themeMode,
            onThemeModeChange = onThemeModeChange,
            onStream = { screen = "stream" },
            onDownload = { screen = "downloadMode" },
            onProfiles = { screen = "profiles" },
            onAbout = { screen = "about" },
        )
    }
}

@Composable
private fun DirectoryScreen(themeMode: ThemeMode, onThemeModeChange: (ThemeMode) -> Unit, onStream: () -> Unit, onDownload: () -> Unit, onProfiles: () -> Unit, onAbout: () -> Unit) {
    Scaffold { padding ->
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).padding(padding).padding(20.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(18.dp)) {
            Text("m3u8 Downloader", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text("选择要做的事情", color = MaterialTheme.colorScheme.onSurfaceVariant)
            EntryCard("流播", "直接播放 m3u8，可按需开启去广告过滤。", Icons.Default.PlayArrow, onStream)
            EntryCard("下载", "下载前选择已有配置，或进入引导式下载。", Icons.Default.Download, onDownload)
            EntryCard("管理配置", "新建、修改或删除过滤、线程、目录、标签和备注。", Icons.Default.Settings, onProfiles)
            EntryCard("关于", "作者主页、项目主页和协议。", Icons.Default.Info, onAbout)
            ThemeChooser(themeMode, onThemeModeChange)
        }
    }
}

@Composable
private fun EntryCard(title: String, description: String, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    ElevatedCard(onClick = onClick, colors = CardDefaults.elevatedCardColors(containerColor = MaterialTheme.colorScheme.surface), modifier = Modifier.fillMaxWidth()) {
        Row(Modifier.padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(color = MaterialTheme.colorScheme.primaryContainer, shape = MaterialTheme.shapes.medium) { Icon(icon, null, Modifier.padding(12.dp).size(30.dp), tint = MaterialTheme.colorScheme.onPrimaryContainer) }
            Spacer(Modifier.width(16.dp))
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
                Text(description, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}

@Composable
private fun DownloadModeScreen(profiles: List<DownloadProfile>, selectedIndex: Int, onSelectedIndexChange: (Int) -> Unit, onUseProfile: () -> Unit, onGuided: () -> Unit, onBack: () -> Unit) {
    FormScreen("选择下载方式", onBack) {
        Text("使用已有配置", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        profiles.forEachIndexed { index, profile ->
            ElevatedCard(onClick = { onSelectedIndexChange(index) }, modifier = Modifier.fillMaxWidth()) {
                Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                    RadioButton(selected = selectedIndex == index, onClick = { onSelectedIndexChange(index) })
                    Column {
                        Text(profileLabel(profile), fontWeight = FontWeight.SemiBold)
                        Text(profileSummary(profile), color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
        }
        Button(onClick = onUseProfile, enabled = profiles.isNotEmpty(), modifier = Modifier.fillMaxWidth()) { Text("使用所选配置") }
        TextButton(onClick = onGuided, modifier = Modifier.fillMaxWidth()) { Text("引导式下载") }
    }
}

@Composable
private fun StreamScreen(url: String, onUrlChange: (String) -> Unit, referer: String, onRefererChange: (String) -> Unit, adFilterEnabled: Boolean, onAdFilterEnabledChange: (Boolean) -> Unit, keywords: String, onKeywordsChange: (String) -> Unit, onPlay: () -> Unit, onBack: () -> Unit) {
    FormScreen("流播", onBack) {
        LabeledField("m3u8 地址") { OutlinedTextField(url, onUrlChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("Referer，可留空") { OutlinedTextField(referer, onRefererChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        FilterSwitch(adFilterEnabled, onAdFilterEnabledChange)
        if (adFilterEnabled) LabeledField("过滤关键词，每行一个") { OutlinedTextField(keywords, onKeywordsChange, minLines = 3, modifier = Modifier.fillMaxWidth()) }
        Button(onClick = onPlay, enabled = url.isNotBlank(), modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.PlayArrow, null); Spacer(Modifier.width(8.dp)); Text("开始播放") }
    }
}

@Composable
private fun DownloadScreen(items: List<DownloadItem>, onItemChange: (DownloadItem) -> Unit, onAddItem: () -> Unit, onRemoveItem: (DownloadItem) -> Unit, referer: String, onRefererChange: (String) -> Unit, adFilterEnabled: Boolean, onAdFilterEnabledChange: (Boolean) -> Unit, keywords: String, onKeywordsChange: (String) -> Unit, threadText: String, onThreadTextChange: (String) -> Unit, savePath: String, status: String, progress: Float, onChooseSavePath: () -> Unit, onDownload: () -> Unit, onBack: () -> Unit) {
    FormScreen("下载", onBack) {
        items.forEach { item ->
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(item.url, { onItemChange(item.copy(url = it)) }, label = { Text("m3u8 地址") }, singleLine = true, modifier = Modifier.weight(1f))
                    IconButton(onClick = { onRemoveItem(item) }) { Icon(Icons.Default.Delete, "删除") }
                }
                OutlinedTextField(item.outputName, { onItemChange(item.copy(outputName = it)) }, label = { Text("输出文件名") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(start = 28.dp))
            }
        }
        TextButton(onClick = onAddItem) { Icon(Icons.Default.Add, null); Spacer(Modifier.width(6.dp)); Text("添加 URL") }
        LabeledField("Referer，可留空") { OutlinedTextField(referer, onRefererChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("并发线程数") { OutlinedTextField(threadText, onThreadTextChange, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth()) }
        LabeledField("保存目录") { Row(verticalAlignment = Alignment.CenterVertically) { OutlinedTextField(savePath, {}, readOnly = true, modifier = Modifier.weight(1f)); Spacer(Modifier.width(8.dp)); Button(onClick = onChooseSavePath) { Icon(Icons.Default.Folder, null) } } }
        FilterSwitch(adFilterEnabled, onAdFilterEnabledChange)
        if (adFilterEnabled) LabeledField("过滤关键词，每行一个") { OutlinedTextField(keywords, onKeywordsChange, minLines = 3, modifier = Modifier.fillMaxWidth()) }
        Button(onClick = onDownload, modifier = Modifier.fillMaxWidth()) { Icon(Icons.Default.Download, null); Spacer(Modifier.width(8.dp)); Text("开始下载") }
        LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
        Text(status, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ProfileScreen(profiles: List<DownloadProfile>, savePath: String, treeUri: String, onChooseSavePath: () -> Unit, onProfilesChange: (List<DownloadProfile>) -> Unit, onBack: () -> Unit) {
    var selected by rememberSaveable { mutableIntStateOf(0) }
    var profile by remember(profiles, selected) { mutableStateOf(profiles.getOrElse(selected) { DownloadProfile() }) }
    FormScreen("管理配置", onBack) {
        profiles.forEachIndexed { index, item -> TextButton(onClick = { selected = index; profile = item }, modifier = Modifier.fillMaxWidth()) { Text(profileLabel(item)) } }
        Button(onClick = { val next = profiles + DownloadProfile(name = "配置 ${profiles.size + 1}"); onProfilesChange(next); selected = next.lastIndex; profile = next.last() }, modifier = Modifier.fillMaxWidth()) { Text("新增配置") }
        LabeledField("名称") { OutlinedTextField(profile.name, { profile = profile.copy(name = it) }, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("标签，逗号分隔") { OutlinedTextField(profile.tags.joinToString(", "), { profile = profile.copy(tags = it.split(",").map(String::trim).filter(String::isNotBlank)) }, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("备注") { OutlinedTextField(profile.note, { profile = profile.copy(note = it) }, minLines = 2, modifier = Modifier.fillMaxWidth()) }
        FilterSwitch(profile.adFilterEnabled) { profile = profile.copy(adFilterEnabled = it) }
        if (profile.adFilterEnabled) LabeledField("过滤关键词，每行一个") { OutlinedTextField(profile.keywords, { profile = profile.copy(keywords = it) }, minLines = 3, modifier = Modifier.fillMaxWidth()) }
        LabeledField("线程数") { OutlinedTextField(profile.threads, { profile = profile.copy(threads = it.filter(Char::isDigit).take(2)) }, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("保存目录") { Row(verticalAlignment = Alignment.CenterVertically) { OutlinedTextField(savePath, {}, readOnly = true, modifier = Modifier.weight(1f)); Spacer(Modifier.width(8.dp)); Button(onClick = onChooseSavePath) { Icon(Icons.Default.Folder, null) } } }
        Button(onClick = {
            val updated = profiles.toMutableList()
            val index = selected.coerceIn(0, updated.lastIndex)
            updated[index] = profile.copy(savePathLabel = savePath, treeUri = treeUri)
            onProfilesChange(updated)
        }, modifier = Modifier.fillMaxWidth()) { Text("保存当前配置") }
        TextButton(
            onClick = {
                if (profiles.size > 1) {
                    val updated = profiles.toMutableList()
                    val index = selected.coerceIn(0, updated.lastIndex)
                    updated.removeAt(index)
                    val next = updated.ifEmpty { listOf(DownloadProfile()) }
                    selected = index.coerceAtMost(next.lastIndex)
                    profile = next[selected]
                    onProfilesChange(next)
                }
            },
            enabled = profiles.size > 1,
            modifier = Modifier.fillMaxWidth(),
        ) { Icon(Icons.Default.Delete, null); Spacer(Modifier.width(6.dp)); Text("删除当前配置") }
    }
}

@Composable
private fun ThemeChooser(themeMode: ThemeMode, onThemeModeChange: (ThemeMode) -> Unit) {
    ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = MaterialTheme.colorScheme.surface), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("深色模式", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text("默认跟随系统，也可以手动指定。", color = MaterialTheme.colorScheme.onSurfaceVariant)
            ThemeMode.values().forEach { mode ->
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                    RadioButton(selected = themeMode == mode, onClick = { onThemeModeChange(mode) })
                    Text(themeLabel(mode))
                }
            }
        }
    }
}

private fun themeLabel(mode: ThemeMode): String = when (mode) {
    ThemeMode.SYSTEM -> "跟随系统"
    ThemeMode.LIGHT -> "浅色"
    ThemeMode.DARK -> "深色"
}

@Composable
private fun AboutScreen(onBack: () -> Unit) {
    FormScreen("关于", onBack) {
        Text("m3u8 Downloader", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("作者主页：https://github.com/Dai2010")
        Text("项目主页：https://github.com/Dai2010/m3u8-down")
        Text("协议：GNU General Public License v3.0")
    }
}

@Composable
private fun FormScreen(title: String, onBack: () -> Unit, content: @Composable ColumnScope.() -> Unit) {
    Scaffold { padding ->
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).padding(padding).verticalScroll(rememberScrollState()).padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }; Text(title, style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
            content()
            Spacer(Modifier.height(12.dp))
        }
    }
}

@Composable
private fun LabeledField(label: String, content: @Composable () -> Unit) { Column(verticalArrangement = Arrangement.spacedBy(6.dp)) { Text(label, style = MaterialTheme.typography.labelLarge); content() } }

@Composable
private fun FilterSwitch(enabled: Boolean, onEnabledChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) { Text("去广告过滤", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold); Text("关闭后不使用关键词过滤", color = MaterialTheme.colorScheme.onSurfaceVariant) }
        Switch(enabled, onEnabledChange)
    }
}

private fun profileLabel(profile: DownloadProfile): String = profile.name + if (profile.tags.isEmpty()) "" else " [${profile.tags.joinToString(", ")}]"

private fun profileSummary(profile: DownloadProfile): String = "备注：${profile.note.ifBlank { "无" }}\n过滤：${if (profile.adFilterEnabled) "开启" else "关闭"}；线程：${profile.threads}；目录：${profile.savePathLabel}"

private fun currentSavePath(context: Context, treeUri: String): String = if (treeUri.isBlank()) context.getExternalFilesDir(null)?.absolutePath.orEmpty() else Uri.parse(treeUri).lastPathSegment ?: treeUri

private fun copyToTree(context: Context, source: File, treeUri: Uri, fileName: String) {
    val directory = DocumentFile.fromTreeUri(context, treeUri) ?: error("selected folder is unavailable")
    directory.findFile(fileName)?.delete()
    val target = directory.createFile("video/mp4", fileName) ?: error("cannot create output file")
    context.contentResolver.openOutputStream(target.uri)?.use { output -> source.inputStream().use { input -> input.copyTo(output) } } ?: error("cannot open output file")
}
