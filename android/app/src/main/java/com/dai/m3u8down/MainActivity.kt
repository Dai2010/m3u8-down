package com.dai2010.m3u8down

import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.darkColorScheme
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
import com.dai2010.m3u8down.config.normalizeHexColor
import com.dai2010.m3u8down.ui.HomeScreen
import kotlin.math.pow

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            var themeMode by remember { mutableStateOf(ThemeStore.load(this)) }
            var buttonColor by remember { mutableStateOf(ThemeStore.loadButtonColor(this)) }
            val isDark = when (themeMode) {
                ThemeMode.SYSTEM -> isSystemInDarkTheme()
                ThemeMode.LIGHT -> false
                ThemeMode.DARK -> true
            }
            val colorScheme = appColorScheme(isDark, buttonColor.toComposeColor())

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
                        buttonColor = buttonColor,
                        onThemeModeChange = { mode ->
                            themeMode = mode
                            ThemeStore.save(this, mode)
                        },
                        onButtonColorChange = { color ->
                            buttonColor = normalizeHexColor(color)
                            ThemeStore.saveButtonColor(this, buttonColor)
                        },
                    )
                }
            }
        }
    }
}

private fun appColorScheme(isDark: Boolean, customPrimaryColor: Color?): ColorScheme {
    return customPrimaryColor?.let { customAppColorScheme(isDark, it) } ?: defaultAppColorScheme(isDark)
}

