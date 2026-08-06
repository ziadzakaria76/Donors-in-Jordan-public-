package jo.tendermonitor.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Problem
import jo.tendermonitor.ui.theme.StatusColors
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * How a failure is shown: a headline, the detail, and what to do about it.
 *
 * Never a toast. A failure that scrolls away in three seconds is a failure
 * nobody can act on, and this app's whole reason for existing is that a broken
 * monitor should be impossible to miss.
 */
@Composable
fun ProblemCard(
    problem: Problem,
    modifier: Modifier = Modifier,
    onRetry: (() -> Unit)? = null,
) {
    val tone = when (problem.kind) {
        Kind.NO_TOKEN -> StatusColors.unconfigured
        Kind.EXPIRED -> StatusColors.noListing
        Kind.OFFLINE, Kind.RATE_LIMITED, Kind.SERVER -> StatusColors.warning
        else -> StatusColors.broken
    }

    Card(
        modifier = modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp),
        colors = CardDefaults.cardColors(containerColor = tone.copy(alpha = 0.10f)),
    ) {
        Column(Modifier.padding(14.dp)) {
            Text(
                problem.headline,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = tone,
            )
            if (problem.detail.isNotBlank()) {
                Spacer(Modifier.height(6.dp))
                Text(problem.detail, style = MaterialTheme.typography.bodyMedium)
            }
            problem.fixHint?.let { hint ->
                Spacer(Modifier.height(8.dp))
                Text(
                    hint,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            problem.retryAtEpochSeconds?.let { reset ->
                Spacer(Modifier.height(6.dp))
                Text(
                    "Resets at ${formatEpochSeconds(reset)}.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (onRetry != null && problem.isTransient) {
                TextButton(onClick = onRetry) { Text("Try again") }
            }
        }
    }
}

/** A short label with a colour, used for run and portal status alike. */
@Composable
fun StatusChip(text: String, color: Color, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        color = color.copy(alpha = 0.15f),
        contentColor = color,
        shape = MaterialTheme.shapes.small,
    ) {
        Text(
            text,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Medium,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
        )
    }
}

@Composable
fun SectionHeader(text: String, modifier: Modifier = Modifier) {
    Text(
        text,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.SemiBold,
        color = MaterialTheme.colorScheme.primary,
        modifier = modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 4.dp),
    )
}

@Composable
fun LabelledValue(label: String, value: String, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.padding(end = 8.dp),
        )
        Text(value, style = MaterialTheme.typography.bodySmall)
    }
}

private val TIME_FORMAT = SimpleDateFormat("HH:mm", Locale.getDefault())
private val DATE_TIME_FORMAT = SimpleDateFormat("d MMM, HH:mm", Locale.getDefault())

fun formatEpochSeconds(seconds: Long): String = TIME_FORMAT.format(Date(seconds * 1000))

fun formatEpochMillis(millis: Long): String = DATE_TIME_FORMAT.format(Date(millis))

/**
 * GitHub's ISO-8601 timestamps, shown readably.
 *
 * Falls back to the original string rather than to a wrong date: a timestamp
 * this app could not parse is still information, and a silently substituted
 * "now" would be a lie about when a run happened.
 */
fun formatIsoTimestamp(iso: String?): String {
    if (iso.isNullOrBlank()) return "unknown"
    return try {
        val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
            timeZone = java.util.TimeZone.getTimeZone("UTC")
        }
        DATE_TIME_FORMAT.format(parser.parse(iso)!!)
    } catch (_: Exception) {
        iso
    }
}
