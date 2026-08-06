package jo.tendermonitor.ui

import android.content.ActivityNotFoundException
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Article
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import jo.tendermonitor.ui.screens.AddPortalScreen
import jo.tendermonitor.ui.screens.FilesScreen
import jo.tendermonitor.ui.screens.PortalHealthScreen
import jo.tendermonitor.ui.screens.PortalsScreen
import jo.tendermonitor.ui.screens.ReportScreen
import jo.tendermonitor.ui.screens.RunScreen
import jo.tendermonitor.ui.screens.SettingsScreen
import jo.tendermonitor.ui.theme.JordanTenderTheme
import jo.tendermonitor.work.Notifier
import jo.tendermonitor.work.PollScheduler
import jo.tendermonitor.work.RunNotice
import java.io.File

class MainActivity : ComponentActivity() {

    private val notificationPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { /* Either way the app works; only the notifications differ. */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val graph = (application as TenderMonitorApp).graph
        val notifier = Notifier(this)

        val factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = when {
                modelClass.isAssignableFrom(AppViewModel::class.java) ->
                    AppViewModel(graph.reports, graph.settings, graph.settings) as T
                modelClass.isAssignableFrom(SettingsViewModel::class.java) ->
                    SettingsViewModel(
                        graph.settings, graph.settings, graph.client, graph.pollState,
                    ) { updated -> PollScheduler.apply(applicationContext, updated) } as T
                modelClass.isAssignableFrom(PortalsViewModel::class.java) ->
                    PortalsViewModel(graph.portals) as T
                else -> throw IllegalArgumentException(modelClass.name)
            }
        }

