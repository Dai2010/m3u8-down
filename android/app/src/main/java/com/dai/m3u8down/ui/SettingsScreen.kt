package com.dai2010.m3u8down.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.ListItem
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

@Composable
fun SettingsScreen(threadText: String, savePath: String) {
    Column(modifier = Modifier.fillMaxWidth()) {
        ListItem(headlineContent = { Text("Threads") }, supportingContent = { Text(threadText) })
        ListItem(headlineContent = { Text("Save path") }, supportingContent = { Text(savePath) })
    }
}
