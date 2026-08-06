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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
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
import jo.tendermonitor.data.portals.PortalsFile
import jo.tendermonitor.ui.PortalsState
import jo.tendermonitor.ui.ProblemCard
import jo.tendermonitor.ui.SectionHeader
import jo.tendermonitor.ui.StatusChip
import jo.tendermonitor.ui.theme.StatusColors

/**
 * Managing the portal list.
 *
 * Every change here is a commit to the repository, and the screen says so
 * before and after: a toggle is not a local preference, it changes what the
 * monitor polls tomorrow morning for everyone reading the report.
 */
@Composable
fun PortalsScreen(
    state: PortalsState,
    onReload: () -> Unit,
    onToggle: (PortalsFile.Entry, Boolean) -> Unit,
    onRemove: (PortalsFile.Entry) -> Unit,
    onAdd: () -> Unit,
    onOpenUrl: (String) -> Unit,
    onDismissCommit: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var confirmRemoval by remember { mutableStateOf<PortalsFile.Entry?>(null) }

    confirmRemoval?.let { entry ->
        AlertDialog(
            onDismissRequest = { confirmRemoval = null },
            title = { Text("Remove ${entry.name}?") },
            text = {
                Text(
                    "This commits a change to portals.json that deletes the " +
                        "entry, including its ${entry.urls.size} URL" +
                        "${if (entry.urls.size == 1) "" else "s"}" +
                        (if (entry.selectors.isNotEmpty()) {
                            " and ${entry.selectors.size} selector hints"
                        } else "") +
                        ".\n\nIf it is only temporarily not worth polling, " +
                        "switch it off instead — that keeps everything and " +
                        "puts the decision on the record."
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    onRemove(entry)
                    confirmRemoval = null
                }) { Text("Remove") }
            },
            dismissButton = {
                TextButton(onClick = { confirmRemoval = null }) { Text("Cancel") }
            },
        )
    }

    LazyColumn(modifier.fillMaxSize()) {
        item {
            Card(Modifier.fillMaxWidth().padding(12.dp)) {
                Column(Modifier.padding(14.dp)) {
                    Text(
                        "The portal list",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "Every change here is a commit to portals.json in the " +
                            "repository. It takes effect on the next run.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(10.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = onAdd, enabled = state.loaded) {
                            Text("Add a portal")
                        }
                        TextButton(onClick = onReload) { Text("Reload") }
                    }
                }
            }
        }

        state.lastCommit?.let { commit ->
            item {
                Card(
                    Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
                    colors = CardDefaults.cardColors(
                        containerColor = StatusColors.ok.copy(alpha = 0.10f),
                    ),
                ) {
                    Column(Modifier.padding(14.dp)) {
                        Text(
                            "Committed",
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = StatusColors.ok,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            commit.message.lineSequence().first(),
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Spacer(Modifier.height(4.dp))
                        Text(
                            commit.sha.take(8),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        Row {
                            if (commit.url.isNotBlank()) {
                                TextButton(onClick = { onOpenUrl(commit.url) }) {
                                    Text("View the commit")
                                }
                            }
                            TextButton(onClick = onDismissCommit) { Text("Dismiss") }
                        }
                    }
                }
            }
        }

        state.problem?.let { problem ->
            item { ProblemCard(problem, onRetry = onReload) }
        }

        if (state.loading && state.entries.isEmpty()) {
            item {
                Row(
                    Modifier.fillMaxWidth().padding(24.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    CircularProgressIndicator(
                        Modifier.width(18.dp).height(18.dp), strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.width(10.dp))
                    Text("Reading portals.json...",
                         style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        if (state.entries.isNotEmpty()) {
            item {
                SectionHeader("${state.entries.size} portals · " +
                    "${state.entries.count { it.enabled }} switched on")
            }
        }

        items(state.entries, key = { it.key }) { entry ->
            PortalEntryRow(
                entry = entry,
                busy = state.busyKey == entry.key,
                onToggle = { onToggle(entry, it) },
                onRemove = { confirmRemoval = entry },
                onOpenUrl = onOpenUrl,
            )
            HorizontalDivider()
        }

        if (state.loaded) {
            item {
                Text(
                    "A portal added here goes through the same six-layer " +
                        "cascade as every other data-only portal. If it stops " +
                        "reading it reports as unavailable with a diagnosed " +
                        "reason, like any other portal — it cannot break the run.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(16.dp),
                )
            }
        }
    }
}

@Composable
private fun PortalEntryRow(
    entry: PortalsFile.Entry,
    busy: Boolean,
    onToggle: (Boolean) -> Unit,
    onRemove: () -> Unit,
    onOpenUrl: (String) -> Unit,
) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(entry.name, style = MaterialTheme.typography.bodyLarge)
                Text(
                    "${entry.key} · tier ${entry.tier}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (busy) {
                CircularProgressIndicator(
                    Modifier.width(20.dp).height(20.dp), strokeWidth = 2.dp,
                )
            } else {
                Switch(checked = entry.enabled, onCheckedChange = onToggle)
            }
        }

        Spacer(Modifier.height(6.dp))
        entry.urls.forEach { url ->
            Text(
                url,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(vertical = 1.dp),
            )
        }

        if (entry.isCodeBacked) {
            Spacer(Modifier.height(6.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                StatusChip("code: ${entry.module}.py", StatusColors.unconfigured)
            }
            Text(
                // Say plainly which fields the file cannot control, rather
                // than offering an edit that would be rejected on load.
                "Its extraction lives in code, not in this file" +
                    (if (entry.codeOwned.isNotEmpty()) {
                        " (${entry.codeOwned.joinToString()})"
                    } else "") +
                    ". You can switch it on or off from here; changing how it " +
                    "reads needs an editor.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier.padding(top = 4.dp),
            )
        }

        if (entry.noListingReason.isNotBlank()) {
            Spacer(Modifier.height(6.dp))
            Text(
                "Declared quiet: ${entry.noListingReason}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (!entry.enabled) {
            Spacer(Modifier.height(6.dp))
            Text(
                "Switched off. It is not polled and does not appear in the " +
                    "portal status table — so its absence from the report is " +
                    "not a failure and will not be reported as one.",
                style = MaterialTheme.typography.labelSmall,
                color = StatusColors.warning,
            )
        }

        Spacer(Modifier.height(4.dp))
        Row {
            entry.urls.firstOrNull()?.let { url ->
                TextButton(onClick = { onOpenUrl(url) }) { Text("Open") }
            }
            TextButton(onClick = onRemove, enabled = !busy) { Text("Remove") }
        }
    }
}
