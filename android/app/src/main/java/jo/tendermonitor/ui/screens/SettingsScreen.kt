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
import jo.tendermonitor.ui.SectionHeader
import jo.tendermonitor.ui.theme.StatusColors

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

        SectionHeader("Notifications")
        Card(Modifier.fillMaxWidth().padding(12.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text(
                    "Background checks and notifications are Phase 3 and are not " +
                        "wired up yet. Nothing on this screen turns them on, and the " +
                        "app does not poll in the background today.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        Spacer(Modifier.height(24.dp))
    }
}
