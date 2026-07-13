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
import androidx.compose.material3.FloatingActionButton
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
import com.dai2010.m3u8down.BuildConfig
import com.dai2010.m3u8down.config.DEFAULT_FILTER_KEYWORDS_TEXT
import com.dai2010.m3u8down.config.DownloadProfile
import com.dai2010.m3u8down.config.ProfileStore
import com.dai2010.m3u8down.config.ThemeMode
import com.dai2010.m3u8down.download.DownloadManager
import com.dai2010.m3u8down.network.mediaRequestHeaders
import kotlinx.coroutines.launch
import java.io.File

data class DownloadItem(val id: Int, val url: String = "", val outputName: String = "")

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
    val downloadItems = remember { mutableStateListOf(DownloadItem(1)) }
    var profiles by remember { mutableStateOf(ProfileStore.load(context)) }
    var selectedProfileIndex by rememberSaveable { mutableIntStateOf(0) }

    fun goBack() {
        screen = when (screen) {
            "player" -> "stream"
            "stream", "downloadMode", "settings" -> "home"
            "profiles", "about" -> "settings"
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
                downloadItems += DownloadItem(nextItemId)
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
                        status = "请至少添加一个媒体 URL"
                        return@launch
                    }
                    try {
                        val manager = DownloadManager()
                        val headers = mediaRequestHeaders(referer)
                        val batchCache = File(context.cacheDir, "segments/batch-${System.currentTimeMillis()}")
                        val threads = threadText.toIntOrNull()?.coerceIn(1, 64) ?: 8
                        val filterWords = if (downloadAdFilterEnabled) downloadKeywords.lines().filter { it.isNotBlank() } else emptyList()
                        try {
                            tasks.forEachIndexed { index, item ->
                                val fileName = item.outputName.ifBlank { outputNameFor(item.url, index) }
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
            onEditProfile = { profile ->
                downloadTreeUri = profile.treeUri
                savePathLabel = profile.savePathLabel.ifBlank { currentSavePath(context, profile.treeUri) }
            },
            onBack = { goBack() },
        )
        "settings" -> SettingsMenuScreen(
            themeMode = themeMode,
            onThemeModeChange = onThemeModeChange,
            onProfiles = { screen = "profiles" },
            onAbout = { screen = "about" },
            onBack = { goBack() },
        )
        "about" -> AboutScreen(onBack = { goBack() })
        "player" -> PlayerScreen(url, referer, streamAdFilterEnabled, streamKeywords.lines().filter { it.isNotBlank() }, { goBack() })
        else -> DirectoryScreen(
            onStream = { screen = "stream" },
            onDownload = { screen = "downloadMode" },
            onSettings = { screen = "settings" },
        )
    }
}

@Composable
private fun DirectoryScreen(onStream: () -> Unit, onDownload: () -> Unit, onSettings: () -> Unit) {
    Scaffold { padding ->
        Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).padding(padding).padding(20.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(18.dp)) {
            Text("m3u8 Downloader", style = MaterialTheme.typography.headlineMedium, fontWeight = FontWeight.Bold)
            Text("选择要做的事情", color = MaterialTheme.colorScheme.onSurfaceVariant)
            EntryCard("流播", "在线播放", Icons.Default.PlayArrow, onStream)
            EntryCard("下载", "保存视频", Icons.Default.Download, onDownload)
            EntryCard("设置", "配置、主题、关于", Icons.Default.Settings, onSettings)
        }
    }
}

