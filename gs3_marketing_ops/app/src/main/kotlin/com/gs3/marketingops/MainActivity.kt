package com.gs3.marketingops

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.gs3.marketingops.core.locale.Gs3Localized
import com.gs3.marketingops.settings.data.ThemeMode
import com.gs3.marketingops.settings.ui.SettingsViewModel
import com.gs3.marketingops.ui.Gs3App
import com.gs3.marketingops.ui.theme.Gs3Theme
import dagger.hilt.android.AndroidEntryPoint

/**
 * The single activity.
 *
 * `enableEdgeToEdge()` is called before `setContent`, from the first commit
 * rather than as a later polish pass. On API 36 the opt-out is gone — an app
 * targeting 36 is edge-to-edge whether it asks to be or not — so calling it
 * explicitly changes nothing about the result and everything about whether the
 * insets were thought through. Every screen below handles its own insets; see
 * `Gs3ScreenScaffold`.
 *
 * The order of the wrappers matters. `Gs3Localized` sits **outside**
 * `Gs3Theme`, because the theme's typography and the layout direction it lays
 * out against both depend on the language. Inverted, the first composition
 * after a language switch would lay Arabic out left-to-right.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    private val settingsViewModel: SettingsViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)

        setContent {
            val settings by settingsViewModel.settings.collectAsStateWithLifecycle()

            val darkTheme = when (settings.theme) {
                ThemeMode.FOLLOW_SYSTEM -> isSystemInDarkTheme()
                ThemeMode.LIGHT -> false
                ThemeMode.DARK -> true
            }

            Gs3Localized(language = settings.language) {
                Gs3Theme(darkTheme = darkTheme) {
                    Gs3App(
                        settings = settings,
                        onLanguageChange = settingsViewModel::setLanguage,
                        onNumeralsChange = settingsViewModel::setNumerals,
                        onShowHijriChange = settingsViewModel::setShowHijri,
                        onThemeChange = settingsViewModel::setTheme,
                    )
                }
            }
        }
    }
}
