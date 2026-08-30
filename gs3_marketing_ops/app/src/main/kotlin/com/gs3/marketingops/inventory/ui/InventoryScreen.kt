package com.gs3.marketingops.inventory.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.gs3.marketingops.R
import com.gs3.marketingops.domain.inventory.Apartment
import com.gs3.marketingops.domain.inventory.InventoryTotals
import com.gs3.marketingops.domain.inventory.PriorityClass
import com.gs3.marketingops.domain.inventory.UnitStatus
import com.gs3.marketingops.domain.inventory.totals
import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.MoneyFormat
import com.gs3.marketingops.domain.money.NumeralStyle
import com.gs3.marketingops.settings.data.AppSettings
import com.gs3.marketingops.ui.components.Gs3EmptyState
import com.gs3.marketingops.ui.components.Gs3ScreenScaffold

/**
 * The fourteen apartments, with the one number a buyer actually compares on.
 *
 * **Price per square metre is shown on every row, deliberately.** The objection
 * the team hears most is "this is dearer than the project down the road", and
 * the honest answer is that the areas differ — which is only a usable answer if
 * the rate is in front of the salesperson while they are talking. Computing it
 * in the client's head at the door is how a wrong figure gets said out loud.
 *
 * Every figure here is derived from `:domain`. Nothing is stored pre-formatted
 * and nothing is re-typed: the summary is `List<Apartment>.totals()`, the rate
 * is `Apartment.pricePerSquareMetre`, both already tested against the brief's
 * own published numbers.
 */
@Composable
internal fun InventoryScreen(
    settings: AppSettings,
    modifier: Modifier = Modifier,
    viewModel: InventoryViewModel = hiltViewModel(),
) {
    val units by viewModel.units.collectAsStateWithLifecycle()
    InventoryList(units = units, settings = settings, modifier = modifier)
}

/**
 * The screen with its data handed to it.
 *
 * Split from [InventoryScreen] so it can be rendered from a test without an
 * injection graph or a database behind it: the fixture is a `List<Apartment>`,
 * which is exactly what the seed puts in the table. A screenshot test that had
 * to stand up Hilt and Room would be testing those instead of this layout.
 */
@Composable
internal fun InventoryList(
    units: List<Apartment>,
    settings: AppSettings,
    modifier: Modifier = Modifier,
) {
    Gs3ScreenScaffold(
        title = stringResource(R.string.nav_inventory),
        modifier = modifier,
    ) { innerPadding ->
        if (units.isEmpty()) {
            Gs3EmptyState(
                title = stringResource(R.string.empty_inventory_title),
                body = stringResource(R.string.empty_inventory_body),
                modifier = Modifier.padding(innerPadding),
            )
        } else {
            LazyColumn(
                modifier = Modifier.padding(innerPadding),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 12.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item(key = "summary") {
                    InventorySummary(totals = units.totals(), settings = settings)
                }
                items(units, key = { it.number }) { unit ->
                    UnitRow(unit = unit, settings = settings)
                }
            }
        }
    }
}

/**
 * The schedule's own totals: fourteen units, 2,320 m², 1,496,000 JOD, 645 JOD/m².
 *
 * These are the figures the brief publishes and the website repeats, so the
 * team can be asked about any of them. Showing them computed rather than
 * hardcoded means the screen cannot drift from the schedule it is summarising.
 */
@Composable
private fun InventorySummary(
    totals: InventoryTotals,
    settings: AppSettings,
    modifier: Modifier = Modifier,
) {
    OutlinedCard(modifier = modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = stringResource(R.string.inventory_summary_heading),
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier.semantics { heading() },
            )
            LabelledValue(
                label = stringResource(R.string.inventory_summary_units),
                value = MoneyFormat.formatInteger(totals.unitCount.toLong(), settings.numerals),
            )
            LabelledValue(
                label = stringResource(R.string.inventory_summary_internal_area),
                value = stringResource(
                    R.string.unit_area_value,
                    MoneyFormat.formatInteger(totals.internalArea.toLong(), settings.numerals),
                ),
            )
            LabelledValue(
                label = stringResource(R.string.inventory_summary_value),
                value = MoneyFormat.formatMoney(
                    totals.grossDevelopmentValue,
                    settings.language,
                    settings.numerals,
                ),
            )
            LabelledValue(
                label = stringResource(R.string.inventory_summary_price_per_sqm),
                value = MoneyFormat.formatMoney(
                    totals.weightedPricePerSquareMetre,
                    settings.language,
                    settings.numerals,
                ),
            )
        }
    }
}

