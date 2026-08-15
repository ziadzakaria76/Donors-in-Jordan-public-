package com.gs3.marketingops.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

/**
 * Status colours that Material's scheme has no slot for.
 *
 * They travel in a composition local rather than a global, so a screenshot test
 * can render the dark palette without putting the device into dark mode.
 */
@Immutable
internal data class StatusColors(
    val success: Color,
    val warn: Color,
    val danger: Color,
)

internal val LocalStatusColors = staticCompositionLocalOf {
    StatusColors(success = Success, warn = Warn, danger = Danger)
}

private val LightColors = lightColorScheme(
    primary = Brass,
    onPrimary = Paper,
    primaryContainer = BrassSoft,
    onPrimaryContainer = Ink,
    secondary = Slate,
    onSecondary = Paper,
    secondaryContainer = Stone2,
    onSecondaryContainer = Ink2,
    tertiary = Ink3,
    onTertiary = Paper,
    background = Ivory,
    onBackground = Ink,
    surface = Paper,
    onSurface = Ink,
    surfaceVariant = Stone2,
    onSurfaceVariant = Slate,
    outline = Muted,
    outlineVariant = Stone,
    error = Danger,
    onError = Paper,
)

private val DarkColors = darkColorScheme(
    primary = Brass2,
    onPrimary = Ink,
    primaryContainer = BrassDeep,
    onPrimaryContainer = BrassSoft,
    secondary = Stone,
    onSecondary = Ink,
    secondaryContainer = Ink3,
    onSecondaryContainer = Stone2,
    tertiary = Stone2,
    onTertiary = Ink,
    background = Ink,
    onBackground = Stone2,
    surface = Ink2,
    onSurface = Stone2,
    surfaceVariant = Ink3,
    onSurfaceVariant = Stone,
    outline = Muted,
    outlineVariant = Ink3,
    error = DangerDark,
    onError = Ink,
)

/**
 * Deliberately **not** dynamic colour.
 *
 * Material You would repaint the app from the user's wallpaper, taking the
 * brass out of a brand the company already publishes on its website and its
 * brochure. A salesperson shows this screen to a client sitting beside them; it
 * needs to look like the company, not like their phone.
 */
@Composable
internal fun Gs3Theme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val statusColors = if (darkTheme) {
        StatusColors(success = SuccessDark, warn = WarnDark, danger = DangerDark)
    } else {
        StatusColors(success = Success, warn = Warn, danger = Danger)
    }

    CompositionLocalProvider(LocalStatusColors provides statusColors) {
        MaterialTheme(
            colorScheme = if (darkTheme) DarkColors else LightColors,
            typography = Gs3Typography,
            content = content,
        )
    }
}

/**
 * Reads the status palette, in the same shape Material uses for its own
 * (`MaterialTheme.colorScheme`), so the call site reads the same way.
 */
internal object Gs3Theme {
    val statusColors: StatusColors
        @Composable @ReadOnlyComposable get() = LocalStatusColors.current
}
