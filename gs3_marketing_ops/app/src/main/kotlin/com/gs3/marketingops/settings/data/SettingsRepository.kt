package com.gs3.marketingops.settings.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.emptyPreferences
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.NumeralStyle
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton

private val Context.settingsDataStore: DataStore<Preferences> by preferencesDataStore(name = "gs3_settings")

/**
 * The display settings, persisted.
 *
 * DataStore rather than SharedPreferences: this is read on the very first frame
 * to decide the app's language, and SharedPreferences would do that read on the
 * main thread. It also gives a `Flow`, which is what makes the language switch
 * *live* — the change reaches the UI without anything having to remember to go
 * and re-read it.
 *
 * Values are stored as enum **names**, not ordinals. An ordinal silently
 * changes meaning the day someone inserts a value into the middle of an enum,
 * and the failure would be a user's app quietly switching language after an
 * update. An unrecognised name falls back to the default rather than throwing:
 * a settings file that cannot be parsed must not stop the app opening.
 */
@Singleton
class SettingsRepository @Inject constructor(
    private val context: Context,
) {

    private object Keys {
        val Language = stringPreferencesKey("language")
        val Numerals = stringPreferencesKey("numerals")
        val ShowHijri = booleanPreferencesKey("show_hijri")
        val Theme = stringPreferencesKey("theme")
    }

    val settings: Flow<AppSettings> = context.settingsDataStore.data
        .catch { cause ->
            // A corrupt or unreadable file is recoverable — the user loses
            // their display preferences, not their data. Anything else is a
            // real failure and is allowed to propagate.
            if (cause is IOException) emit(emptyPreferences()) else throw cause
        }
        .map { preferences ->
            AppSettings(
                language = preferences[Keys.Language]
                    .toEnumOr(AppSettings.Default.language, AppLanguage.entries),
                numerals = preferences[Keys.Numerals]
                    .toEnumOr(AppSettings.Default.numerals, NumeralStyle.entries),
                showHijri = preferences[Keys.ShowHijri] ?: AppSettings.Default.showHijri,
                theme = preferences[Keys.Theme]
                    .toEnumOr(AppSettings.Default.theme, ThemeMode.entries),
            )
        }

    suspend fun setLanguage(language: AppLanguage) = put(Keys.Language, language.name)

    suspend fun setNumerals(numerals: NumeralStyle) = put(Keys.Numerals, numerals.name)

    suspend fun setTheme(theme: ThemeMode) = put(Keys.Theme, theme.name)

    suspend fun setShowHijri(show: Boolean) {
        context.settingsDataStore.edit { it[Keys.ShowHijri] = show }
    }

    private suspend fun put(key: Preferences.Key<String>, value: String) {
        context.settingsDataStore.edit { it[key] = value }
    }
}

/** Name-based enum lookup that falls back rather than throwing. */
private fun <T : Enum<T>> String?.toEnumOr(fallback: T, entries: List<T>): T =
    entries.firstOrNull { it.name == this } ?: fallback
