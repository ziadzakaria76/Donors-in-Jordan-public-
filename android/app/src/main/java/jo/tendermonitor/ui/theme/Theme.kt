package jo.tendermonitor.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

/**
 * The Word pack's header blue, so the app and the documents look like one
 * system rather than two.
 *
 * DYNAMIC COLOUR IS DELIBERATELY NOT USED. It was, and that made this comment
 * false on every phone that mattered: `dynamicLightColorScheme` derives the
 * whole palette from the user's wallpaper, so on Android 12 and later the
 * brand navy was dead code and the app came out lilac, or sage, or whatever
 * the wallpaper happened to be.
 *
 * That is a reasonable choice for a consumer app. It is the wrong one here.
 * These screens are read next to the .docx and .xlsx the same run produced,
 * and often in front of somebody else -- a report and an app that share a
 * colour read as one tool, while a report and an app that do not read as two
 * things that happen to have the same numbers in them.
 */
private val Navy = Color(0xFF1F4E79)

private val LightColors = lightColorScheme(
    primary = Navy,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD3E4F7),
    onPrimaryContainer = Color(0xFF001D36),
    secondary = Color(0xFF4A7BAA),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFDAE7F5),
    onSecondaryContainer = Color(0xFF0C1D2E),
    // A muted brass against the navy. Used sparingly -- it exists so that
    // "this needs a decision" has somewhere to go that is neither the calm of
    // the primary nor the alarm of the error colour.
    tertiary = Color(0xFF7A5900),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFDF9B),
    onTertiaryContainer = Color(0xFF261A00),
    error = Color(0xFFBA1A1A),
    onError = Color.White,
    errorContainer = Color(0xFFFFDAD6),
    onErrorContainer = Color(0xFF410002),
    background = Color(0xFFFCFCFF),
    onBackground = Color(0xFF1A1C1E),
    surface = Color(0xFFFCFCFF),
    onSurface = Color(0xFF1A1C1E),
    surfaceVariant = Color(0xFFDFE2EB),
    onSurfaceVariant = Color(0xFF43474E),
    outline = Color(0xFF73777F),
    outlineVariant = Color(0xFFC3C7CF),
)

private val DarkColors = darkColorScheme(
    // Navy itself is too dark to sit on a dark surface -- it reads as a hole
    // rather than an accent. The dark scheme keeps the hue and lifts it.
    primary = Color(0xFF9FCAF5),
    onPrimary = Color(0xFF003258),
    primaryContainer = Color(0xFF17497B),
    onPrimaryContainer = Color(0xFFD3E4F7),
    secondary = Color(0xFFB9C8DA),
    onSecondary = Color(0xFF24323F),
    secondaryContainer = Color(0xFF3A4856),
    onSecondaryContainer = Color(0xFFD5E4F7),
    tertiary = Color(0xFFEBC248),
    onTertiary = Color(0xFF3F2E00),
    tertiaryContainer = Color(0xFF5B4300),
    onTertiaryContainer = Color(0xFFFFDF9B),
    error = Color(0xFFFFB4AB),
    onError = Color(0xFF690005),
    errorContainer = Color(0xFF93000A),
    onErrorContainer = Color(0xFFFFDAD6),
    background = Color(0xFF1A1C1E),
    onBackground = Color(0xFFE2E2E6),
    surface = Color(0xFF1A1C1E),
    onSurface = Color(0xFFE2E2E6),
    surfaceVariant = Color(0xFF43474E),
    onSurfaceVariant = Color(0xFFC3C7CF),
    outline = Color(0xFF8D9199),
    outlineVariant = Color(0xFF43474E),
)

/**
 * Status colours, used everywhere a portal or a run is described.
 *
 * Deliberately NOT a red/green pair. Four states have to be distinguishable --
 * read, quiet-by-design, not-set-up and broken -- and collapsing the middle
 * two into "not green" is how a status table stops being read.
 *
 * EACH ONE HAS A DARK VARIANT, and that is not decoration. These are drawn as
 * text and as icons on a surface, and mid-tone greens and reds chosen to sit
 * on white go nearly invisible on a dark one -- worst of all as the tinted
 * chip in [StatusChip], which uses the same colour for the fill and the
 * label. A status table nobody can read at night is a status table nobody
 * reads.
 *
 * The properties resolve per composition, so a call site reads
 * `StatusColors.ok` exactly as before and gets the right one for the theme it
 * is being drawn in.
 */
object StatusColors {

    val ok: Color
        @Composable get() = pick(light = Color(0xFF2E7D32), dark = Color(0xFF7BD88F))

    val broken: Color
        @Composable get() = pick(light = Color(0xFFC62828), dark = Color(0xFFFF8A80))

    val unconfigured: Color
        @Composable get() = pick(light = Color(0xFF6A4C93), dark = Color(0xFFC7AEEF))

    val noListing: Color
        @Composable get() = pick(light = Color(0xFF757575), dark = Color(0xFFB0B4BA))

    val warning: Color
        @Composable get() = pick(light = Color(0xFFE65100), dark = Color(0xFFFFB77C))

    @Composable
    private fun pick(light: Color, dark: Color): Color =
        if (isSystemInDarkTheme()) dark else light

    @Composable
    fun forPortalStatus(status: String): Color = when (status) {
        "ok" -> ok
        "unavailable" -> broken
        "unconfigured" -> unconfigured
        "no listing" -> noListing
        else -> warning
    }

    @Composable
    fun forRunStatus(status: String): Color = when (status) {
        "ok" -> ok
        "quiet" -> noListing
        "partial" -> warning
        "action_needed" -> broken
        else -> warning
    }
}

@Composable
fun JordanTenderTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
