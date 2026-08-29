package com.gs3.marketingops.data

import android.content.Context
import android.content.res.Configuration
import android.text.TextUtils
import android.view.View
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.gs3.marketingops.R
import java.util.Locale
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Both languages are inside the installed APK, and Arabic lays out right to left.
 *
 * WHY THIS IS AN INSTRUMENTED TEST. It asserts a property of the *installed
 * artifact*, not of the source tree. `verifyStrings` proves both `strings.xml`
 * files carry the same keys, and it would go on passing while the app on the
 * phone had no Arabic at all — because whether a locale survives packaging is
 * decided after that check, by the build.
 *
 * That is not hypothetical here. An App Bundle splits by language by default
 * and delivers only the locales the device is configured for, fetching the rest
 * over the network later. This app opens in Arabic, switches language at
 * runtime, and holds no INTERNET permission. Left at the default, a phone set
 * to English would have installed with the Arabic resources missing and no way
 * to fetch them: the switch would have fallen back to English, on the screens
 * written to explain themselves in Arabic. Lint caught it as
 * `AppBundleLocaleChanges` and `bundle { language { enableSplit = false } }` is
 * the fix. This test is what would notice if that line were ever removed.
 */
@RunWith(AndroidJUnit4::class)
class BilingualResourcesOnDeviceTest {

    private val context: Context = ApplicationProvider.getApplicationContext()

    private fun localized(tag: String): Context {
        val configuration = Configuration(context.resources.configuration)
        // forLanguageTag rather than the Locale(String) constructor, which is
        // deprecated and would fail this module's allWarningsAsErrors build.
        configuration.setLocale(Locale.forLanguageTag(tag))
        return context.createConfigurationContext(configuration)
    }

    @Test
    fun both_languages_are_present_in_the_installed_apk() {
        val arabic = localized("ar").getString(R.string.app_name)
        val english = localized("en").getString(R.string.app_name)

        assertEquals("GS3 Marketing", english)
        assertEquals("تسويق شيرمان ٣", arabic)
        // The real failure this guards is not a wrong string, it is Arabic
        // resolving to the English fallback — which looks like a working app.
        assertNotEquals(english, arabic)
    }

    @Test
    fun the_arabic_strings_are_actually_arabic_script() {
        val arabic = localized("ar").getString(R.string.app_name)

        assertTrue(
            "expected Arabic-script characters, got: $arabic",
            arabic.any { Character.UnicodeBlock.of(it) == Character.UnicodeBlock.ARABIC },
        )
    }

    @Test
    fun navigation_labels_resolve_in_both_languages() {
        // app_name alone could pass while every screen fell back, because it is
        // the one string a launcher reads. These are strings the UI reads.
        listOf(R.string.nav_dashboard, R.string.nav_inventory, R.string.nav_leads)
            .forEach { key ->
                val arabic = localized("ar").getString(key)
                val english = localized("en").getString(key)

                assertTrue("empty Arabic string for $key", arabic.isNotBlank())
                assertTrue("empty English string for $key", english.isNotBlank())
                assertNotEquals("Arabic fell back to English for $key", english, arabic)
            }
    }

    @Test
    fun arabic_lays_out_right_to_left_on_this_device() {
        // The framework's own answer, not ours. Gs3Localized overrides
        // LocalLayoutDirection from this, so if the platform disagreed the
        // whole RTL foundation would be built on a wrong assumption.
        assertEquals(
            View.LAYOUT_DIRECTION_RTL,
            TextUtils.getLayoutDirectionFromLocale(Locale.forLanguageTag("ar")),
        )
        assertEquals(
            View.LAYOUT_DIRECTION_LTR,
            TextUtils.getLayoutDirectionFromLocale(Locale.forLanguageTag("en")),
        )
    }
}