@Composable
private fun SettingsMenuScreen(themeMode: ThemeMode, onThemeModeChange: (ThemeMode) -> Unit, onProfiles: () -> Unit, onAbout: () -> Unit, onBack: () -> Unit) {
    FormScreen("设置", onBack) {
        ThemeChooser(themeMode, onThemeModeChange)
        EntryCard("管理配置", "点击配置即可编辑", Icons.Default.Settings, onProfiles)
        EntryCard("关于", "版本与链接", Icons.Default.Info, onAbout)
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
        LabeledField("媒体地址") { OutlinedTextField(url, onUrlChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
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
                    OutlinedTextField(item.url, { onItemChange(item.copy(url = it)) }, label = { Text("媒体地址") }, singleLine = true, modifier = Modifier.weight(1f))
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
private fun ProfileScreen(
    profiles: List<DownloadProfile>,
    savePath: String,
    treeUri: String,
    onChooseSavePath: () -> Unit,
    onProfilesChange: (List<DownloadProfile>) -> Unit,
    onEditProfile: (DownloadProfile) -> Unit,
    onBack: () -> Unit,
) {
    var editingIndex by rememberSaveable { mutableStateOf<Int?>(null) }
    val safeProfiles = profiles.ifEmpty { listOf(DownloadProfile()) }

    if (editingIndex == null) {
        Scaffold(
            floatingActionButton = {
                FloatingActionButton(
                    onClick = {
                        val next = safeProfiles + DownloadProfile(name = "配置 ${safeProfiles.size + 1}")
                        onProfilesChange(next)
                        onEditProfile(next.last())
                        editingIndex = next.lastIndex
                    },
                ) { Icon(Icons.Default.Add, "新建配置") }
            },
        ) { padding ->
            Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).padding(padding).verticalScroll(rememberScrollState()).padding(18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "返回") }; Text("管理配置", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
                Text("点击配置即可编辑。", color = MaterialTheme.colorScheme.onSurfaceVariant)
                safeProfiles.forEachIndexed { index, item ->
                    ElevatedCard(
                        onClick = {
                            onEditProfile(item)
                            editingIndex = index
                        },
                        colors = CardDefaults.elevatedCardColors(containerColor = MaterialTheme.colorScheme.surface),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(profileLabel(item), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                            Text(profileSummary(item), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                Spacer(Modifier.height(72.dp))
            }
        }
        return
    }

    val index = editingIndex!!.coerceIn(0, safeProfiles.lastIndex)
    var profile by remember(index, safeProfiles) { mutableStateOf(safeProfiles[index]) }
    BackHandler { editingIndex = null }
    FormScreen("编辑配置", { editingIndex = null }) {
        LabeledField("名称") { OutlinedTextField(profile.name, { profile = profile.copy(name = it) }, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("标签，逗号分隔") { OutlinedTextField(profile.tags.joinToString(", "), { profile = profile.copy(tags = it.split(",").map(String::trim).filter(String::isNotBlank)) }, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("备注") { OutlinedTextField(profile.note, { profile = profile.copy(note = it) }, minLines = 2, modifier = Modifier.fillMaxWidth()) }
        FilterSwitch(profile.adFilterEnabled) { profile = profile.copy(adFilterEnabled = it) }
        if (profile.adFilterEnabled) LabeledField("过滤关键词，每行一个") { OutlinedTextField(profile.keywords, { profile = profile.copy(keywords = it) }, minLines = 3, modifier = Modifier.fillMaxWidth()) }
        LabeledField("线程数") { OutlinedTextField(profile.threads, { profile = profile.copy(threads = it.filter(Char::isDigit).take(2)) }, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        LabeledField("保存目录") { Row(verticalAlignment = Alignment.CenterVertically) { OutlinedTextField(savePath, {}, readOnly = true, modifier = Modifier.weight(1f)); Spacer(Modifier.width(8.dp)); Button(onClick = onChooseSavePath) { Icon(Icons.Default.Folder, null) } } }
        Button(onClick = {
            val updated = safeProfiles.toMutableList()
            updated[index] = profile.copy(savePathLabel = savePath, treeUri = treeUri)
            onProfilesChange(updated)
            editingIndex = null
        }, modifier = Modifier.fillMaxWidth()) { Text("保存配置") }
        TextButton(
            onClick = {
                if (safeProfiles.size > 1) {
                    val updated = safeProfiles.toMutableList()
                    updated.removeAt(index)
                    onProfilesChange(updated.ifEmpty { listOf(DownloadProfile()) })
                    editingIndex = null
                }
            },
            enabled = safeProfiles.size > 1,
            modifier = Modifier.fillMaxWidth(),
        ) { Icon(Icons.Default.Delete, null); Spacer(Modifier.width(6.dp)); Text("删除配置") }
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
    val context = LocalContext.current
    FormScreen("关于", onBack) {
        Text("m3u8 Downloader", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("版本：${BuildConfig.VERSION_NAME}")
        LinkButton("个人主页", "https://github.com/Dai2010", context)
        LinkButton("项目主页", "https://github.com/Dai2010/m3u8-down", context)
        Text("协议：GNU General Public License v3.0")
    }
}

@Composable
private fun LinkButton(label: String, url: String, context: Context) {
    TextButton(
        onClick = { runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) } },
        modifier = Modifier.fillMaxWidth(),
    ) { Text("$label：$url") }
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

private fun outputNameFor(url: String, index: Int): String {
    val rawExtension = Uri.parse(url).lastPathSegment
        ?.substringAfterLast('.', missingDelimiterValue = "")
        ?.takeIf { it.length in 2..5 }
        ?.lowercase()
    val extension = when (rawExtension) {
        "m3u", "m3u8", "mpd" -> "mp4"
        null, "" -> "mp4"
        else -> rawExtension
    }
    return "video-${(index + 1).toString().padStart(3, '0')}.$extension"
}

private fun copyToTree(context: Context, source: File, treeUri: Uri, fileName: String) {
    val directory = DocumentFile.fromTreeUri(context, treeUri) ?: error("selected folder is unavailable")
    directory.findFile(fileName)?.delete()
    val target = directory.createFile(mimeTypeFor(fileName), fileName) ?: error("cannot create output file")
    context.contentResolver.openOutputStream(target.uri)?.use { output -> source.inputStream().use { input -> input.copyTo(output) } } ?: error("cannot open output file")
}

private fun mimeTypeFor(fileName: String): String = when (fileName.substringAfterLast('.', "").lowercase()) {
    "mp4", "m4v" -> "video/mp4"
    "mkv" -> "video/x-matroska"
    "webm" -> "video/webm"
    "mov" -> "video/quicktime"
    "mp3" -> "audio/mpeg"
    "m4a" -> "audio/mp4"
    "aac" -> "audio/aac"
    "ogg", "opus" -> "audio/ogg"
    "wav" -> "audio/wav"
    else -> "application/octet-stream"
}
