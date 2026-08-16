package com.gs3.marketingops.settings.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.gs3.marketingops.R
import com.gs3.marketingops.domain.datetime.DateFormat
import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.Jod
import com.gs3.marketingops.domain.money.MoneyFormat
import com.gs3.marketingops.domain.money.NumeralStyle
import com.gs3.marketingops.settings.data.AppSettings
import com.gs3.marketingops.settings.data.ThemeMode
import com.gs3.marketingops.ui.components.Gs3ScreenScaffold
import java.time.LocalDate

/**
 * Display settings, and a live preview of what they do.
 *
 * The preview is the point of this screen rather than decoration. "Arabic-Indic
 * digits" and "show the Hijri date" are abstract until you see «٩٠٬٠٠٠ د.أ» and
 * a date in both calendars; with the preview, the person choosing can see the
 * consequence before they commit to it, which is the difference between a
 * setting people use and one they leave alone because they are not sure what it
 * will do.
 */
@Composable
internal fun SettingsScreen(
    settings: AppSettings,
    onLanguageChange: (AppLanguage) -> Unit,
    onNumeralsChange: (NumeralStyle) -> Unit,
    onShowHijriChange: (Boolean) -> Unit,
    onThemeChange: (ThemeMode) -> Unit,
    modifier: Modifier = Modifier,
    today: LocalDate = LocalDate.now(),
) {
    Gs3ScreenScaffold(
        title = stringResource(R.string.settings_title),
        modifier = modifier,
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(20.dp),
        ) {
            SettingSection(title = stringResource(R.string.settings_language)) {
                ChoiceRow(
                    options = AppLanguage.entries,
                    selected = settings.language,
                    onSelect = onLanguageChange,
                    label = { language ->
                        stringResource(
                            when (language) {
                                AppLanguage.ARABIC -> R.string.settings_language_arabic
                                AppLanguage.ENGLISH -> R.string.settings_language_english
                            },
                        )
                    },
                )
            }

            SettingSection(title = stringResource(R.string.settings_numerals)) {
                ChoiceRow(
                    options = NumeralStyle.entries,
                    selected = settings.numerals,
                    onSelect = onNumeralsChange,
                    label = { style ->
                        stringResource(
                            when (style) {
                                NumeralStyle.WESTERN -> R.string.settings_numerals_western
                                NumeralStyle.ARABIC_INDIC -> R.string.settings_numerals_arabic
                            },
                        )
                    },
                )
            }

            SettingSection(title = stringResource(R.string.settings_theme)) {
                ChoiceRow(
                    options = ThemeMode.entries,
                    selected = settings.theme,
                    onSelect = onThemeChange,
                    label = { mode ->
                        stringResource(
                            when (mode) {
                                ThemeMode.FOLLOW_SYSTEM -> R.string.settings_theme_system
                                ThemeMode.LIGHT -> R.string.settings_theme_light
                                ThemeMode.DARK -> R.string.settings_theme_dark
                            },
                        )
                    },
                )
            }

            SettingSection(title = stringResource(R.string.settings_show_hijri)) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Switch(
                        checked = settings.showHijri,
                        onCheckedChange = onShowHijriChange,
                    )
                    Text(
                        text = stringResource(R.string.settings_show_hijri_explanation),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            SettingsPreview(settings = settings, today = today)
        }
    }
}

/**
 * The live preview.
 *
 * Every value here is rendered by the same `:domain` formatters the rest of the
 * app uses — [MoneyFormat] and [DateFormat] — rather than by preview-only
 * code. If the preview and a real screen ever disagreed, the preview would be
 * worse than useless, because it would be teaching the wrong thing.
 *
 * The price is 90,000 JOD because that is the entry price the company actually
 * advertises for this project, so the preview shows a number the team
 * recognises.
 */
@Composable
private fun SettingsPreview(
    settings: AppSettings,
    today: LocalDate,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = stringResource(R.string.settings_preview_title),
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.semantics { heading() },
            )
            HorizontalDivider()

            PreviewRow(
                label = stringResource(R.string.settings_preview_date),
                value = DateFormat.formatDate(
                    date = today,
                    language = settings.language,
                    numerals = settings.numerals,
                    showHijri = settings.showHijri,
                ),
            )
            PreviewRow(
                label = stringResource(R.string.settings_preview_price),
                value = MoneyFormat.formatMoney(
                    amount = Jod.ofDinars(90_000),
                    language = settings.language,
                    numerals = settings.numerals,
                ),
            )
        }
    }
}

@Composable
private fun PreviewRow(label: String, value: String) {
    Column {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = value, style = MaterialTheme.typography.bodyLarge)
    }
}

@Composable
private fun SettingSection(
    title: String,
    content: @Composable () -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.semantics { heading() },
        )
        content()
    }
}

/**
 * A single-choice row of chips.
 *
 * `selectableGroup()` is what makes TalkBack announce this as "1 of 3" rather
 * than reading three unrelated buttons, and `widthIn` keeps a long option label
 * from being clipped at a 200% font scale.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun <T> ChoiceRow(
    options: List<T>,
    selected: T,
    onSelect: (T) -> Unit,
    label: @Composable (T) -> String,
) {
    FlowRow(
        modifier = Modifier
            .fillMaxWidth()
            .selectableGroup(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        options.forEach { option ->
            FilterChip(
                selected = option == selected,
                onClick = { onSelect(option) },
                label = {
                    Text(
                        text = label(option),
                        modifier = Modifier.widthIn(max = 240.dp),
                    )
                },
            )
        }
    }
}
