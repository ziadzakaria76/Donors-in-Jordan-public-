package jo.tendermonitor.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

/**
 * The Word pack's header blue, so the app and the documents look like one
 * system rather than two.
 */
private val Navy = Color(0xFF1F4E79)
private val NavyLight = Color(0xFF4A7BAA)

private val LightColors = lightColorScheme(
    primary = Navy,
    secondary = NavyLight,
)

private val DarkColors = darkColorScheme(
    primary = NavyLight,
    secondary = Navy,
)

/**
 * Status colours, used everywhere a portal or a run is described.
 *
 * Deliberately NOT a red/green pair. Four states have to be distinguishable --
 * read, quiet-by-design, not-set-up and broken -- and collapsing the middle
 * two into "not green" is how a status table stops being read.
 */
object StatusColors {
    val ok = Color(0xFF2E7D32)
    val broken = Color(0xFFC62828)
    val unconfigured = Color(0xFF6A4C93)
    val noListing = Color(0xFF757575)
    val warning = Color(0xFFE65100)

    fun forPortalStatus(status: String): Color = when (status) {
        "ok" -> ok
        "unavailable" -> broken
        "unconfigured" -> unconfigured
        "no listing" -> noListing
        else -> warning
    }

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
    val colors = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context)
            else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColors
        else -> LightColors
    }
    MaterialTheme(colorScheme = colors, content = content)
}
