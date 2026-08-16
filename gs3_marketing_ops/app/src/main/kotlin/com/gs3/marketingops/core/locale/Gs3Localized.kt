package com.gs3.marketingops.core.locale

import android.content.Context
import android.content.ContextWrapper
import android.content.res.Configuration
import android.content.res.Resources
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.unit.LayoutDirection
import com.gs3.marketingops.domain.money.AppLanguage
import java.util.Locale

/** The BCP-47 tag for each language the app is authored in. */
internal val AppLanguage.localeTag: String
    get() = when (this) {
        AppLanguage.ARABIC -> "ar"
        AppLanguage.ENGLISH -> "en"
    }

internal val AppLanguage.layoutDirection: LayoutDirection
    get() = when (this) {
        AppLanguage.ARABIC -> LayoutDirection.Rtl
        AppLanguage.ENGLISH -> LayoutDirection.Ltr
    }

/**
 * A [ContextWrapper] that answers with another context's resources.
 *
 * The subtlety this exists for: `createConfigurationContext` returns a fresh
 * context that is **not** wrapped around the activity. Handing that straight to
 * `LocalContext` would give the right strings and quietly break every later
 * piece of code that walks `baseContext` to find the hosting activity — which
 * is how launching an intent, showing a biometric prompt or asking for a
 * permission all locate their activity. That breakage would appear milestones
 * later, far from the cause.
 *
 * Wrapping the *original* context and overriding only `getResources` and
 * `getAssets` keeps the activity chain intact and still returns Arabic strings.
 */
private class LocalizedContextWrapper(
    base: Context,
    private val localized: Context,
) : ContextWrapper(base) {
    override fun getResources(): Resources = localized.resources
    override fun getAssets(): android.content.res.AssetManager = localized.assets
}

/**
 * Applies the chosen language to everything composed inside it.
 *
 * This is what makes the language switch **live**. The alternative — the
 * platform's per-app locales — either needs API 33 or drags in AppCompat for
 * the backport, and in both cases it restarts the activity: the screen blinks,
 * and any half-typed lead is gone. Overriding the composition locals instead
 * re-composes in place, so a salesperson can switch language mid-conversation
 * to show a client a screen and switch back, without losing what they were
 * doing.
 *
 * Three locals are provided together, and all three are needed:
 *
 *  - `LocalContext`, because `stringResource` resolves through its resources;
 *  - `LocalConfiguration`, because Compose reads it to know when the resource
 *    lookups it has cached are stale — without it, some text keeps the previous
 *    language until something else happens to recompose;
 *  - `LocalLayoutDirection`, which is what actually flips the layout. Every
 *    `start`/`end` padding, every row order and every auto-mirrored icon in the
 *    app follows from this one value.
 */
@Composable
internal fun Gs3Localized(
    language: AppLanguage,
    content: @Composable () -> Unit,
) {
    val context = LocalContext.current
    val baseConfiguration = LocalConfiguration.current

    val configuration = remember(language, baseConfiguration) {
        Configuration(baseConfiguration).apply {
            val locale = Locale.forLanguageTag(language.localeTag)
            Locale.setDefault(locale)
            setLocale(locale)
            setLayoutDirection(locale)
        }
    }

    val localizedContext = remember(context, configuration) {
        LocalizedContextWrapper(
            base = context,
            localized = context.createConfigurationContext(configuration),
        )
    }

    CompositionLocalProvider(
        LocalContext provides localizedContext,
        LocalConfiguration provides configuration,
        LocalLayoutDirection provides language.layoutDirection,
        content = content,
    )
}
