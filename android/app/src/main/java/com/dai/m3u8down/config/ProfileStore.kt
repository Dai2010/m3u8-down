package com.dai2010.m3u8down.config

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

data class DownloadProfile(
    val name: String = "默认配置",
    val tags: List<String> = emptyList(),
    val note: String = "",
    val adFilterEnabled: Boolean = false,
    val keywords: String = "adjump\nad\nbanner",
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
                keywords = item.optString("keywords", "adjump\nad\nbanner"),
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
}
