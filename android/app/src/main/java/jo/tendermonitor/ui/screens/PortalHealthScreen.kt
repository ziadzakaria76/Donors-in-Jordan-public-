package jo.tendermonitor.ui.screens

import androidx.compose.foundation.clickable
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
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import jo.tendermonitor.data.report.PortalStatus
import jo.tendermonitor.ui.ReportState
import jo.tendermonitor.ui.StatusChip
import jo.tendermonitor.ui.theme.StatusColors

/**
 * Every portal, in full.
 *
 * THIS TABLE IS THE SYSTEM'S HONESTY MECHANISM and it is rendered whole: no
 * "3 portals had problems" roll-up, no hiding the healthy ones behind a
 * filter. The backend learned that a status table people stop reading is a
 * status table that cannot raise an alarm, and a summary is how that starts.
 *
 * Four statuses, deliberately not two:
 *
 *   ok           read successfully. The count may still be 0.
 *   unavailable  could not be read. This is the one that needs action.
 *   unconfigured waiting on something you have to supply (a SAM.gov key,
 *                whose approval takes weeks). Not a fault.
 *   no listing   the source publishes nothing to read. A fact about the
 *                source, established the hard way, not a broken scraper.
 */
@Composable
fun PortalHealthScreen(
    state: ReportState,
    onOpenUrl: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    val report = state.report
    if (report == null) {
        Column(modifier.fillMaxWidth().padding(24.dp)) {
            Text(
                "No run has been read yet, so there is nothing to say about the " +
                    "portals. That is not the same as them being healthy.",
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        return
    }

    val portals = report.portals
    val broken = portals.count { it.isBroken }

    LazyColumn(modifier.fillMaxSize()) {
        item {
            Column(Modifier.padding(16.dp)) {
                Text(
                    "${portals.size} portals",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    if (broken == 0) {
                        "All read successfully. A portal reading 0 read fine and had " +
                            "nothing in scope -- that is different from a failure."
                    } else {
                        "$broken could not be read. Anything they published is missing " +
                            "from this report, and the report cannot tell you what."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = if (broken == 0) MaterialTheme.colorScheme.onSurfaceVariant
                    else StatusColors.broken,
                )
            }
            HorizontalDivider()
        }

        items(portals, key = { it.key }) { portal ->
            PortalRow(portal, onOpenUrl)
            HorizontalDivider()
        }
    }
}

@Composable
private fun PortalRow(portal: PortalStatus, onOpenUrl: (String) -> Unit) {
    val color = StatusColors.forPortalStatus(portal.status)
    val firstUrl = portal.urls.firstOrNull()

    Column(
        Modifier
            .fillMaxWidth()
            .clickable(enabled = firstUrl != null) { firstUrl?.let(onOpenUrl) }
            .padding(horizontal = 16.dp, vertical = 12.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                portal.name,
                style = MaterialTheme.typography.bodyLarge,
                modifier = Modifier.weight(1f),
            )
            Spacer(Modifier.width(8.dp))
            StatusChip(
                text = when (portal.status) {
                    "ok" -> "read"
                    "unavailable" -> "unavailable"
                    "unconfigured" -> "not set up"
                    "no listing" -> "no listing"
                    else -> portal.status
                },
                color = color,
            )
        }

        Spacer(Modifier.height(4.dp))
        Text(
            "Tier ${portal.tier}" +
                (portal.tierLabel.takeIf { it.isNotBlank() }?.let { " · $it" } ?: ""),
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )

        if (portal.isOk) {
            Spacer(Modifier.height(6.dp))
            Text(countSentence(portal), style = MaterialTheme.typography.bodySmall)
            if (portal.layer.isNotBlank()) {
                Text(
                    "Read via the ${portal.layer} layer" +
                        if (portal.quality > 0) {
                            ", quality %.2f".format(portal.quality)
                        } else "",
                    style = MaterialTheme.typography.labelSmall,
                    color = qualityColor(portal.quality),
                )
            }
        }

        if (portal.reason.isNotBlank()) {
            Spacer(Modifier.height(6.dp))
            Text(
                portal.reason,
                style = MaterialTheme.typography.bodySmall,
                color = if (portal.isBroken) StatusColors.broken
                else MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        firstUrl?.let { url ->
            Spacer(Modifier.height(4.dp))
            Text(
                if (portal.isBroken) "Check by hand: $url" else url,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

/**
 * The sentence that made five identical zeroes into five diagnoses.
 *
 * `scanned` is null when a portal never filters -- rendering that as 0 would
 * undo the distinction the backend added it for, so the two cases get two
 * different sentences here.
 */
private fun countSentence(portal: PortalStatus): String {
    val scanned = portal.scanned
    return when {
        // "IN SCOPE", NOT A COUNTRY NAME. This app drives two monitors, and
        // these sentences named Jordan unconditionally -- so a Syria run's
        // Health tab, the screen this file's own header calls the honesty
        // mechanism, reported "85 Jordan notices" over Syrian ones. The report
        // does not carry a country for the run, only per tender, and inventing
        // one here would be the same mistake in a different place. The
        // pipeline's own word for what survived its country gate is "in scope".
        scanned == null && portal.count == 0 ->
            "Read successfully. Nothing in scope, and this portal does not report " +
                "how many it looked at."
        scanned == null ->
            "${portal.count} notice${plural(portal.count)} in scope."
        scanned == portal.count ->
            "${portal.count} notice${plural(portal.count)}, all of them in scope."
        portal.count == 0 ->
            "Read $scanned notice${plural(scanned)}; none in scope. The portal " +
                "worked -- there was simply nothing here."
        else ->
            "${portal.count} in scope of $scanned read " +
                "(${portal.filteredOut} filtered out)."
    }
}

private fun plural(n: Int) = if (n == 1) "" else "s"

@Composable
private fun qualityColor(quality: Double) = when {
    quality <= 0.0 -> MaterialTheme.colorScheme.onSurfaceVariant
    // The backend's own gate. Below it, a result was returned but labelled
    // as not clearing the bar, and that has to be visible here too.
    quality < 0.36 -> StatusColors.warning
    else -> MaterialTheme.colorScheme.onSurfaceVariant
}
