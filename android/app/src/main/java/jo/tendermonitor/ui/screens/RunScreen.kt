package jo.tendermonitor.ui.screens

import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import jo.tendermonitor.data.github.WorkflowRun
import jo.tendermonitor.ui.ProblemCard
import jo.tendermonitor.ui.RunState
import jo.tendermonitor.ui.SectionHeader
import jo.tendermonitor.ui.StatusChip
import jo.tendermonitor.ui.formatIsoTimestamp
import jo.tendermonitor.ui.theme.StatusColors

/**
 * The workflow's real inputs, spelled exactly as monitor.yml declares them.
 *
 * `workflow_dispatch` matches choice inputs by their literal string. A typo
 * here is a 422 from GitHub at the moment you tap Run, so these are constants
 * rather than anything constructed.
 */
object WorkflowInputs {
    const val SCOPE_ALL = "everything currently open"
    const val SCOPE_NEW = "only what is new since the last run"
    const val MODE_REPORT = "produce the report"
    const val MODE_DIAGNOSE = "diagnose portals (--capture)"
}

@Composable
fun RunScreen(
    state: RunState,
    onStartRun: (scope: String, portals: String, mode: String) -> Unit,
    onRefresh: () -> Unit,
    onRefreshList: () -> Unit,
    onFollow: (Long) -> Unit,
    onOpenUrl: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var scopeAll by remember { mutableStateOf(true) }
    var diagnose by remember { mutableStateOf(false) }
    var portals by remember { mutableStateOf("") }

    LazyColumn(modifier.fillMaxSize()) {
        item {
            Card(Modifier.fillMaxWidth().padding(12.dp)) {
                Column(Modifier.padding(14.dp)) {
                    Text("Start a run", style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "The scrapers run on GitHub's servers, not on this phone. " +
                            "Closing the app does not stop a run.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )

                    Spacer(Modifier.height(12.dp))
                    Text("What to report", style = MaterialTheme.typography.labelLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(
                            selected = scopeAll,
                            onClick = { scopeAll = true },
                            label = { Text("Everything open") },
                        )
                        FilterChip(
                            selected = !scopeAll,
                            onClick = { scopeAll = false },
                            label = { Text("Only what is new") },
                        )
                    }
                    Text(
                        if (scopeAll) {
                            "The whole current pipeline. Best when you are looking now."
                        } else {
                            "Only notices not reported before. What the schedule does."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )

                    Spacer(Modifier.height(12.dp))
                    Text("What to do", style = MaterialTheme.typography.labelLarge)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        FilterChip(
                            selected = !diagnose,
                            onClick = { diagnose = false },
                            label = { Text("Report") },
                        )
                        FilterChip(
                            selected = diagnose,
                            onClick = { diagnose = true },
                            label = { Text("Diagnose") },
                        )
                    }
                    if (diagnose) {
                        Text(
                            "Fetches each portal's live pages and reports what every " +
                                "extraction layer found. It writes no report, so the " +
                                "Latest tab will not change.",
                            style = MaterialTheme.typography.bodySmall,
                            color = StatusColors.warning,
                        )
                    }

                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = portals,
                        onValueChange = { portals = it },
                        label = { Text("Limit to portals (optional)") },
                        placeholder = { Text("ungm worldbank giz") },
                        supportingText = {
                            Text("Space-separated keys. Blank runs all of them.")
                        },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                        modifier = Modifier.fillMaxWidth(),
                    )

                    Spacer(Modifier.height(12.dp))
                    Button(
                        onClick = {
                            onStartRun(
                                if (scopeAll) WorkflowInputs.SCOPE_ALL
                                else WorkflowInputs.SCOPE_NEW,
                                portals,
                                if (diagnose) WorkflowInputs.MODE_DIAGNOSE
                                else WorkflowInputs.MODE_REPORT,
                            )
                        },
                        enabled = !state.dispatching && !state.awaitingNewRun,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(if (state.dispatching) "Asking GitHub..." else "Run")
                    }
                }
            }
        }

        state.problem?.let { problem ->
            item { ProblemCard(problem, onRetry = onRefresh) }
        }

        if (state.awaitingNewRun || state.note != null) {
            item {
                Card(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)) {
                    Row(
                        Modifier.padding(14.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        if (state.awaitingNewRun) {
                            CircularProgressIndicator(
                                Modifier.width(18.dp).height(18.dp), strokeWidth = 2.dp,
                            )
                            Spacer(Modifier.width(10.dp))
                        }
                        Text(
                            state.note ?: "Waiting for the run to appear...",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        }

        state.watching?.let { run ->
            item {
                SectionHeader("Watching")
                RunRow(run, onOpenUrl = onOpenUrl, onFollow = onFollow, highlight = true)
                HorizontalDivider()
            }
        }

        item {
            Row(verticalAlignment = Alignment.CenterVertically) {
                SectionHeader("Recent runs")
                Spacer(Modifier.weight(1f))
                if (state.loading) {
                    CircularProgressIndicator(
                        Modifier.width(16.dp).height(16.dp), strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.width(16.dp))
                } else {
                    TextButton(onClick = onRefreshList) { Text("Refresh") }
                }
            }
        }

        // Only after a listing has actually been attempted. Before that, an
        // empty list means "we have not looked", and printing a diagnosis for
        // a state nobody has checked is exactly the kind of plausible wrong
        // answer this codebase keeps removing.
        if (state.runs.isEmpty() && !state.loading && state.loaded) {
            item {
                Text(
                    "No runs found for this workflow. If that is a surprise, check the " +
                        "repository and workflow file in Settings -- GitHub answers 404 " +
                        "for a workflow that does not exist and for one your token " +
                        "cannot see, so the app cannot tell you which.",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(16.dp),
                )
            }
        }

        items(state.runs, key = { it.id }) { run ->
            RunRow(run, onOpenUrl = onOpenUrl, onFollow = onFollow)
            HorizontalDivider()
        }
    }
}

@Composable
private fun RunRow(
    run: WorkflowRun,
    onOpenUrl: (String) -> Unit,
    onFollow: (Long) -> Unit,
    highlight: Boolean = false,
) {
    Column(
        Modifier
            .fillMaxWidth()
            .clickable { if (run.isRunning) onFollow(run.id) else run.htmlUrl?.let(onOpenUrl) }
            .padding(horizontal = 16.dp, vertical = 12.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "#${run.runNumber}",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = if (highlight) FontWeight.Bold else FontWeight.Normal,
                modifier = Modifier.width(56.dp),
            )
            Column(Modifier.weight(1f)) {
                Text(
                    runDescription(run),
                    style = MaterialTheme.typography.bodyMedium,
                )
                Text(
                    "${run.event ?: "unknown trigger"} · " +
                        formatIsoTimestamp(run.createdAt),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            StatusChip(text = runLabel(run), color = runColor(run))
        }
    }
}

/**
 * A run's outcome in words.
 *
 * "failure" is deliberately not called "error": the monitor exits non-zero on
 * purpose when every portal is unreachable, so a failed run is often the
 * report you most need to read rather than a broken build.
 */
private fun runDescription(run: WorkflowRun): String = when {
    run.isRunning -> "Running now"
    run.conclusion == "success" -> "Finished cleanly"
    run.conclusion == "failure" ->
        "Finished with a failure -- often a deliberate one: the monitor exits " +
            "non-zero when it could not read its sources"
    run.conclusion == "cancelled" -> "Cancelled"
    run.conclusion == null -> "Finished, with no conclusion reported"
    else -> "Finished: ${run.conclusion}"
}

private fun runLabel(run: WorkflowRun): String = when {
    run.status == "queued" -> "queued"
    run.isRunning -> "running"
    else -> run.conclusion ?: "done"
}

private fun runColor(run: WorkflowRun) = when {
    run.isRunning -> StatusColors.warning
    run.conclusion == "success" -> StatusColors.ok
    run.conclusion == "failure" -> StatusColors.broken
    else -> StatusColors.noListing
}
