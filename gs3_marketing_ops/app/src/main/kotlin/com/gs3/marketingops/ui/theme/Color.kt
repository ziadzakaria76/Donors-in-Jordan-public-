package com.gs3.marketingops.ui.theme

import androidx.compose.ui.graphics.Color

/**
 * The brand palette, taken verbatim from the company's own stylesheet
 * (`website/assets/css/main.css`) rather than re-picked by eye. The app and the
 * website are the same brand, not two near-misses.
 *
 * Dark values are derived rather than inverted: brass on ink at the light
 * theme's contrast would fail against a dark surface, so the dark theme uses
 * the lighter `brass-2` for text and keeps the deeper brass for fills.
 */

internal val Ink = Color(0xFF0F1518)
internal val Ink2 = Color(0xFF18232A)
internal val Ink3 = Color(0xFF2B3940)
internal val Slate = Color(0xFF55666E)
internal val Muted = Color(0xFF77878E)
internal val Stone = Color(0xFFE4DED2)
internal val Stone2 = Color(0xFFEFEAE0)
internal val Ivory = Color(0xFFFAF7F1)
internal val Paper = Color(0xFFFFFFFF)
internal val Brass = Color(0xFF9C7A38)
internal val Brass2 = Color(0xFFBE9A55)
internal val BrassSoft = Color(0xFFEFE3CB)

/**
 * Status colours. These carry meaning — an overdue SLA, a blocked discount — so
 * they are never the only signal: every use is paired with an icon or a label,
 * because roughly one man in twelve cannot separate the red from the green.
 */
/** A dark brass fill. The one colour with no website equivalent — the site has
 *  no dark theme to need it. */
internal val BrassDeep = Color(0xFF4A3A1C)

internal val Success = Color(0xFF2F6B4F)
internal val Warn = Color(0xFF9A6B1E)
internal val Danger = Color(0xFF8C3A34)
internal val SuccessDark = Color(0xFF7BC4A1)
internal val WarnDark = Color(0xFFE0B269)
internal val DangerDark = Color(0xFFE58C85)