private fun defaultAppColorScheme(isDark: Boolean): ColorScheme {
    return if (isDark) darkColorScheme(
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
}

private fun customAppColorScheme(isDark: Boolean, primaryColor: Color): ColorScheme {
    val accentColors = primaryColor.toAccentColors(isDark)
    return if (isDark) darkColorScheme(
        primary = accentColors.primary,
        onPrimary = accentColors.onPrimary,
        primaryContainer = accentColors.primaryContainer,
        onPrimaryContainer = accentColors.onPrimaryContainer,
        inversePrimary = accentColors.inversePrimary,
        secondary = accentColors.secondary,
        onSecondary = accentColors.onSecondary,
        secondaryContainer = accentColors.secondaryContainer,
        onSecondaryContainer = accentColors.onSecondaryContainer,
        tertiary = accentColors.tertiary,
        onTertiary = accentColors.onTertiary,
        tertiaryContainer = accentColors.tertiaryContainer,
        onTertiaryContainer = accentColors.onTertiaryContainer,
        background = Color(0xFF111815),
        onBackground = Color(0xFFE0E8E2),
        surface = Color(0xFF19211D),
        onSurface = Color(0xFFE0E8E2),
        surfaceVariant = accentColors.surfaceVariant,
        onSurfaceVariant = Color(0xFFB8C9C0),
        outline = accentColors.outline,
        outlineVariant = accentColors.outlineVariant,
        surfaceTint = accentColors.primary,
    ) else lightColorScheme(
        primary = accentColors.primary,
        onPrimary = accentColors.onPrimary,
        primaryContainer = accentColors.primaryContainer,
        onPrimaryContainer = accentColors.onPrimaryContainer,
        inversePrimary = accentColors.inversePrimary,
        secondary = accentColors.secondary,
        onSecondary = accentColors.onSecondary,
        secondaryContainer = accentColors.secondaryContainer,
        onSecondaryContainer = accentColors.onSecondaryContainer,
        tertiary = accentColors.tertiary,
        onTertiary = accentColors.onTertiary,
        tertiaryContainer = accentColors.tertiaryContainer,
        onTertiaryContainer = accentColors.onTertiaryContainer,
        background = Color(0xFFF7F8F5),
        onBackground = Color(0xFF1E2421),
        surface = Color.White,
        onSurface = Color(0xFF1E2421),
        surfaceVariant = accentColors.surfaceVariant,
        onSurfaceVariant = Color(0xFF5C665F),
        outline = accentColors.outline,
        outlineVariant = accentColors.outlineVariant,
        surfaceTint = accentColors.primary,
    )
}

private data class AccentColors(
    val primary: Color,
    val onPrimary: Color,
    val primaryContainer: Color,
    val onPrimaryContainer: Color,
    val inversePrimary: Color,
    val secondary: Color,
    val onSecondary: Color,
    val secondaryContainer: Color,
    val onSecondaryContainer: Color,
    val tertiary: Color,
    val onTertiary: Color,
    val tertiaryContainer: Color,
    val onTertiaryContainer: Color,
    val surfaceVariant: Color,
    val outline: Color,
    val outlineVariant: Color,
)

private fun Color.toAccentColors(isDark: Boolean): AccentColors {
    val secondaryColor = shiftHue(-18f).withSaturationMultiplier(0.64f)
    val tertiaryColor = shiftHue(42f).withSaturationMultiplier(0.72f)
    val primaryContainerColor = containerColor(isDark)
    val secondaryContainerColor = secondaryColor.containerColor(isDark)
    val tertiaryContainerColor = tertiaryColor.containerColor(isDark)
    val neutralSurfaceVariant = if (isDark) Color(0xFF202820) else Color(0xFFEEF2EE)
    val neutralOutline = if (isDark) Color(0xFF7F9087) else Color(0xFF77827B)

    return AccentColors(
        primary = this,
        onPrimary = contrastContentColor(),
        primaryContainer = primaryContainerColor,
        onPrimaryContainer = primaryContainerColor.contrastContentColor(),
        inversePrimary = if (isDark) containerColor(false) else containerColor(true),
        secondary = secondaryColor,
        onSecondary = secondaryColor.contrastContentColor(),
        secondaryContainer = secondaryContainerColor,
        onSecondaryContainer = secondaryContainerColor.contrastContentColor(),
        tertiary = tertiaryColor,
        onTertiary = tertiaryColor.contrastContentColor(),
        tertiaryContainer = tertiaryContainerColor,
        onTertiaryContainer = tertiaryContainerColor.contrastContentColor(),
        surfaceVariant = blendWith(neutralSurfaceVariant, if (isDark) 0.82f else 0.9f),
        outline = blendWith(neutralOutline, 0.72f),
        outlineVariant = blendWith(neutralSurfaceVariant, if (isDark) 0.7f else 0.84f),
    )
}

private fun Color.containerColor(isDark: Boolean): Color {
    val hsvValues = toHsvValues()
    hsvValues[1] = if (isDark) {
        (hsvValues[1] * 0.88f).coerceIn(0.18f, 0.9f)
    } else {
        (hsvValues[1] * 0.24f).coerceIn(0.08f, 0.34f)
    }
    hsvValues[2] = if (isDark) {
        (hsvValues[2] * 0.58f).coerceIn(0.22f, 0.48f)
    } else {
        0.95f
    }
    return Color(android.graphics.Color.HSVToColor(hsvValues))
}

private fun Color.shiftHue(degrees: Float): Color {
    val hsvValues = toHsvValues()
    hsvValues[0] = (hsvValues[0] + degrees + 360f) % 360f
    return Color(android.graphics.Color.HSVToColor(hsvValues))
}

private fun Color.withSaturationMultiplier(multiplier: Float): Color {
    val hsvValues = toHsvValues()
    hsvValues[1] = (hsvValues[1] * multiplier).coerceIn(0f, 1f)
    return Color(android.graphics.Color.HSVToColor(hsvValues))
}

private fun Color.toHsvValues(): FloatArray {
    val hsvValues = FloatArray(3)
    android.graphics.Color.colorToHSV(toArgb(), hsvValues)
    return hsvValues
}

private fun Color.blendWith(target: Color, amount: Float): Color {
    val clampedAmount = amount.coerceIn(0f, 1f)
    return Color(
        red = red + (target.red - red) * clampedAmount,
        green = green + (target.green - green) * clampedAmount,
        blue = blue + (target.blue - blue) * clampedAmount,
        alpha = alpha + (target.alpha - alpha) * clampedAmount,
    )
}

private fun Color.contrastContentColor(): Color {
    val darkContentColor = Color(0xFF111111)
    return if (contrastRatio(Color.White) >= contrastRatio(darkContentColor)) Color.White else darkContentColor
}

private fun Color.contrastRatio(contentColor: Color): Float {
    val backgroundLuminance = relativeLuminance()
    val contentLuminance = contentColor.relativeLuminance()
    val lighter = maxOf(backgroundLuminance, contentLuminance)
    val darker = minOf(backgroundLuminance, contentLuminance)
    return (lighter + 0.05f) / (darker + 0.05f)
}

private fun Color.relativeLuminance(): Float {
    val redLuminance = red.toLinearColorComponent()
    val greenLuminance = green.toLinearColorComponent()
    val blueLuminance = blue.toLinearColorComponent()
    return 0.2126f * redLuminance + 0.7152f * greenLuminance + 0.0722f * blueLuminance
}

private fun Float.toLinearColorComponent(): Float {
    return if (this <= 0.03928f) {
        this / 12.92f
    } else {
        ((this + 0.055f) / 1.055f).toDouble().pow(2.4).toFloat()
    }
}

private fun String.toComposeColor(): Color? {
    val normalized = normalizeHexColor(this)
    if (normalized.isBlank()) return null
    return Color(android.graphics.Color.parseColor(normalized))
}
