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
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ElevatedCard
import androidx.compose.material3.FilterChip
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
import androidx.compose.runtime.LaunchedEffect
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.documentfile.provider.DocumentFile
import com.dai2010.m3u8down.BuildConfig
import com.dai2010.m3u8down.config.DEFAULT_FILTER_KEYWORDS_TEXT
import com.dai2010.m3u8down.config.DownloadProfile
import com.dai2010.m3u8down.config.ProfileStore
import com.dai2010.m3u8down.config.ThemeMode
import com.dai2010.m3u8down.config.normalizeHexColor
import com.dai2010.m3u8down.download.DownloadManager
import com.dai2010.m3u8down.media.MediaInfo
import com.dai2010.m3u8down.media.MediaKind
import com.dai2010.m3u8down.media.MediaTypeDetector
import com.dai2010.m3u8down.network.mediaRequestHeaders
import com.dai2010.m3u8down.network.prepareBilibiliUrl
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.File

data class DownloadItem(
    val id: Int,
    val url: String = "",
    val outputName: String = "",
    val detectedUrl: String = "",
    val mediaInfo: MediaInfo? = null,
    val detectionStatus: String = "等待输入链接",
)

private fun updateDownloadItem(items: MutableList<DownloadItem>, id: Int, transform: (DownloadItem) -> DownloadItem) {
    val index = items.indexOfFirst { it.id == id }
    if (index >= 0) items[index] = transform(items[index])
}

private val BUTTON_COLOR_PRESETS = listOf("#146C5A", "#2F80ED", "#7C3AED", "#D97706", "#DC2626", "#0F766E")

