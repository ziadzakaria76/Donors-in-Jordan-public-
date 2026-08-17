package com.gs3.marketingops.settings

import androidx.test.core.app.ApplicationProvider
import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.NumeralStyle
import com.gs3.marketingops.settings.data.AppSettings
import com.gs3.marketingops.settings.data.SettingsRepository
import com.gs3.marketingops.settings.data.ThemeMode
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/**
 * The settings survive a restart, which is the whole point of storing them.
 *
 * Robolectric gives a real `Context` and a real file system, so this exercises
 * the actual DataStore rather than a fake — a mock would happily prove that a
 * mock works.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [36])
class SettingsRepositoryTest {

    private fun repository() =
        SettingsRepository(ApplicationProvider.getApplicationContext())

    @Test
    fun `opens in arabic with western digits before anything is written`() = runTest {
        val settings = repository().settings.first()

        // A2 and C4. If these ever change, they change here and in
        // DECISIONS.md together, not by accident.
        assertEquals(AppLanguage.ARABIC, settings.language)
        assertEquals(NumeralStyle.WESTERN, settings.numerals)
        assertEquals(false, settings.showHijri)
        assertEquals(ThemeMode.FOLLOW_SYSTEM, settings.theme)
    }

    @Test
    fun `every setting survives being written and read back`() = runTest {
        val repository = repository()

        repository.setLanguage(AppLanguage.ENGLISH)
        repository.setNumerals(NumeralStyle.ARABIC_INDIC)
        repository.setShowHijri(true)
        repository.setTheme(ThemeMode.DARK)

        assertEquals(
            AppSettings(
                language = AppLanguage.ENGLISH,
                numerals = NumeralStyle.ARABIC_INDIC,
                showHijri = true,
                theme = ThemeMode.DARK,
            ),
            repository.settings.first(),
        )
    }

    @Test
    fun `a second instance sees what the first one wrote`() = runTest {
        repository().setLanguage(AppLanguage.ENGLISH)

        // A fresh repository over the same store — the closest thing to a
        // process restart that a JVM test can arrange, and the case that
        // catches a value held only in memory.
        assertEquals(AppLanguage.ENGLISH, repository().settings.first().language)
    }

    @Test
    fun `switching back to arabic is itself persisted`() = runTest {
        val repository = repository()

        repository.setLanguage(AppLanguage.ENGLISH)
        repository.setLanguage(AppLanguage.ARABIC)

        // Not the same as never having written: the stored value is now
        // explicitly ARABIC rather than absent, and both must read back the
        // same way.
        assertEquals(AppLanguage.ARABIC, repository().settings.first().language)
    }
}
