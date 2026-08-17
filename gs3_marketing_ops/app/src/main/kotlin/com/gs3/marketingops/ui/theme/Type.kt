package com.gs3.marketingops.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.LineHeightStyle
import androidx.compose.ui.unit.sp

/**
 * Typography, tuned for Arabic first.
 *
 * The company's website sets IBM Plex Sans Arabic. That font is **not** bundled
 * here, and the omission is deliberate rather than an oversight: the app must
 * build and run with no network, the font file is not in this repository, and a
 * downloadable-font provider would put a Play Services dependency and a runtime
 * network fetch into an app whose whole premise is that it works offline. The
 * platform's own Arabic face is used instead. When a licensed font file is
 * added to the repository this is the one file that changes.
 *
 * Two things here are about Arabic specifically, and neither is cosmetic:
 *
 *  - **Line height is generous.** Arabic ascenders and descenders travel
 *    further than Latin ones, and diacritics sit above them again. At
 *    Material's default line heights, «مؤهَّل» clips against the line above.
 *  - **`trim = None`.** Compose trims the first line's ascent and the last
 *    line's descent by default, which crops the very marks Arabic puts there.
 */

private val ArabicSafeLineHeight = LineHeightStyle(
    alignment = LineHeightStyle.Alignment.Center,
    trim = LineHeightStyle.Trim.None,
)

private fun gs3(
    size: Int,
    lineHeight: Int,
    weight: FontWeight = FontWeight.Normal,
    letterSpacing: Double = 0.0,
) = TextStyle(
    fontFamily = FontFamily.Default,
    fontWeight = weight,
    fontSize = size.sp,
    lineHeight = lineHeight.sp,
    letterSpacing = letterSpacing.sp,
    lineHeightStyle = ArabicSafeLineHeight,
)

internal val Gs3Typography = Typography(
    displayLarge = gs3(size = 52, lineHeight = 68, weight = FontWeight.SemiBold),
    displayMedium = gs3(size = 42, lineHeight = 56, weight = FontWeight.SemiBold),
    displaySmall = gs3(size = 34, lineHeight = 46, weight = FontWeight.SemiBold),
    headlineLarge = gs3(size = 30, lineHeight = 42, weight = FontWeight.SemiBold),
    headlineMedium = gs3(size = 26, lineHeight = 36, weight = FontWeight.SemiBold),
    headlineSmall = gs3(size = 22, lineHeight = 32, weight = FontWeight.Medium),
    titleLarge = gs3(size = 20, lineHeight = 30, weight = FontWeight.Medium),
    titleMedium = gs3(size = 17, lineHeight = 26, weight = FontWeight.Medium),
    titleSmall = gs3(size = 15, lineHeight = 24, weight = FontWeight.Medium),
    bodyLarge = gs3(size = 16, lineHeight = 26),
    bodyMedium = gs3(size = 15, lineHeight = 24),
    bodySmall = gs3(size = 13, lineHeight = 21),
    labelLarge = gs3(size = 15, lineHeight = 22, weight = FontWeight.Medium),
    labelMedium = gs3(size = 13, lineHeight = 19, weight = FontWeight.Medium),
    labelSmall = gs3(size = 11, lineHeight = 17, weight = FontWeight.Medium),
)
