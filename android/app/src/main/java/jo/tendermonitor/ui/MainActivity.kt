package jo.tendermonitor.ui

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Article
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.core.content.FileProvider
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import jo.tendermonitor.TenderMonitorApp
import jo.tendermonitor.ui.screens.FilesScreen
import jo.tendermonitor.ui.screens.PortalHealthScreen
import jo.tendermonitor.ui.screens.ReportScreen
import jo.tendermonitor.ui.screens.RunScreen
import jo.tendermonitor.ui.screens.SettingsScreen
import jo.tendermonitor.ui.theme.JordanTenderTheme
import java.io.File

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val graph = (application as TenderMonitorApp).graph

        val factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = when {
                modelClass.isAssignableFrom(AppViewModel::class.java) ->
                    AppViewModel(graph.reports, graph.settings, graph.settings) as T
                modelClass.isAssignableFrom(SettingsViewModel::class.java) ->
                    SettingsViewModel(graph.settings, graph.settings, graph.client) as T
                else -> throw IllegalArgumentException(modelClass.name)
            }
        }

        setContent {
            JordanTenderTheme {
                AppScaffold(
                    factory = factory,
                    onOpenUrl = ::openUrl,
                    onOpenFile = ::openFile,
                    onShareFile = ::shareFile,
                )
            }
        }
    }

    /**
     * Opens a notice in the browser.
     *
     * A URL that cannot be opened says so rather than doing nothing: a tap
     * that silently fails reads as a broken link, and this codebase's rule is
     * that a dead link is worse than none because it looks checked.
     */
    private fun openUrl(url: String) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(this, "No app on this phone can open $url", Toast.LENGTH_LONG).show()
        } catch (_: Exception) {
            Toast.makeText(this, "That link could not be opened: $url", Toast.LENGTH_LONG).show()
        }
    }

    private fun uriFor(file: File): Uri =
        FileProvider.getUriForFile(this, "$packageName.files", file)

    private fun openFile(file: File) {
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uriFor(file), mimeTypeOf(file))
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        try {
            startActivity(intent)
        } catch (_: ActivityNotFoundException) {
            Toast.makeText(
                this,
                "Nothing on this phone opens ${file.extension.uppercase()} files. " +
                    "Install Word or Excel, or use Share.",
                Toast.LENGTH_LONG,
            ).show()
        }
    }

    private fun shareFile(file: File) {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = mimeTypeOf(file)
            putExtra(Intent.EXTRA_STREAM, uriFor(file))
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        startActivity(Intent.createChooser(intent, "Share ${file.name}"))
    }

    private fun mimeTypeOf(file: File): String = when {
        file.name.endsWith(".docx", true) ->
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        file.name.endsWith(".xlsx", true) ->
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file.name.endsWith(".json", true) -> "application/json"
        else -> "*/*"
    }
}

private enum class Tab(val label: String, val icon: ImageVector) {
    LATEST("Latest", Icons.Filled.Article),
    RUN("Run", Icons.Filled.PlayArrow),
    PORTALS("Portals", Icons.Filled.Dns),
    FILES("Files", Icons.Filled.Folder),
    SETTINGS("Settings", Icons.Filled.Settings),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppScaffold(
    factory: ViewModelProvider.Factory,
    onOpenUrl: (String) -> Unit,
    onOpenFile: (File) -> Unit,
    onShareFile: (File) -> Unit,
) {
    val app: AppViewModel = viewModel(factory = factory)
    val settingsVm: SettingsViewModel = viewModel(factory = factory)

    var tab by remember { mutableStateOf(Tab.LATEST) }

    val reportState by app.report.collectAsState()
    val runState by app.runs.collectAsState()
    val filesState by app.files.collectAsState()
    val settings by settingsVm.settings.collectAsState()
    val fingerprint by settingsVm.fingerprint.collectAsState()
    val verifyResult by settingsVm.verifyResult.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(title = { Text(topBarTitle(tab, settings.repoSlug)) })
        },
        bottomBar = {
            NavigationBar {
                Tab.entries.forEach { entry ->
                    NavigationBarItem(
                        selected = tab == entry,
                        onClick = { tab = entry },
                        icon = { Icon(entry.icon, contentDescription = entry.label) },
                        label = { Text(entry.label) },
                    )
                }
            }
        },
    ) { padding ->
        val modifier = Modifier.padding(padding)
        when (tab) {
            Tab.LATEST -> ReportScreen(
                state = reportState,
                onRefresh = app::refreshLatestReport,
                onOpenUrl = onOpenUrl,
                modifier = modifier,
            )

            Tab.RUN -> RunScreen(
                state = runState,
                onStartRun = app::startRun,
                onRefresh = app::refreshRuns,
                onFollow = app::followRun,
                onOpenUrl = onOpenUrl,
                modifier = modifier,
            )

            Tab.PORTALS -> PortalHealthScreen(
                state = reportState,
                onOpenUrl = onOpenUrl,
                modifier = modifier,
            )

            Tab.FILES -> FilesScreen(
                state = filesState,
                run = runState.watching ?: runState.runs.firstOrNull { it.isFinished },
                onDownload = {
                    (runState.watching ?: runState.runs.firstOrNull { it.isFinished })
                        ?.let(app::downloadFiles)
                },
                onOpen = onOpenFile,
                onShare = onShareFile,
                modifier = modifier,
            )

            Tab.SETTINGS -> SettingsScreen(
                settings = settings,
                tokenFingerprint = fingerprint,
                onSaveToken = settingsVm::saveToken,
                onClearToken = settingsVm::clearToken,
                onSaveSettings = {
                    settingsVm.saveSettings(it)
                    app.refreshSettings()
                },
                onVerifyToken = settingsVm::verify,
                verifyResult = verifyResult,
                modifier = modifier,
            )
        }
    }
}

private fun topBarTitle(tab: Tab, repo: String): String = when (tab) {
    Tab.LATEST -> "Latest report"
    Tab.RUN -> "Run the monitor"
    Tab.PORTALS -> "Portal health"
    Tab.FILES -> "Files"
    Tab.SETTINGS -> repo
}
