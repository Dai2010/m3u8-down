package com.dai2010.m3u8down

import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.dai2010.m3u8down.config.ThemeMode
import com.dai2010.m3u8down.config.ThemeStore
import com.dai2010.m3u8down.ui.HomeScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            var themeMode by remember { mutableStateOf(ThemeStore.load(this)) }
            val isDark = when (themeMode) {
                ThemeMode.SYSTEM -> isSystemInDarkTheme()
                ThemeMode.LIGHT -> false
                ThemeMode.DARK -> true
            }
            val colorScheme = if (isDark) darkColorScheme(
                primary = Color(0xFF66DBB5),
                onPrimary = Color(0xFF00382C),
                primaryContainer = Color(0xFF005141),
                onPrimaryContainer = Color(0xFF85F8D0),
                secondary = Color(0xFFD8C57B),
                background = Color(0xFF111815),
                surface = Color(0xFF19211D),
                onSurface = Color(0xFFE0E8E2),
                onSurfaceVariant = Color(0xFFB8C9C0),
            ) else lightColorScheme(
                primary = Color(0xFF146C5A),
                onPrimary = Color.White,
                primaryContainer = Color(0xFFD8F4EA),
                onPrimaryContainer = Color(0xFF06382E),
                secondary = Color(0xFF6B5E2E),
                background = Color(0xFFF7F8F5),
                surface = Color.White,
                onSurface = Color(0xFF1E2421),
                onSurfaceVariant = Color(0xFF5C665F),
            )

            LaunchedEffect(isDark, colorScheme.background) {
                WindowCompat.setDecorFitsSystemWindows(window, true)
                window.statusBarColor = colorScheme.background.toArgb()
                window.navigationBarColor = colorScheme.background.toArgb()
                WindowInsetsControllerCompat(window, window.decorView).isAppearanceLightStatusBars = !isDark
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    WindowInsetsControllerCompat(window, window.decorView).isAppearanceLightNavigationBars = !isDark
                }
            }

            MaterialTheme(
                colorScheme = colorScheme,
            ) {
                Surface(color = colorScheme.background) {
                    HomeScreen(
                        themeMode = themeMode,
                        onThemeModeChange = { mode ->
                            themeMode = mode
                            ThemeStore.save(this, mode)
                        },
                    )
                }
            }
        }
    }
}