        setContent {
            JordanTenderTheme {
                AppScaffold(
                    factory = factory,
                    startTab = destinationFrom(intent),
                    onOpenUrl = ::openUrl,
                    onOpenFile = ::openFile,
                    onShareFile = ::shareFile,
                    notificationsAllowed = notifier::canPost,
                    onRequestNotificationPermission = ::askForNotifications,
                )
            }
        }
    }

    /**
     * Where a tapped notification should land.
     *
     * A notification about three unreachable portals that opened the
     * opportunity list would be worse than one that opened nothing: it would
     * show a short report and no reason for it.
     */
    private fun destinationFrom(intent: Intent?): String? =
        intent?.getStringExtra(Notifier.EXTRA_DESTINATION)

    private fun askForNotifications() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
        val granted = ContextCompat.checkSelfPermission(
            this, android.Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
        if (!granted) {
            notificationPermission.launch(android.Manifest.permission.POST_NOTIFICATIONS)
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
    HEALTH("Health", Icons.Filled.Dns),
    PORTALS("Portals", Icons.Filled.Tune),
    FILES("Files", Icons.Filled.Folder),
    SETTINGS("Settings", Icons.Filled.Settings),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AppScaffold(
    factory: ViewModelProvider.Factory,
    startTab: String?,
    onOpenUrl: (String) -> Unit,
    onOpenFile: (File) -> Unit,
    onShareFile: (File) -> Unit,
    /**
     * Re-read rather than passed as a value.
     *
     * It was a Boolean captured once in onCreate, so granting the permission
     * left "Android is not allowing notifications" on screen until the app was
     * restarted -- a warning that outlives the thing it warns about teaches
     * people to ignore warnings.
     */
    notificationsAllowed: () -> Boolean,
    onRequestNotificationPermission: () -> Unit,
) {
    val app: AppViewModel = viewModel(factory = factory)
    val settingsVm: SettingsViewModel = viewModel(factory = factory)
    val portalsVm: PortalsViewModel = viewModel(factory = factory)

    var tab by remember {
        mutableStateOf(
            when (startTab) {
                RunNotice.Destination.HEALTH.name -> Tab.HEALTH
                RunNotice.Destination.SETTINGS.name -> Tab.SETTINGS
                else -> Tab.LATEST
            }
        )
    }
    // The Add form is a sub-screen of Portals rather than a tab: it is a
    // task with a beginning and an end, and a tab you can wander away from
    // mid-edit would lose a tested candidate without saying so.
    var addingPortal by remember { mutableStateOf(false) }

    val reportState by app.report.collectAsState()
    val runState by app.runs.collectAsState()
    val filesState by app.files.collectAsState()
    val settings by settingsVm.settings.collectAsState()
    val portalsState by portalsVm.state.collectAsState()
    val addState by portalsVm.add.collectAsState()
    val fingerprint by settingsVm.fingerprint.collectAsState()
    val verifyResult by settingsVm.verifyResult.collectAsState()
    val pollStatus by settingsVm.pollStatus.collectAsState()
    // Keyed on the tab, so returning to Settings after granting the permission
    // re-checks it.
    val canNotify = remember(tab) { notificationsAllowed() }

    // Load a tab's data the first time it is opened, and not again.
    //
    // Without this the Run tab printed "No runs found for this workflow" and
    // the Portals tab sat empty with its Add button disabled -- both of them
    // stating a conclusion before anything had been looked at, which is the
    // one thing this app is not allowed to do. Guarded on the loaded flag
    // rather than fired on every tab switch, so browsing between tabs does not
    // spend a request each time.
    LaunchedEffect(tab, portalsState.loaded, runState.loaded) {
        when (tab) {
            Tab.LATEST ->
                if (reportState.report == null && !reportState.loading) {
                    app.refreshLatestReport()
                }
            // Files needs a run to download from, and it is reached without
            // going through Run -- so it loads the list too, or the screen
            // says "no run selected yet" about a list nobody has fetched.
            Tab.RUN, Tab.FILES ->
                if (!runState.loaded && !runState.loading) app.refreshRuns()
            Tab.PORTALS ->
                if (!portalsState.loaded && !portalsState.loading) portalsVm.load()
            // Local reads, so this is free and can happen every time. It has
            // to: "last checked 20 minutes ago" is only true if it is re-read.
            Tab.SETTINGS -> settingsVm.refreshPollStatus()
            else -> Unit
        }
    }

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
                onRefreshList = app::refreshRuns,
                onStartRun = app::startRun,
                onRefresh = app::refreshRuns,
                onFollow = app::followRun,
                onOpenUrl = onOpenUrl,
                modifier = modifier,
            )

            Tab.HEALTH -> PortalHealthScreen(
                state = reportState,
                onOpenUrl = onOpenUrl,
                modifier = modifier,
            )

            Tab.PORTALS -> if (addingPortal) {
                AddPortalScreen(
                    state = addState,
                    onChange = portalsVm::updateAdd,
                    onTest = portalsVm::test,
                    onSave = portalsVm::save,
                    onCancel = { portalsVm.resetAdd(); addingPortal = false },
                    onOpenUrl = onOpenUrl,
                    modifier = modifier,
                )
            } else {
                PortalsScreen(
                    state = portalsState,
                    onReload = portalsVm::load,
                    onToggle = portalsVm::setEnabled,
                    onRemove = portalsVm::remove,
                    onAdd = { addingPortal = true },
                    onOpenUrl = onOpenUrl,
                    onDismissCommit = portalsVm::dismissCommit,
                    modifier = modifier,
                )
            }

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
                pollStatus = pollStatus,
                nowMillis = System.currentTimeMillis(),
                notificationsAllowed = canNotify,
                onRequestNotificationPermission = onRequestNotificationPermission,
                modifier = modifier,
            )
        }
    }
}

private fun topBarTitle(tab: Tab, repo: String): String = when (tab) {
    Tab.LATEST -> "Latest report"
    Tab.RUN -> "Run the monitor"
    Tab.HEALTH -> "Portal health"
    Tab.PORTALS -> "Manage portals"
    Tab.FILES -> "Files"
    Tab.SETTINGS -> repo
}