@Composable
fun HomeScreen(
    themeMode: ThemeMode,
    buttonColor: String,
    onThemeModeChange: (ThemeMode) -> Unit,
    onButtonColorChange: (String) -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var screen by rememberSaveable { mutableStateOf("home") }
    var url by rememberSaveable { mutableStateOf("") }
    var referer by rememberSaveable { mutableStateOf("") }
    var streamAdFilterEnabled by rememberSaveable { mutableStateOf(false) }
    var streamBilibiliCompatEnabled by rememberSaveable { mutableStateOf(false) }
    var streamKeywords by rememberSaveable { mutableStateOf(DEFAULT_FILTER_KEYWORDS_TEXT) }
    var downloadAdFilterEnabled by rememberSaveable { mutableStateOf(false) }
    var downloadBilibiliCompatEnabled by rememberSaveable { mutableStateOf(false) }
    var downloadKeywords by rememberSaveable { mutableStateOf(DEFAULT_FILTER_KEYWORDS_TEXT) }
    var threadText by rememberSaveable { mutableStateOf("8") }
    var downloadTreeUri by rememberSaveable { mutableStateOf("") }
    var savePathLabel by rememberSaveable { mutableStateOf(currentSavePath(context, "")) }
    var status by rememberSaveable { mutableStateOf("等待操作") }
    var progress by rememberSaveable { mutableStateOf(0f) }
    var previewUrl by rememberSaveable { mutableStateOf("") }
    var previewContent by rememberSaveable { mutableStateOf("") }
    var previewStatus by rememberSaveable { mutableStateOf("等待加载") }
    var previewReturnScreen by rememberSaveable { mutableStateOf("home") }
    var nextItemId by rememberSaveable { mutableIntStateOf(2) }
    val downloadItems = remember { mutableStateListOf(DownloadItem(1)) }
    var profiles by remember { mutableStateOf(ProfileStore.load(context)) }
    var selectedProfileIndex by rememberSaveable { mutableIntStateOf(0) }
    var streamMediaInfo by remember { mutableStateOf<MediaInfo?>(null) }
    var streamDetectedUrl by remember { mutableStateOf("") }
    var streamDetectionStatus by remember { mutableStateOf("输入链接后等待 5 秒自动探测") }

    LaunchedEffect(url, referer, streamBilibiliCompatEnabled) {
        streamMediaInfo = null
        streamDetectedUrl = ""
        if (url.isBlank()) {
            streamDetectionStatus = "输入链接后等待 5 秒自动探测"
            return@LaunchedEffect
        }
        streamDetectionStatus = "将在 5 秒后探测媒体类型"
        delay(5000)
        streamDetectionStatus = "正在探测媒体类型"
        val info = withContext(Dispatchers.IO) {
            MediaTypeDetector.detect(url, mediaRequestHeaders(referer, url, streamBilibiliCompatEnabled), bilibiliCompatEnabled = streamBilibiliCompatEnabled)
        }
        streamMediaInfo = info
        streamDetectedUrl = url
        streamDetectionStatus = if (info.kind == MediaKind.UNKNOWN) "未能识别媒体类型，请检查链接或请求头" else "已识别：${info.kind.displayName}"
    }

    val downloadDetectionKey = downloadItems.joinToString("|") { "${it.id}:${it.url}" }
    LaunchedEffect(downloadDetectionKey, referer, downloadBilibiliCompatEnabled) {
        delay(5000)
        downloadItems.filter { it.url.isNotBlank() && it.detectedUrl != it.url }.forEach { item ->
            updateDownloadItem(downloadItems, item.id) { it.copy(detectionStatus = "正在探测媒体类型") }
            val info = withContext(Dispatchers.IO) {
                MediaTypeDetector.detect(item.url, mediaRequestHeaders(referer, item.url, downloadBilibiliCompatEnabled), bilibiliCompatEnabled = downloadBilibiliCompatEnabled)
            }
            updateDownloadItem(downloadItems, item.id) {
                it.copy(
                    mediaInfo = info,
                    detectedUrl = item.url,
                    detectionStatus = if (info.kind == MediaKind.UNKNOWN) "未能识别媒体类型" else "已识别：${info.kind.displayName}",
                )
            }
        }
    }

    fun goBack() {
        screen = when (screen) {
            "player" -> "stream"
            "stream", "downloadMode", "settings" -> "home"
            "profiles", "about" -> "settings"
            "download" -> "downloadMode"
            "playlistPreview" -> previewReturnScreen
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

    fun previewPlaylist(targetUrl: String, returnScreen: String, detectedInfo: MediaInfo?, detectedUrl: String) {
        val target = targetUrl.trim()
        if (target.isBlank()) {
            status = "请先输入 m3u8 URL"
            return
        }
        if (target != detectedUrl || detectedInfo == null) {
            status = "请等待链接输入 5 秒后的媒体探测完成"
            return
        }
        if (detectedInfo.kind != MediaKind.HLS) {
            status = "当前是${detectedInfo.kind.displayName}，不支持 m3u8 列表预览"
            return
        }
        previewUrl = target
        previewContent = ""
        previewStatus = "正在加载 m3u8 列表全文"
        previewReturnScreen = returnScreen
        screen = "playlistPreview"
        val bilibiliCompat = if (returnScreen == "stream") streamBilibiliCompatEnabled else downloadBilibiliCompatEnabled
        scope.launch {
            try {
                previewContent = fetchPlaylistText(
                    prepareBilibiliUrl(target, bilibiliCompat),
                    mediaRequestHeaders(referer, target, bilibiliCompat),
                )
                previewStatus = "已加载 ${previewContent.lines().size} 行"
            } catch (exc: Exception) {
                previewStatus = "加载失败：${exc.message ?: exc.javaClass.simpleName}"
            }
        }
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
        "stream" -> StreamScreen(
            url,
            { url = it },
            referer,
            { referer = it },
            streamAdFilterEnabled,
            { streamAdFilterEnabled = it },
            streamBilibiliCompatEnabled,
            { streamBilibiliCompatEnabled = it },
            streamKeywords,
            { streamKeywords = it },
            streamDetectionStatus,
            streamMediaInfo,
            streamDetectedUrl,
            { screen = "player" },
            { previewPlaylist(url, "stream", streamMediaInfo, streamDetectedUrl) },
            { goBack() },
        )
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
                if (itemIndex >= 0) {
                    val previous = downloadItems[itemIndex]
                    downloadItems[itemIndex] = if (previous.url == item.url) item else item.copy(
                        detectedUrl = "",
                        mediaInfo = null,
                        detectionStatus = if (item.url.isBlank()) "等待输入链接" else "将在 5 秒后探测媒体类型",
                    )
                }
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
            bilibiliCompatEnabled = downloadBilibiliCompatEnabled,
            onBilibiliCompatEnabledChange = { downloadBilibiliCompatEnabled = it },
            keywords = downloadKeywords,
            onKeywordsChange = { downloadKeywords = it },
            threadText = threadText,
            onThreadTextChange = { value -> threadText = value.filter { it.isDigit() }.take(2) },
            savePath = savePathLabel,
            status = status,
            progress = progress,
            onChooseSavePath = { directoryLauncher.launch(null) },
            onBack = { goBack() },
            onPreview = { item -> previewPlaylist(item.url, "download", item.mediaInfo, item.detectedUrl) },
            onDownload = {
                scope.launch {
                    val tasks = downloadItems.filter { it.url.isNotBlank() }
                    if (tasks.isEmpty()) {
                        status = "请至少添加一个媒体 URL"
                        return@launch
                    }
                    if (tasks.any { it.detectedUrl != it.url || it.mediaInfo == null }) {
                        status = "请等待所有链接完成 5 秒后的媒体探测"
                        return@launch
                    }
                    if (tasks.any { it.mediaInfo?.kind == MediaKind.UNKNOWN }) {
                        status = "存在未识别的媒体链接，请检查链接或请求头"
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
                                manager.download(item.url, finalOutput, taskCache, headers, filterWords, threads, item.mediaInfo, downloadBilibiliCompatEnabled).collect { update ->
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
            buttonColor = buttonColor,
            onThemeModeChange = onThemeModeChange,
            onButtonColorChange = onButtonColorChange,
            onProfiles = { screen = "profiles" },
            onAbout = { screen = "about" },
            onBack = { goBack() },
        )
        "about" -> AboutScreen(onBack = { goBack() })
        "playlistPreview" -> PlaylistPreviewScreen(previewUrl, previewContent, previewStatus, { goBack() })
        "player" -> PlayerScreen(url, referer, streamAdFilterEnabled, streamKeywords.lines().filter { it.isNotBlank() }, streamMediaInfo, streamBilibiliCompatEnabled, { goBack() })
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
private fun SettingsMenuScreen(
    themeMode: ThemeMode,
    buttonColor: String,
    onThemeModeChange: (ThemeMode) -> Unit,
    onButtonColorChange: (String) -> Unit,
    onProfiles: () -> Unit,
    onAbout: () -> Unit,
    onBack: () -> Unit,
) {
    FormScreen("设置", onBack) {
        AppearanceChooser(themeMode, buttonColor, onThemeModeChange, onButtonColorChange)
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
private fun StreamScreen(url: String, onUrlChange: (String) -> Unit, referer: String, onRefererChange: (String) -> Unit, adFilterEnabled: Boolean, onAdFilterEnabledChange: (Boolean) -> Unit, bilibiliCompatEnabled: Boolean, onBilibiliCompatEnabledChange: (Boolean) -> Unit, keywords: String, onKeywordsChange: (String) -> Unit, detectionStatus: String, mediaInfo: MediaInfo?, detectedUrl: String, onPlay: () -> Unit, onPreview: () -> Unit, onBack: () -> Unit) {
    var advancedExpanded by rememberSaveable { mutableStateOf(false) }
    FormScreen("流播", onBack) {
        LabeledField("媒体地址") { OutlinedTextField(url, onUrlChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
        Text(detectionStatus, color = MaterialTheme.colorScheme.onSurfaceVariant)
        AdvancedToggle(advancedExpanded) { advancedExpanded = it }
        if (advancedExpanded) {
            LabeledField("Referer，可留空") { OutlinedTextField(referer, onRefererChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
            BilibiliCompatSwitch(bilibiliCompatEnabled, onBilibiliCompatEnabledChange)
            FilterSwitch(adFilterEnabled, onAdFilterEnabledChange)
            if (adFilterEnabled) LabeledField("过滤关键词，每行一个") { OutlinedTextField(keywords, onKeywordsChange, minLines = 3, modifier = Modifier.fillMaxWidth()) }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            val detected = detectedUrl == url && mediaInfo != null && mediaInfo.kind != MediaKind.UNKNOWN
            Button(onClick = onPlay, enabled = detected, modifier = Modifier.weight(1f)) { Icon(Icons.Default.PlayArrow, null); Spacer(Modifier.width(8.dp)); Text("开始播放") }
            TextButton(onClick = onPreview, enabled = detected && mediaInfo?.kind == MediaKind.HLS, modifier = Modifier.weight(1f)) { Text("预览 m3u8 列表") }
        }
    }
}

@Composable
private fun DownloadScreen(items: List<DownloadItem>, onItemChange: (DownloadItem) -> Unit, onAddItem: () -> Unit, onRemoveItem: (DownloadItem) -> Unit, referer: String, onRefererChange: (String) -> Unit, adFilterEnabled: Boolean, onAdFilterEnabledChange: (Boolean) -> Unit, bilibiliCompatEnabled: Boolean, onBilibiliCompatEnabledChange: (Boolean) -> Unit, keywords: String, onKeywordsChange: (String) -> Unit, threadText: String, onThreadTextChange: (String) -> Unit, savePath: String, status: String, progress: Float, onChooseSavePath: () -> Unit, onPreview: (DownloadItem) -> Unit, onDownload: () -> Unit, onBack: () -> Unit) {
    var advancedExpanded by rememberSaveable { mutableStateOf(false) }
    FormScreen("下载", onBack) {
        items.forEach { item ->
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(item.url, { onItemChange(item.copy(url = it)) }, label = { Text("媒体地址") }, singleLine = true, modifier = Modifier.weight(1f))
                    TextButton(onClick = { onPreview(item) }, enabled = item.detectedUrl == item.url && item.mediaInfo?.kind == MediaKind.HLS) { Text("预览") }
                    IconButton(onClick = { onRemoveItem(item) }) { Icon(Icons.Default.Delete, "删除") }
                }
                Text(item.detectionStatus, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(start = 28.dp))
                OutlinedTextField(item.outputName, { onItemChange(item.copy(outputName = it)) }, label = { Text("输出文件名") }, singleLine = true, modifier = Modifier.fillMaxWidth().padding(start = 28.dp))
            }
        }
        TextButton(onClick = onAddItem) { Icon(Icons.Default.Add, null); Spacer(Modifier.width(6.dp)); Text("添加 URL") }
        LabeledField("并发线程数") { OutlinedTextField(threadText, onThreadTextChange, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = Modifier.fillMaxWidth()) }
        LabeledField("保存目录") { Row(verticalAlignment = Alignment.CenterVertically) { OutlinedTextField(savePath, {}, readOnly = true, modifier = Modifier.weight(1f)); Spacer(Modifier.width(8.dp)); Button(onClick = onChooseSavePath) { Icon(Icons.Default.Folder, null) } } }
        AdvancedToggle(advancedExpanded) { advancedExpanded = it }
        if (advancedExpanded) {
            LabeledField("Referer，可留空") { OutlinedTextField(referer, onRefererChange, singleLine = true, modifier = Modifier.fillMaxWidth()) }
            BilibiliCompatSwitch(bilibiliCompatEnabled, onBilibiliCompatEnabledChange)
            FilterSwitch(adFilterEnabled, onAdFilterEnabledChange)
            if (adFilterEnabled) LabeledField("过滤关键词，每行一个") { OutlinedTextField(keywords, onKeywordsChange, minLines = 3, modifier = Modifier.fillMaxWidth()) }
        }
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
private fun AppearanceChooser(
    themeMode: ThemeMode,
    buttonColor: String,
    onThemeModeChange: (ThemeMode) -> Unit,
    onButtonColorChange: (String) -> Unit,
) {
    var colorText by rememberSaveable(buttonColor) { mutableStateOf(buttonColor) }
    ElevatedCard(colors = CardDefaults.elevatedCardColors(containerColor = MaterialTheme.colorScheme.surface), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("外观", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text("主题和按钮颜色压缩在这里。按钮色可留空使用默认。", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                ThemeMode.values().forEach { mode ->
                    FilterChip(selected = themeMode == mode, onClick = { onThemeModeChange(mode) }, label = { Text(themeLabel(mode)) })
                }
            }
            OutlinedTextField(
                value = colorText,
                onValueChange = { colorText = it.take(7) },
                label = { Text("按钮颜色 #RRGGBB") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                BUTTON_COLOR_PRESETS.forEach { preset ->
                    Button(
                        onClick = {
                            colorText = preset
                            onButtonColorChange(preset)
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = preset.toComposeColor() ?: MaterialTheme.colorScheme.primary),
                        modifier = Modifier.weight(1f),
                    ) { Text(" ") }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
                Button(onClick = { onButtonColorChange(colorText) }, modifier = Modifier.weight(1f)) { Text("应用颜色") }
                TextButton(
                    onClick = {
                        colorText = ""
                        onButtonColorChange("")
                    },
                    modifier = Modifier.weight(1f),
                ) { Text("恢复默认") }
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
private fun PlaylistPreviewScreen(url: String, content: String, status: String, onBack: () -> Unit) {
    FormScreen("m3u8 列表预览", onBack) {
        Text("完整全文", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Text(url, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(status, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Surface(
            color = if (MaterialTheme.colorScheme.background == Color(0xFFF7F8F5)) Color(0xFFFBF7EC) else Color(0xFF202820),
            shape = MaterialTheme.shapes.medium,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                text = content.ifBlank { "加载后会显示 m3u8 原文。" },
                color = if (MaterialTheme.colorScheme.background == Color(0xFFF7F8F5)) Color(0xFF26302B) else Color(0xFFE8EAD8),
                fontFamily = FontFamily.Monospace,
                modifier = Modifier.padding(14.dp),
            )
        }
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
private fun AdvancedToggle(expanded: Boolean, onExpandedChange: (Boolean) -> Unit) {
    TextButton(onClick = { onExpandedChange(!expanded) }, modifier = Modifier.fillMaxWidth()) {
        Text(if (expanded) "高级 ▲" else "高级 ▼")
    }
}

@Composable
private fun BilibiliCompatSwitch(enabled: Boolean, onEnabledChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text("开启B站兼容模式", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Text("B站链接会自动启用，也可手动开启", color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(enabled, onEnabledChange)
    }
}

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

private fun String.looksLikeM3uUrl(): Boolean {
    val path = runCatching { Uri.parse(this).path.orEmpty() }.getOrDefault("").lowercase()
    return path.endsWith(".m3u8") || path.endsWith(".m3u")
}

private suspend fun fetchPlaylistText(url: String, headers: Map<String, String>): String = withContext(Dispatchers.IO) {
    val request = Request.Builder().url(url).apply {
        headers.forEach { (key, value) -> if (value.isNotBlank()) addHeader(key, value) }
    }.build()
    OkHttpClient().newCall(request).execute().use { response ->
        if (!response.isSuccessful) error("HTTP ${response.code}")
        response.body?.string().orEmpty()
    }
}

private fun String.toComposeColor(): Color? {
    val normalized = normalizeHexColor(this)
    if (normalized.isBlank()) return null
    return runCatching { Color(android.graphics.Color.parseColor(normalized)) }.getOrNull()
}

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
    "mp4", "m4s", "m4v" -> "video/mp4"
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
