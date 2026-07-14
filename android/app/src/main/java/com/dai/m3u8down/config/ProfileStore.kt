package com.dai2010.m3u8down.config

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

const val DEFAULT_FILTER_KEYWORDS_TEXT = "/video/adjump/"

enum class ThemeMode(val value: String) {
    SYSTEM("system"),
    LIGHT("light"),
    DARK("dark");

    companion object {
        fun from(value: String?): ThemeMode = values().firstOrNull { it.value == value } ?: SYSTEM
    }
}

fun normalizeHexColor(value: String?): String {
    val raw = value.orEmpty().trim()
    if (raw.isBlank()) return ""
    val color = raw.removePrefix("#")
    return if (color.length == 6 && color.all { it in '0'..'9' || it in 'a'..'f' || it in 'A'..'F' }) "#${color.uppercase()}" else ""
}

data class DownloadProfile(
    val name: String = "默认配置",
    val tags: List<String> = emptyList(),
    val note: String = "",
    val adFilterEnabled: Boolean = false,
    val keywords: String = DEFAULT_FILTER_KEYWORDS_TEXT,
    val threads: String = "8",
    val savePathLabel: String = "应用目录",
    val treeUri: String = "",
)

object ProfileStore {
    private const val PREFS = "profiles"
    private const val KEY = "items"

    fun load(context: Context): List<DownloadProfile> {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY, null) ?: return listOf(DownloadProfile())
        val array = JSONArray(raw)
        return List(array.length()) { index ->
            val item = array.getJSONObject(index)
            DownloadProfile(
                name = item.optString("name", "默认配置"),
                tags = item.optJSONArray("tags")?.let { tags -> List(tags.length()) { tags.getString(it) } }.orEmpty(),
                note = item.optString("note", ""),
                adFilterEnabled = item.optBoolean("adFilterEnabled", false),
                keywords = normalizeKeywords(item.optString("keywords", DEFAULT_FILTER_KEYWORDS_TEXT)),
                threads = item.optString("threads", "8"),
                savePathLabel = item.optString("savePathLabel", "应用目录"),
                treeUri = item.optString("treeUri", ""),
            )
        }.ifEmpty { listOf(DownloadProfile()) }
    }

    fun save(context: Context, profiles: List<DownloadProfile>) {
        val array = JSONArray()
        profiles.forEach { profile ->
            array.put(JSONObject().apply {
                put("name", profile.name)
                put("tags", JSONArray(profile.tags))
                put("note", profile.note)
                put("adFilterEnabled", profile.adFilterEnabled)
                put("keywords", profile.keywords)
                put("threads", profile.threads)
                put("savePathLabel", profile.savePathLabel)
                put("treeUri", profile.treeUri)
            })
        }
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY, array.toString()).apply()
    }

    private fun normalizeKeywords(value: String): String {
        val lines = value.lines().map(String::trim).filter(String::isNotEmpty)
        return if (lines == listOf("adjump", "ad", "banner")) DEFAULT_FILTER_KEYWORDS_TEXT else value
    }
}

object ThemeStore {
    private const val PREFS = "appearance"
    private const val KEY_THEME = "theme"
    private const val KEY_BUTTON_COLOR = "buttonColor"

    fun load(context: Context): ThemeMode {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_THEME, ThemeMode.SYSTEM.value)
        return ThemeMode.from(raw)
    }

    fun loadButtonColor(context: Context): String {
        val raw = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).getString(KEY_BUTTON_COLOR, "")
        return normalizeHexColor(raw)
    }

    fun save(context: Context, mode: ThemeMode) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY_THEME, mode.value).apply()
    }

    fun saveButtonColor(context: Context, color: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE).edit().putString(KEY_BUTTON_COLOR, normalizeHexColor(color)).apply()
    }
}
