package com.gs3.marketingops.settings.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.NumeralStyle
import com.gs3.marketingops.settings.data.AppSettings
import com.gs3.marketingops.settings.data.SettingsRepository
import com.gs3.marketingops.settings.data.ThemeMode
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val repository: SettingsRepository,
) : ViewModel() {

    /**
     * `WhileSubscribed(5_000)` rather than `Eagerly`: the five seconds carry the
     * flow across a rotation or a brief trip to another app without dropping
     * and re-reading the store, but a screen left in the background does not
     * keep a collector alive indefinitely.
     */
    val settings: StateFlow<AppSettings> = repository.settings.stateIn(
        scope = viewModelScope,
        started = SharingStarted.WhileSubscribed(5_000),
        initialValue = AppSettings.Default,
    )

    fun setLanguage(language: AppLanguage) = viewModelScope.launch {
        repository.setLanguage(language)
    }

    fun setNumerals(numerals: NumeralStyle) = viewModelScope.launch {
        repository.setNumerals(numerals)
    }

    fun setShowHijri(show: Boolean) = viewModelScope.launch {
        repository.setShowHijri(show)
    }

    fun setTheme(theme: ThemeMode) = viewModelScope.launch {
        repository.setTheme(theme)
    }
}
