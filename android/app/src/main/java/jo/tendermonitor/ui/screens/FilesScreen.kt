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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import jo.tendermonitor.data.github.WorkflowRun
import jo.tendermonitor.ui.FilesState
import jo.tendermonitor.ui.ProblemCard
import java.io.File

/**
 * The Word and Excel packs, downloaded and handed to whatever opens them.
 *
 * The failure that matters here is expiry. GitHub keeps run artifacts for 90
 * days and then deletes them; the API answers 410 and the artifact is flagged
 * `expired`. "Download failed" would send someone looking for a network
 * problem that does not exist, so that case gets its own sentence all the way
 * up from the repository.
 */
@Composable
fun FilesScreen(
    state: FilesState,
    run: WorkflowRun?,
    onDownload: () -> Unit,
    onOpen: (File) -> Unit,
    onShare: (File) -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(modifier.fillMaxSize()) {
        item {
            Card(Modifier.fillMaxWidth().padding(12.dp)) {
                Column(Modifier.padding(14.dp)) {
                    Text(
                        "Report pack",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        if (run == null) {
                            "No run selected yet. Read a run on the Latest tab first."
                        } else {
                            "Run #${run.runNumber}. The Word pack is the bid review " +
                                "document; the Excel file is the working pipeline."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Spacer(Modifier.height(12.dp))
                    Button(
                        onClick = onDownload,
                        enabled = run != null && !state.downloading,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        if (state.downloading) {
                            CircularProgressIndicator(
                                Modifier.width(16.dp).height(16.dp), strokeWidth = 2.dp,
                            )
                            Spacer(Modifier.width(8.dp))
                        }
                        Text(if (state.downloading) "Downloading..." else "Download the files")
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Artifacts are kept for 90 days. After that GitHub deletes " +
                            "them and there is nothing to download -- which the app " +
                            "will say plainly rather than reporting a failure.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        state.problem?.let { problem ->
            item { ProblemCard(problem, onRetry = onDownload) }
        }

        if (state.files.isNotEmpty()) {
            item {
                Text(
                    "${state.files.size} file(s) on this phone",
                    style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.padding(16.dp),
                )
                HorizontalDivider()
            }
        }

        items(state.files, key = { it.absolutePath }) { file ->
            FileRow(file, onOpen = onOpen, onShare = onShare)
            HorizontalDivider()
        }
    }
}

@Composable
private fun FileRow(file: File, onOpen: (File) -> Unit, onShare: (File) -> Unit) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable { onOpen(file) }
            .padding(horizontal = 16.dp, vertical = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f)) {
            Text(file.name, style = MaterialTheme.typography.bodyMedium)
            Text(
                "${describeKind(file.name)} · ${humanSize(file.length())}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Text(
            "Share",
            style = MaterialTheme.typography.labelLarge,
            color = MaterialTheme.colorScheme.primary,
            modifier = Modifier.clickable { onShare(file) }.padding(8.dp),
        )
    }
}

private fun describeKind(name: String): String = when {
    name.endsWith(".docx", true) -> "Word bid-review pack"
    name.endsWith(".xlsx", true) -> "Excel working file"
    name.endsWith(".json", true) -> "The report this app reads"
    else -> "File"
}

private fun humanSize(bytes: Long): String = when {
    bytes >= 1_048_576 -> "%.1f MB".format(bytes / 1_048_576.0)
    bytes >= 1024 -> "${bytes / 1024} KB"
    else -> "$bytes bytes"
}