@Composable
private fun UnitRow(
    unit: Apartment,
    settings: AppSettings,
    modifier: Modifier = Modifier,
) {
    val number = MoneyFormat.formatInteger(unit.number.toLong(), settings.numerals)
    val title = stringResource(R.string.unit_number, number)

    // The position is data, not a string resource: it is the schedule's own
    // wording in each language, cross-checked against the website. Picking the
    // wrong half here would show «الطابق الأرضي» to an English-speaking client.
    val position = when (settings.language) {
        AppLanguage.ARABIC -> unit.positionAr
        AppLanguage.ENGLISH -> unit.positionEn
    }
    val status = stringResource(unit.status.labelRes())
    val price = MoneyFormat.formatMoney(unit.listPrice, settings.language, settings.numerals)

    Card(
        modifier = modifier
            .fillMaxWidth()
            // One TalkBack stop per apartment rather than nine, and every line
            // still read out.
            //
            // `clearAndSetSemantics` with a hand-written description was tried
            // first and is wrong twice over: it *replaces* the children, so the
            // price per square metre and the areas stop being announced at all
            // — the numbers this screen exists to surface — and it also has to
            // be kept in step with the layout by hand for ever.
            // `mergeDescendants` gets the single focus stop by merging what is
            // already there, in order, already translated.
            .semantics(mergeDescendants = true) {},
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(text = title, style = MaterialTheme.typography.titleMedium)
                Text(
                    text = status,
                    style = MaterialTheme.typography.labelLarge,
                    color = unit.status.tint(),
                )
            }

            Text(
                text = position,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                text = stringResource(unit.priorityClass.labelRes()),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            LabelledValue(
                label = stringResource(R.string.unit_internal_area),
                value = stringResource(
                    R.string.unit_area_value,
                    MoneyFormat.formatInteger(unit.internalArea.toLong(), settings.numerals),
                ),
            )
            LabelledValue(
                label = stringResource(R.string.unit_external_area),
                value = if (unit.hasExternalArea) {
                    stringResource(
                        R.string.unit_area_value,
                        MoneyFormat.formatInteger(unit.externalArea.toLong(), settings.numerals),
                    )
                } else {
                    // Eight of the fourteen have none. "0 m²" reads as a
                    // measurement that happens to be zero; this says there is
                    // no terrace, which is the question being asked.
                    stringResource(R.string.unit_no_external_area)
                },
            )
            LabelledValue(
                label = stringResource(R.string.unit_price_per_sqm),
                value = MoneyFormat.formatMoney(
                    unit.pricePerSquareMetre,
                    settings.language,
                    settings.numerals,
                ),
            )

            Text(
                text = price,
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 2.dp),
            )
        }
    }
}

/**
 * A label and its value on one line, label at `start` and value at `end`.
 *
 * `SpaceBetween` rather than a fixed width, so the pair mirrors correctly in
 * Arabic without a second layout: `start` is the right-hand side there, and
 * nothing here says left or right.
 */
@Composable
private fun LabelledValue(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(text = value, style = MaterialTheme.typography.bodyMedium)
    }
}

private fun UnitStatus.labelRes(): Int = when (this) {
    UnitStatus.AVAILABLE -> R.string.unit_status_available
    UnitStatus.RESERVED -> R.string.unit_status_reserved
    UnitStatus.CONTRACTED -> R.string.unit_status_contracted
}

private fun PriorityClass.labelRes(): Int = when (this) {
    PriorityClass.A -> R.string.unit_class_a
    PriorityClass.B -> R.string.unit_class_b
    PriorityClass.C -> R.string.unit_class_c
    PriorityClass.D -> R.string.unit_class_d
}

/**
 * Status colour, and colour is never the only carrier: the word is always
 * there beside it. A red "Contracted" that reads only as red is unusable to a
 * colour-blind salesperson and invisible to TalkBack.
 */
@Composable
private fun UnitStatus.tint() = when (this) {
    UnitStatus.AVAILABLE -> MaterialTheme.colorScheme.primary
    UnitStatus.RESERVED -> MaterialTheme.colorScheme.tertiary
    UnitStatus.CONTRACTED -> MaterialTheme.colorScheme.onSurfaceVariant
}
