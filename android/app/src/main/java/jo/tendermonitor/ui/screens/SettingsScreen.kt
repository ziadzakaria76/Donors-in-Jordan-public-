package jo.tendermonitor.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import jo.tendermonitor.data.settings.AppSettings
import jo.tendermonitor.data.settings.Redact
import jo.tendermonitor.data.settings.TokenAdvice
import jo.tendermonitor.ui.PollStatus
import jo.tendermonitor.ui.SectionHeader
import jo.tendermonitor.ui.theme.StatusColors
import jo.tendermonitor.work.PollPolicy

/**
 * Token and repository.
 *
 * THE TOKEN IS NEVER SHOWN BACK. Once saved it is described -- its last four
 * characters and its length -- and never rendered in full, because a
 * credential on screen is a credential in a screenshot, in a screen recording,
 * and in whatever is looking over your shoulder.
 */
@Composable
fun SettingsScreen(
    settings: AppSettings,
    tokenFingerprint: String,
    onSaveToken: (String) -> Unit,
    onClearToken: () -> Unit,
    onSaveSettings: (AppSettings) -> Unit,
    onVerifyToken: () -> Unit,
    verifyResult: String?,
    pollStatus: PollStatus,
    nowMillis: Long,
    notificationsAllowed: Boolean,
    onRequestNotificationPermission: (() -> Unit)?,
    modifier: Modifier = Modifier,
) {
    var token by remember { mutableStateOf("") }
    var owner by remember(settings) { mutableStateOf(settings.repoOwner) }
    var repo by remember(settings) { mutableStateOf(settings.repoName) }
    var workflow by remember(settings) { mutableStateOf(settings.workflowFile) }

    val warning = TokenAdvice.warning(token)

    Column(modifier.fillMaxSize().verticalScroll(rememberScrollState())) {

        SectionHeader("GitHub token")
        Card(Modifier.fillMaxWidth().padding(12.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text(
                    "Currently: $tokenFingerprint",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = token,
                    onValueChange = { token = it },
                    label = { Text("Paste a fine-grained token") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    modifier = Modifier.fillMaxWidth(),
                )
                warning?.let {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        it,
                        style = MaterialTheme.typography.bodySmall,
                        color = StatusColors.warning,
                    )
                }
                Spacer(Modifier.height(10.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Button(
                        onClick = { onSaveToken(token); token = "" },
                        enabled = token.isNotBlank(),
                    ) { Text("Save") }
                    Spacer(Modifier.height(0.dp))
                    TextButton(onClick = onVerifyToken) { Text("Check it works") }
                    TextButton(onClick = onClearToken) { Text("Remove") }
                }
                verifyResult?.let {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        // Belt and braces: this string has already been through
                        // Redact on the way here.
                        Redact.scrub(it),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                Spacer(Modifier.height(12.dp))
                HorizontalDivider()
                Spacer(Modifier.height(10.dp))
                Text(
                    "The exact permissions this app needs",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "A fine-grained personal access token, scoped to this ONE " +
                        "repository, with:\n" +
                        "  • Actions: Read and write — to start a run and read its files\n" +
                        "  • Contents: Read and write — to edit the portal list\n" +
                        "\nNothing else. No organisation permissions, no other " +
                        "repositories. If you only want to read runs and never edit " +
                        "portals, Contents can be Read-only.",
                    style = MaterialTheme.typography.bodySmall,
                )
                Spacer(Modifier.height(8.dp))
                Text(
                    "It is stored in EncryptedSharedPreferences, whose key is held by " +
                        "the Android Keystore. It is not in the APK, not in any log " +
                        "line, and it is stripped out of every error this app shows.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        SectionHeader("Repository")
        Card(Modifier.fillMaxWidth().padding(12.dp)) {
            Column(Modifier.padding(14.dp)) {
                OutlinedTextField(
                    value = owner,
                    onValueChange = { owner = it },
                    label = { Text("Owner") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = repo,
                    onValueChange = { repo = it },
                    label = { Text("Repository") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(
                    value = workflow,
                    onValueChange = { workflow = it },
                    label = { Text("Workflow file") },
                    supportingText = { Text("The file name, e.g. monitor.yml") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(10.dp))
                Button(
                    onClick = {
                        onSaveSettings(
                            settings.copy(
                                repoOwner = owner.trim(),
                                repoName = repo.trim(),
                                workflowFile = workflow.trim(),
                            )
                        )
                    },
                    enabled = owner.isNotBlank() && repo.isNotBlank() && workflow.isNotBlank(),
                ) { Text("Save") }
            }
        }

        SectionHeader("Background checks")
        Card(Modifier.fillMaxWidth().padding(12.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text(
                    "The monitor runs on GitHub's servers on a weekday schedule " +
                        "whether or not this phone is awake. These checks only ask " +
                        "whether a run has finished, and tell you what it found.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                Spacer(Modifier.height(12.dp))
                Text("How often", style = MaterialTheme.typography.labelLarge)
                Column {
                    PollPolicy.INTERVALS.forEach { (minutes, label) ->
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            RadioButton(
                                selected = settings.pollMinutes == minutes,
                                onClick = { onSaveSettings(settings.copy(pollMinutes = minutes)) },
                            )
                            Text(label, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
                Text(
                    PollPolicy.describeCost(settings.pollMinutes),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(4.dp))
                Text(
                    "Android decides when a background job actually runs. It will " +
                        "be at least this long and can be considerably more if the " +
                        "phone is asleep — this is an interval, not an appointment.",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )

                Spacer(Modifier.height(14.dp))
                HorizontalDivider()
                Spacer(Modifier.height(10.dp))

                SwitchRow(
                    checked = settings.notifyOnResults,
                    onChange = { onSaveSettings(settings.copy(notifyOnResults = it)) },
                    title = "Tell me about results",
                    detail = "\"12 new opportunities\", and \"no new opportunities " +
                        "— all 13 portals read\", which is a different thing and " +
                        "arrives as a different sentence.",
                )
                SwitchRow(
                    checked = settings.notifyOnFailures,
                    onChange = { onSaveSettings(settings.copy(notifyOnFailures = it)) },
                    title = "Tell me when something is wrong",
                    detail = "Portals unreachable, or this app unable to check at " +
                        "all. Sent on a separate, higher-priority channel so you " +
                        "can make it noisier than results in Android's settings — " +
                        "or quieten results without quietening this.",
                )
                SwitchRow(
                    checked = settings.pollOnMetered,
                    onChange = { onSaveSettings(settings.copy(pollOnMetered = it)) },
                    title = "Check on mobile data too",
                    detail = "Off by default. Checking hourly over mobile data to " +
                        "find out that nothing changed spends your allowance " +
                        "without asking. On Wi-Fi only, the checks are free.",
                )

                if (!notificationsAllowed) {
                    Spacer(Modifier.height(10.dp))
                    Text(
                        "Android is not allowing this app to post notifications, so " +
                            "nothing above will reach you. The checks still run and " +
                            "the app still updates when you open it.",
                        style = MaterialTheme.typography.bodySmall,
                        color = StatusColors.warning,
                    )
                    onRequestNotificationPermission?.let { request ->
                        TextButton(onClick = request) { Text("Allow notifications") }
                    }
                }
            }
        }

        SectionHeader("Last check")
        Card(Modifier.fillMaxWidth().padding(12.dp)) {
            Column(Modifier.padding(14.dp)) {
                // The line that makes silence legible. With nothing here, "no
                // notifications this week" means either no news or no checks,
                // and those are the two states this whole system exists to
                // keep apart.
                Text(
                    PollPolicy.describeLastCheck(pollStatus.lastAttemptMillis, nowMillis),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                )
                if (pollStatus.lastNote.isNotBlank()) {
                    Spacer(Modifier.height(4.dp))
                    Text(pollStatus.lastNote, style = MaterialTheme.typography.bodySmall)
                }
                if (pollStatus.consecutiveFailures > 0) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "${pollStatus.consecutiveFailures} check(s) in a row have " +
                            "failed. Until one succeeds, no news here is not the " +
                            "same as no news.",
                        style = MaterialTheme.typography.bodySmall,
                        color = StatusColors.warning,
                    )
                }
                if (pollStatus.lastNotifiedRunId > 0) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Last run announced: #${pollStatus.lastNotifiedRunId}.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (settings.pollMinutes <= 0) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Background checks are off, so this will not change.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun SwitchRow(
    checked: Boolean,
    onChange: (Boolean) -> Unit,
    title: String,
    detail: String,
) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 6.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Switch(checked = checked, onCheckedChange = onChange)
        Spacer(Modifier.height(0.dp))
        Column(Modifier.padding(start = 12.dp)) {
            Text(title, style = MaterialTheme.typography.bodyMedium)
            Text(
                detail,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
