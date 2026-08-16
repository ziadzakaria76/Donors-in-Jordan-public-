package com.gs3.marketingops.settings.data

import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.NumeralStyle

/**
 * How the app should be shown, as opposed to what it should show.
 *
 * [AppLanguage] and [NumeralStyle] come from `:domain` rather than being
 * redeclared here. They are already the vocabulary every formatter in the
 * domain speaks, and a second copy of the same two-value enum in the Android
 * layer would need converting at every call site — which is exactly where it
 * would eventually be converted wrongly.
 */
data class AppSettings(
    val language: AppLanguage = AppLanguage.ARABIC,
    val numerals: NumeralStyle = NumeralStyle.WESTERN,
    val showHijri: Boolean = false,
    val theme: ThemeMode = ThemeMode.FOLLOW_SYSTEM,
) {
    internal companion object {
        /**
         * The defaults, and each one is a recorded decision rather than a
         * preference:
         *
         *  - **Arabic on first launch** (A2). This is the team's working
         *    language; opening in English would be a daily small tax on
         *    everyone who uses it.
         *  - **Western digits** (C4). Chosen because prices are cross-checked
         *    against bank statements, contracts and the company's own website,
         *    all of which use them. Toggleable for anyone who prefers ٠-٩.
         *  - **Hijri off**. It is a companion to the Gregorian date, and
         *    contracts and government deadlines here are Gregorian.
         *  - **Theme follows the phone** (C3).
         */
        val Default = AppSettings()
    }
}

/** Light, dark, or whatever the phone is doing. */
enum class ThemeMode { FOLLOW_SYSTEM, LIGHT, DARK }
