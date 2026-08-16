package com.gs3.marketingops.screenshot

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import com.gs3.marketingops.core.locale.Gs3Localized
import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.NumeralStyle
import com.gs3.marketingops.settings.data.AppSettings
import com.gs3.marketingops.settings.data.ThemeMode
import com.gs3.marketingops.settings.ui.SettingsScreen
import com.gs3.marketingops.ui.theme.Gs3Theme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
import java.time.LocalDate

/**
 * The both-language screenshot set.
 *
 * These run on the JVM under Robolectric with hardware-accelerated graphics, so
 * `./gradlew test` produces them on any machine and CI produces them on every
 * commit. That matters more than it sounds: a screenshot set that needs an
 * emulator is a screenshot set that gets taken once, at the end, when it is too
 * late for what it finds to be cheap.
 *
 * Everything that could vary between runs is pinned — the date, the window
 * size, the settings — so a changed pixel means changed code rather than a
 * changed afternoon.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [ROBOLECTRIC_SDK], qualifiers = "w411dp-h891dp-xhdpi")
class SettingsScreenshotTest {

    @get:Rule
    val composeRule = createComposeRule()

    /**
     * A fixed date, not `LocalDate.now()`.
     *
     * The screen renders a date, so with a real clock every screenshot would
     * differ from the last one by exactly the thing that is not being tested,
     * and the set would have to be regenerated daily until someone gave up on
     * it. 15 August 2026 is a Saturday — the first day of the working week
     * here, which makes it the right day to be looking at anyway.
     */
    private val fixedDate = LocalDate.of(2026, 8, 15)

    @Test
    fun `arabic, the language the app opens in`() {
        capture(
            name = "settings_arabic",
            settings = AppSettings(
                language = AppLanguage.ARABIC,
                numerals = NumeralStyle.WESTERN,
                showHijri = false,
                theme = ThemeMode.LIGHT,
            ),
        )
    }

    @Test
    fun `arabic with arabic-indic digits and the hijri date`() {
        capture(
            name = "settings_arabic_indic_hijri",
            settings = AppSettings(
                language = AppLanguage.ARABIC,
                numerals = NumeralStyle.ARABIC_INDIC,
                showHijri = true,
                theme = ThemeMode.LIGHT,
            ),
        )
    }

    @Test
    fun `english, which must lay out left-to-right`() {
        capture(
            name = "settings_english",
            settings = AppSettings(
                language = AppLanguage.ENGLISH,
                numerals = NumeralStyle.WESTERN,
                showHijri = false,
                theme = ThemeMode.LIGHT,
            ),
        )
    }

    @Test
    fun `arabic in dark mode`() {
        capture(
            name = "settings_arabic_dark",
            settings = AppSettings(
                language = AppLanguage.ARABIC,
                numerals = NumeralStyle.ARABIC_INDIC,
                showHijri = false,
                theme = ThemeMode.DARK,
            ),
            darkTheme = true,
        )
    }

    private fun capture(
        name: String,
        settings: AppSettings,
        darkTheme: Boolean = false,
    ) {
        composeRule.setContent {
            ScreenshotHost(darkTheme = darkTheme, language = settings.language) {
                SettingsScreen(
                    settings = settings,
                    onLanguageChange = {},
                    onNumeralsChange = {},
                    onShowHijriChange = {},
                    onThemeChange = {},
                    today = fixedDate,
                )
            }
        }

        val target = File("$SCREENSHOT_DIR/$name.png")
        composeRule.onRoot().captureRoboImage(target.path)

        // The capture is asserted, not assumed. `captureRoboImage` does nothing
        // at all unless Roborazzi is in record mode, and a test that silently
        // captures nothing still passes -- which would leave the milestone
        // reporting a screenshot set that does not exist.
        assertTrue("no screenshot written to $target", target.exists())
        assertTrue("screenshot $target is suspiciously small", target.length() > 10_000L)
    }
}

/**
 * The same wrapping order the real activity uses: localise, then theme.
 *
 * Deliberately not a shortcut that renders the screen directly. If the test
 * bypassed `Gs3Localized`, it would still produce Arabic-looking screenshots —
 * from the resources — while proving nothing about whether the layout actually
 * flips, which is the single thing these screenshots exist to catch.
 *
 * The opaque background matters too: `captureRoboImage` on a transparent root
 * produces a PNG whose light and dark variants are indistinguishable at a
 * glance, and a screenshot nobody can read is not a test.
 */
@Composable
private fun ScreenshotHost(
    darkTheme: Boolean,
    language: AppLanguage,
    content: @Composable () -> Unit,
) {
    Gs3Localized(language = language) {
        Gs3Theme(darkTheme = darkTheme) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(MaterialTheme.colorScheme.background),
            ) {
                content()
            }
        }
    }
}

/**
 * API 36. The app targets it, so the screenshots are taken against it — testing
 * at an older SDK would be testing a configuration no user will run.
 */
internal const val ROBOLECTRIC_SDK = 36

/**
 * Committed to the repository rather than left in `build/`.
 *
 * These are the artefact Milestone 1 is judged on, and keeping them in version
 * control means a layout that stops flipping for Arabic shows up as an image
 * diff in the pull request, where someone will see it -- instead of inside a
 * build directory that is deleted on the next clean.
 */
internal const val SCREENSHOT_DIR = "screenshots"
