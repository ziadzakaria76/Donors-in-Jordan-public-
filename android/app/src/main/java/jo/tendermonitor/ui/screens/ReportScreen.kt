package jo.tendermonitor.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import jo.tendermonitor.data.report.Opportunity
import jo.tendermonitor.ui.ProblemCard
import jo.tendermonitor.ui.Provenance
import jo.tendermonitor.ui.ReportState
import jo.tendermonitor.ui.SectionHeader
import jo.tendermonitor.ui.StatusChip
import jo.tendermonitor.ui.formatEpochMillis
import jo.tendermonitor.ui.theme.StatusColors

enum class SortBy(val label: String) { SCORE("Score"), DEADLINE("Deadline") }

/**
 * The report.
 *
 * Three things this screen must never do, all of them carried from the
 * backend:
 *
 *  * show an empty list without saying WHY it is empty -- a quiet run and a
 *    dead one look the same otherwise;
 *  * show a filtered list without saying it is filtered, with both numbers;
 *  * hide the cached report behind an error. A stale report with a banner is
 *    more useful than a blank screen.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReportScreen(
    state: ReportState,
    onRefresh: () -> Unit,
    onOpenUrl: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var sortBy by remember { mutableStateOf(SortBy.SCORE) }
    var donorFilter by remember { mutableStateOf<String?>(null) }
    var sectorFilter by remember { mutableStateOf<String?>(null) }

    val report = state.report

    // Pull to refresh over the whole screen.
    //
    // When there is a report the LazyColumn below provides the nested scroll
    // the gesture rides on. When there is not, the column is made scrollable
    // instead -- otherwise the one moment you most want to pull, an empty
    // screen, would be the one moment the gesture did nothing.
    PullToRefreshBox(
        isRefreshing = state.loading,
        onRefresh = onRefresh,
        modifier = modifier.fillMaxSize(),
    ) {
    Column(
        Modifier.fillMaxSize().then(
            if (report == null) Modifier.verticalScroll(rememberScrollState())
            else Modifier
        )
    ) {
        if (state.loading) {
            Row(
                Modifier.fillMaxWidth().padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CircularProgressIndicator(Modifier.width(18.dp).height(18.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(10.dp))
                Text("Reading the latest run...", style = MaterialTheme.typography.bodySmall)
            }
        }

        state.problem?.let { problem ->
            if (state.hasStaleData) {
                // The report below is real, just not current. Say which.
                Card(
                    Modifier.fillMaxWidth().padding(12.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = StatusColors.warning.copy(alpha = 0.10f),
                    ),
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Text(
                            "Showing the last report that downloaded",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = StatusColors.warning,
                        )
                        Text(
                            "${problem.headline}. ${problem.detail}",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        state.cached?.let {
                            Text(
                                "Stored ${formatEpochMillis(it.storedAt)}, from run " +
                                    "#${it.runNumber}.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        TextButton(onClick = onRefresh) { Text("Try again") }
                    }
                }
            } else {
                ProblemCard(problem, onRetry = onRefresh)
            }
        }

        if (report == null) {
            if (state.problem == null && !state.loading) {
                EmptyStart(onRefresh)
            }
            return@Column
        }

        val summary = report.run
        Card(Modifier.fillMaxWidth().padding(12.dp)) {
            Column(Modifier.padding(14.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    StatusChip(
                        text = when (summary.status) {
                            "action_needed" -> "ACTION NEEDED"
                            "partial" -> "PARTIAL"
                            "quiet" -> "QUIET"
                            "ok" -> "OK"
                            else -> summary.status.uppercase()
                        },
                        color = StatusColors.forRunStatus(summary.status),
                    )
                    Spacer(Modifier.width(8.dp))
                    state.cached?.let {
                        Text(
                            "run #${it.runNumber}",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.weight(1f))
                    if (state.provenance == Provenance.CACHE) {
                        Text(
                            "offline copy",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                Spacer(Modifier.height(8.dp))
                // The pipeline's own sentence, not one recomposed here. An app
                // that re-words this would eventually disagree with the Word
                // pack, and nobody would see the disagreement.
                Text(summary.statusLine, style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(8.dp))
                Text(
                    "${summary.scanned} notices read across ${summary.portalsTotal} " +
                        "portals. ${summary.opportunityCount} reported" +
                        if (summary.mergedDuplicates > 0) {
                            ", ${summary.mergedDuplicates} duplicate(s) merged."
                        } else ".",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (summary.newOnly) {
                    Text(
                        "This run reported only what is new since the last one.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                state.cached?.let {
                    Text(
                        "Downloaded ${formatEpochMillis(it.storedAt)}.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        val donors = remember(report) { report.tenders.map { it.portalName }.distinct().sorted() }
        val sectors = remember(report) {
            report.tenders.mapNotNull { it.sector }.distinct().sorted()
        }

        val shown = remember(report, sortBy, donorFilter, sectorFilter) {
            report.tenders
                .filter { donorFilter == null || it.portalName == donorFilter }
                .filter { sectorFilter == null || it.sector == sectorFilter }
                .sortedWith(
                    when (sortBy) {
                        SortBy.SCORE -> compareByDescending<Opportunity> { it.score }
                        // Undated notices go LAST rather than first. They have
                        // no deadline, which is not the same as an imminent
                        // one, and sorting them to the top of a
                        // deadline-ordered list would read as urgency.
                        SortBy.DEADLINE -> compareBy<Opportunity>(
                            { it.closingDate.isNullOrBlank() },
                            { it.closingDate.orEmpty() },
                        )
                    }
                )
        }

        Row(
            Modifier.fillMaxWidth().padding(horizontal = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            SortBy.entries.forEach { option ->
                FilterChip(
                    selected = sortBy == option,
                    onClick = { sortBy = option },
                    label = { Text(option.label) },
                )
            }
            Spacer(Modifier.weight(1f))
            FilterMenu("Donor", donors, donorFilter) { donorFilter = it }
            FilterMenu("Sector", sectors, sectorFilter) { sectorFilter = it }
        }

        if (shown.size != report.tenders.size) {
            // No silent caps. Both numbers, always.
            Text(
                "Showing ${shown.size} of ${report.tenders.size} opportunities " +
                    "(filters are on).",
                style = MaterialTheme.typography.bodySmall,
                color = StatusColors.warning,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 6.dp),
            )
        }

        if (report.tenders.isEmpty()) {
            NothingToShow(
                status = summary.status,
                statusLine = summary.statusLine,
                portalsBroken = summary.portalsBroken,
            )
            return@Column
        }

        LazyColumn(Modifier.fillMaxSize()) {
            items(shown, key = { it.id.ifBlank { it.title } }) { tender ->
                OpportunityRow(tender, onOpenUrl)
                HorizontalDivider()
            }
            item {
                Text(
                    "${shown.size} shown. Every opportunity in this run is here -- the " +
                        "list is not truncated.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp),
                )
            }
        }
    }
    }
}

@Composable
private fun OpportunityRow(tender: Opportunity, onOpenUrl: (String) -> Unit) {
    val hasLink = !tender.url.isNullOrBlank()
    Column(
        Modifier
            .fillMaxWidth()
            .clickable(enabled = hasLink) { tender.url?.let(onOpenUrl) }
            .padding(horizontal = 16.dp, vertical = 10.dp)
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Text(
                "%.0f".format(tender.score),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = scoreColor(tender.score),
                modifier = Modifier.width(38.dp),
            )
            Column(Modifier.weight(1f)) {
                // The notice's own words, in the notice's own direction.
                //
                // The pipeline detects Arabic and records it per opportunity;
                // the e-mail applies class="rtl" and the Word pack has its own
                // branch. This screen ignored the field entirely, so an Arabic
                // title rendered left-to-right, putting its punctuation and any
                // Latin fragment or figure in the wrong visual place. Saudi Fund
                // publishes in Arabic and the pipeline deliberately keeps it in
                // the original, so this is not a hypothetical row.
                //
                // Only the title is re-based. Everything else on this row --
                // portal name, sector, the deadline sentence, the flags -- is
                // written by this app in English, and forcing those right would
                // be wrong in the opposite direction.
                val ambient = LocalLayoutDirection.current
                val direction =
                    if (tender.language.equals("ar", ignoreCase = true)) {
                        LayoutDirection.Rtl
                    } else {
                        ambient
                    }
                CompositionLocalProvider(LocalLayoutDirection provides direction) {
                    Text(
                        tender.title,
                        style = MaterialTheme.typography.bodyLarge,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    buildString {
                        append(tender.portalName)
                        tender.sector?.let { append("  ·  $it") }
                        tender.noticeType?.takeIf { it.isNotBlank() }?.let { append("  ·  $it") }
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(4.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    // "Deadline not published" is a sentence, not a blank.
                    Text(
                        deadlineText(tender),
                        style = MaterialTheme.typography.bodySmall,
                        color = deadlineColor(tender),
                    )
                    Text(
                        tender.valueDisplay.ifBlank { "value not published" },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (tender.flags.isNotEmpty()) {
                    Spacer(Modifier.height(6.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        tender.flags.take(3).forEach { flag ->
                            StatusChip(flag, StatusColors.warning)
                        }
                    }
                }
                if (!hasLink) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "No link published for this notice",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

private fun deadlineText(tender: Opportunity): String = when {
    tender.closingDate.isNullOrBlank() -> "Deadline not published"
    tender.daysLeft == null -> "Closes ${tender.closingDate}"
    tender.daysLeft <= 0 -> "Closes today (${tender.closingDate})"
    tender.daysLeft == 1 -> "1 day left (${tender.closingDate})"
    else -> "${tender.daysLeft} days left (${tender.closingDate})"
}

@Composable
private fun deadlineColor(tender: Opportunity) = when {
    tender.closingDate.isNullOrBlank() -> MaterialTheme.colorScheme.onSurfaceVariant
    (tender.daysLeft ?: 99) <= 7 -> StatusColors.broken
    (tender.daysLeft ?: 99) <= 21 -> StatusColors.warning
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}

@Composable
private fun scoreColor(score: Double) = when {
    score >= 70 -> StatusColors.ok
    score >= 40 -> StatusColors.warning
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}

@Composable
private fun FilterMenu(
    label: String,
    options: List<String>,
    selected: String?,
    onSelect: (String?) -> Unit,
) {
    var open by remember { mutableStateOf(false) }
    Box {
        AssistChip(
            onClick = { open = true },
            label = { Text(selected?.take(12) ?: label) },
        )
        DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
            DropdownMenuItem(
                text = { Text("All ${label.lowercase()}s") },
                onClick = { onSelect(null); open = false },
            )
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(option) },
                    onClick = { onSelect(option); open = false },
                )
            }
        }
    }
}

/**
 * An empty report, explained.
 *
 * This is the screen the whole app exists for. "0 opportunities" on its own is
 * exactly the ambiguity the backend spent so long removing, and it must not be
 * reintroduced here.
 */
@Composable
private fun NothingToShow(status: String, statusLine: String, portalsBroken: Int) {
    Column(Modifier.fillMaxWidth().padding(24.dp)) {
        Text(
            when (status) {
                "action_needed" -> "Nothing could be read"
                "partial" -> "No opportunities, and the picture is incomplete"
                else -> "No new opportunities"
            },
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            color = StatusColors.forRunStatus(status),
        )
        Spacer(Modifier.height(8.dp))
        Text(statusLine, style = MaterialTheme.typography.bodyMedium)
        if (portalsBroken > 0) {
            Spacer(Modifier.height(8.dp))
            Text(
                "See Portals for which ones failed and why.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun EmptyStart(onRefresh: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(24.dp)) {
        SectionHeader("Nothing downloaded yet")
        Text(
            "This app reads the runs that GitHub Actions already produces. Pull the " +
                "latest finished run to get started -- or use the Run tab to start one.",
            style = MaterialTheme.typography.bodyMedium,
        )
        Spacer(Modifier.height(8.dp))
        TextButton(onClick = onRefresh) { Text("Read the latest run") }
    }
}
