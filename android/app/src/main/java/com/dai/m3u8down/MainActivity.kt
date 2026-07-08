package com.dai2010.m3u8down

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import com.dai2010.m3u8down.ui.HomeScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(
                colorScheme = lightColorScheme(
                    primary = Color(0xFF146C5A),
                    onPrimary = Color.White,
                    primaryContainer = Color(0xFFD8F4EA),
                    onPrimaryContainer = Color(0xFF06382E),
                    secondary = Color(0xFF6B5E2E),
                    background = Color(0xFFF7F8F5),
                    surface = Color.White,
                    onSurface = Color(0xFF1E2421),
                    onSurfaceVariant = Color(0xFF5C665F),
                ),
            ) {
                Surface {
                    HomeScreen()
                }
            }
        }
    }
}
