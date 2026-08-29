package jo.tendermonitor.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import jo.tendermonitor.data.portals.ProbeReport
import jo.tendermonitor.data.portals.ProbeSource
import jo.tendermonitor.ui.AddPortalState
import jo.tendermonitor.ui.ProblemCard
import jo.tendermonitor.ui.SectionHeader
import jo.tendermonitor.ui.StatusChip
import jo.tendermonitor.ui.theme.StatusColors

/**
 * Adding a portal by URL, and testing it before it is committed.
 *
 * The test is the reason this screen is worth having. Committing a URL nobody
 * has looked at is how a portal ends up reporting "unavailable" forever while
 * looking like an honest failure — the mistake the backend made with KfW and
 * with ADFD. One tap fetches the page on GitHub's runner and reports what each
 * extraction layer found, including the rows, so the decision to save is made
 * on evidence.
 */
@Composable
fun AddPortalScreen(
    state: AddPortalState,
    onChange: ((AddPortalState) -> AddPortalState) -> Unit,
    onTest: () -> Unit,
    onSave: () -> Unit,
    onCancel: () -> Unit,
    onOpenUrl: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var advanced by remember { mutableStateOf(false) }

    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState())) {

        Card(Modifier.fillMaxWidth().padding(12.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text("A new portal", style = MaterialTheme.typography.titleMedium,
                     fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(4.dp))
                Text(
                    "A name and a listing URL is usually enough: the page goes " +
                        "through the same six-layer cascade every other portal " +
                        "uses. Test it before saving — a URL alone is " +
                        "best-effort, not a guarantee.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = state.name,
                    onValueChange = { v -> onChange { it.copy(name = v) } },
                    label = { Text("Name") },
                    placeholder = { Text("Example Development Bank") },
                    supportingText = { Text("What the report calls it.") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )

                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = state.key,
                    onValueChange = { v -> onChange { it.copy(key = v.lowercase()) } },
                    label = { Text("Key") },
                    placeholder = { Text("exampledb") },
                    supportingText = {
                        Text("Lower-case, no spaces. Used in --only, in the " +
                             "output filename, and in the status table.")
                    },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )

                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = state.urls,
                    onValueChange = { v -> onChange { it.copy(urls = v) } },
                    label = { Text("Listing URL(s)") },
                    placeholder = { Text("https://example.org/tenders") },
                    supportingText = {
                        Text("One per line. Several portals publish across two " +
                             "sites; one failing is tolerated while another works.")
                    },
                    minLines = 2,
                    modifier = Modifier.fillMaxWidth(),
                )

                Spacer(Modifier.height(12.dp))
                Text("Reliability tier", style = MaterialTheme.typography.labelLarge)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(
                        1 to "API",
                        2 to "HTML",
                        3 to "Announcements",
                    ).forEach { (tier, label) ->
                        FilterChip(
                            selected = state.tier == tier,
                            onClick = { onChange { it.copy(tier = tier) } },
                            label = { Text(label) },
                        )
                    }
                }
                Text(
                    "Shown in the report so a quiet tier-3 portal is not " +
                        "mistaken for a broken one.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                Spacer(Modifier.height(8.dp))
                TextButton(onClick = { advanced = !advanced }) {
                    Text(if (advanced) "Hide advanced fields" else "Advanced fields")
                }

                if (advanced) {
                    OutlinedTextField(
                        value = state.selectors,
                        onValueChange = { v -> onChange { it.copy(selectors = v) } },
                        label = { Text("CSS selectors (optional)") },
                        placeholder = { Text("div.tender-item") },
                        supportingText = {
                            Text("Hints, not contracts. A wrong one is rejected " +
                                 "by the quality gate and a class-independent " +
                                 "layer takes over — but an over-broad one like " +
                                 "bare 'article' can match a nav menu and " +
                                 "short-circuit the layer that would have worked.")
                        },
                        minLines = 2,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = state.anchorHint,
                        onValueChange = { v -> onChange { it.copy(anchorHint = v) } },
                        label = { Text("Anchor hint (optional)") },
                        placeholder = { Text("/procurement/") },
                        supportingText = {
                            Text("A URL fragment notice links contain. Last-resort " +
                                 "layer only.")
                        },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = state.currency,
                        onValueChange = { v -> onChange { it.copy(currency = v.uppercase()) } },
                        label = { Text("Currency (optional)") },
                        placeholder = { Text("EUR") },
                        supportingText = {
                            Text("Used to convert published values to USD for " +
                                 "ranking. Unknown values are kept and flagged.")
                        },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Switch(
                            checked = state.filterToJordan,
                            onCheckedChange = { v -> onChange { it.copy(filterToJordan = v) } },
                        )
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text("Filter to Jordan",
                                 style = MaterialTheme.typography.bodyMedium)
                            Text(
                                "On for a worldwide listing. Off only when the " +
                                    "page is already Jordan-specific — off on a " +
                                    "worldwide source puts every country in the " +
                                    "report.",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = state.notes,
                        onValueChange = { v -> onChange { it.copy(notes = v) } },
                        label = { Text("Notes (optional)") },
                        supportingText = {
                            Text("Why this portal is configured the way it is. " +
                                 "Goes into portals.json and is read by whoever " +
                                 "fixes it later.")
                        },
                        minLines = 2,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }

                state.formProblem?.let { problem ->
                    Spacer(Modifier.height(10.dp))
                    Text(
                        problem,
                        style = MaterialTheme.typography.bodySmall,
                        color = StatusColors.broken,
                    )
                }

                Spacer(Modifier.height(14.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Button(onClick = onTest, enabled = !state.testing && !state.saving) {
                        if (state.testing) {
                            CircularProgressIndicator(
                                Modifier.width(16.dp).height(16.dp), strokeWidth = 2.dp,
                            )
                            Spacer(Modifier.width(8.dp))
                        }
                        Text(if (state.probe == null) "Test it" else "Test again")
                    }
                    Button(onClick = onSave, enabled = state.canSave) {
                        Text(if (state.saving) "Saving..." else "Save")
                    }
                    TextButton(onClick = onCancel) { Text("Cancel") }
                }
                if (state.probe == null && !state.testing) {
                    Text(
                        "Save is available once the page has been tested. " +
                            "Committing a URL nobody has looked at is how a " +
                            "portal ends up reporting unavailable forever while " +
                            "looking like an honest failure.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(top = 6.dp),
                    )
                }
                state.testStage?.let { stage ->
                    Spacer(Modifier.height(8.dp))
                    Text(stage, style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        state.problem?.let { problem ->
            ProblemCard(problem, onRetry = onTest)
        }

        state.probe?.let { report -> ProbeResult(report, onOpenUrl) }

        Spacer(Modifier.height(32.dp))
    }
}

/**
 * What the test found.
 *
 * The verdict, then every layer, then the rows. In that order because that is
 * the order of increasing evidence: the verdict is a summary, the layer table
 * says how confident it is, and only the rows can show that a column is wrong.
 */
@Composable
private fun ProbeResult(report: ProbeReport, onOpenUrl: (String) -> Unit) {
    val verdict = report.verdict
    val tone = if (verdict.usable) StatusColors.ok else StatusColors.warning

    Card(
        Modifier.fillMaxWidth().padding(12.dp),
        colors = CardDefaults.cardColors(containerColor = tone.copy(alpha = 0.08f)),
    ) {
        Column(Modifier.padding(14.dp)) {
            StatusChip(if (verdict.usable) "READS" else "DOES NOT READ", tone)
            Spacer(Modifier.height(8.dp))
            Text(verdict.headline, style = MaterialTheme.typography.titleSmall,
                 fontWeight = FontWeight.SemiBold)
            if (verdict.detail.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(verdict.detail, style = MaterialTheme.typography.bodySmall)
            }
            if (verdict.advice.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    verdict.advice,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (report.wouldBeRejected) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "This entry would be rejected when the run loads it:",
                    style = MaterialTheme.typography.bodySmall,
                    color = StatusColors.broken,
                )
                report.rejected.forEach { problem ->
                    Text("· $problem", style = MaterialTheme.typography.labelSmall,
                         color = StatusColors.broken)
                }
            }
        }
    }

    report.sources.forEach { source ->
        SourceResult(source, report.qualityThreshold, onOpenUrl)
    }
}

@Composable
private fun SourceResult(
    source: ProbeSource,
    threshold: Double,
    onOpenUrl: (String) -> Unit,
) {
    Card(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)) {
        Column(Modifier.padding(14.dp)) {
            Text(
                source.url,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.fillMaxWidth(),
            )
            TextButton(onClick = { onOpenUrl(source.url) }) { Text("Open the page") }

            if (!source.fetched) {
                Text(
                    "Could not be fetched: ${source.error}",
                    style = MaterialTheme.typography.bodySmall,
                    color = StatusColors.broken,
                )
                return@Column
            }

            Text(
                "${source.bytes} bytes read",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Spacer(Modifier.height(10.dp))
            Text("Every layer, in order", style = MaterialTheme.typography.labelLarge)
            Spacer(Modifier.height(4.dp))
            source.layers.forEach { layer ->
                Row(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
                    Text(
                        layer.layer,
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.width(120.dp),
                        color = if (layer.wins) StatusColors.ok
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        "${layer.rows} rows",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.width(70.dp),
                    )
                    Text(
                        "%.2f".format(layer.quality),
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.width(50.dp),
                        color = if (layer.quality >= threshold) StatusColors.ok
                        else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (layer.wins) {
                        Text("wins", style = MaterialTheme.typography.labelSmall,
                             color = StatusColors.ok)
                    }
                }
            }
            Text(
                "The gate is %.2f. A layer below it is rejected even if it found rows."
                    .format(threshold),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            if (source.diagnosis.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    source.diagnosis,
                    style = MaterialTheme.typography.bodySmall,
                    color = StatusColors.warning,
                )
            }

            if (source.sampleRows.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                HorizontalDivider()
                Spacer(Modifier.height(8.dp))
                Text(
                    if (source.sampleRejected) {
                        "Rows from the best-scoring layer — which the gate " +
                            "REJECTED. Shown anyway: whether these are notices " +
                            "missing their dates or navigation dressed as " +
                            "opportunities is not something the score can answer."
                    } else {
                        "Rows from the winning '${source.sampleFrom}' layer. " +
                            "Read them: a score cannot see a column being wrong, " +
                            "and a wrong deadline column silently drops open " +
                            "tenders."
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = if (source.sampleRejected) StatusColors.warning
                    else MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(8.dp))
                source.sampleRows.forEach { row ->
                    Column(Modifier.padding(vertical = 6.dp)) {
                        Text(row.title.ifBlank { "(no title found)" },
                             style = MaterialTheme.typography.bodyMedium)
                        Text(
                            "posted ${row.postedText ?: "—"}   ·   " +
                                "closes ${row.closingText ?: "—"}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        row.url?.let {
                            Text(it, style = MaterialTheme.typography.labelSmall,
                                 color = MaterialTheme.colorScheme.primary)
                        } ?: Text(
                            "no link on this row",
                            style = MaterialTheme.typography.labelSmall,
                            color = StatusColors.warning,
                        )
                    }
                    HorizontalDivider()
                }
            }
        }
    }
}
