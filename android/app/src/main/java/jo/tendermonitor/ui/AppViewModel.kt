package jo.tendermonitor.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Outcome
import jo.tendermonitor.data.Problem
import jo.tendermonitor.data.ReportRepository
import jo.tendermonitor.data.db.CachedReport
import jo.tendermonitor.data.github.WorkflowRun
import jo.tendermonitor.data.report.Report
import jo.tendermonitor.data.report.ReportParser
import jo.tendermonitor.data.settings.AppSettings
import jo.tendermonitor.data.settings.SettingsStore
import jo.tendermonitor.data.settings.TokenStore
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File

/** How the report currently on screen got there. */
enum class Provenance { NONE, CACHE, NETWORK }

data class ReportState(
    val report: Report? = null,
    val cached: CachedReport? = null,
    val provenance: Provenance = Provenance.NONE,
    val loading: Boolean = false,
    val problem: Problem? = null,
) {
    /**
     * True when there is a report to read AND a problem to show. Both are
     * shown: a stale report with a banner beats an error page that hides the
     * only data on the device.
     */
    val hasStaleData: Boolean get() = report != null && problem != null
}

data class RunState(
    val runs: List<WorkflowRun> = emptyList(),
    val watching: WorkflowRun? = null,
    /** Set between dispatching and the new run appearing. */
    val awaitingNewRun: Boolean = false,
    val dispatching: Boolean = false,
    val loading: Boolean = false,
    val problem: Problem? = null,
    val note: String? = null,
)

data class FilesState(
    val files: List<File> = emptyList(),
    val downloading: Boolean = false,
    val problem: Problem? = null,
)

/**
 * One view model for the three screens that all talk about the same run.
 *
 * Splitting them would mean three copies of "which run are we looking at",
 * and the bug that follows is the Files screen downloading a different run
 * from the one the report came from.
 */
class AppViewModel(
    private val repository: ReportRepository,
    private val tokens: TokenStore,
    private val settingsStore: SettingsStore,
) : ViewModel() {

    private val _report = MutableStateFlow(ReportState())
    val report: StateFlow<ReportState> = _report.asStateFlow()

    private val _runs = MutableStateFlow(RunState())
    val runs: StateFlow<RunState> = _runs.asStateFlow()

    private val _files = MutableStateFlow(FilesState())
    val files: StateFlow<FilesState> = _files.asStateFlow()

    private val _settings = MutableStateFlow(AppSettings())
    val settings: StateFlow<AppSettings> = _settings.asStateFlow()

    init {
        _settings.value = settingsStore.settings()
        observeCache()
    }

    /**
     * Show whatever is on disk immediately, before any network call.
     *
     * This is the offline-first promise, and it is also what makes the app
     * usable at all on a bad connection: the report you read this morning is
     * still the report, and it says when it was stored so you can judge it.
     */
    private fun observeCache() {
        viewModelScope.launch {
            repository.cachedLatest().collect { cached ->
                if (cached == null) return@collect
                if (_report.value.provenance == Provenance.NETWORK &&
                    _report.value.cached?.runId == cached.runId
                ) return@collect
                when (val parsed = ReportParser.parse(cached.json)) {
                    is Outcome.Ok -> _report.value = _report.value.copy(
                        report = parsed.value,
                        cached = cached,
                        provenance = Provenance.CACHE,
                    )
                    is Outcome.Failed -> _report.value = _report.value.copy(
                        problem = parsed.problem,
                    )
                }
            }
        }
    }

    fun refreshSettings() {
        _settings.value = settingsStore.settings()
    }

    /** Pull to refresh: find the newest finished run and read its report. */
    fun refreshLatestReport() {
        if (_report.value.loading) return
        viewModelScope.launch {
            _report.value = _report.value.copy(loading = true, problem = null)

            when (val list = repository.runs(20)) {
                is Outcome.Failed -> {
                    _report.value = _report.value.copy(loading = false, problem = list.problem)
                    return@launch
                }

                is Outcome.Ok -> {
                    _runs.value = _runs.value.copy(runs = list.value)
                    val finished = list.value.firstOrNull { it.isFinished }
                    if (finished == null) {
                        _report.value = _report.value.copy(
                            loading = false,
                            problem = Problem(
                                headline = "No finished run to read",
                                detail = if (list.value.isEmpty()) {
                                    "This workflow has never run."
                                } else {
                                    "The most recent run has not finished yet."
                                },
                                kind = Kind.NOT_FOUND,
                                fixHint = "Use the Run tab to start one.",
                            ),
                        )
                        return@launch
                    }
                    loadReport(finished)
                }
            }
        }
    }

    fun loadReport(run: WorkflowRun) {
        viewModelScope.launch {
            _report.value = _report.value.copy(loading = true, problem = null)
            when (val loaded = repository.fetchReport(run)) {
                is Outcome.Ok -> _report.value = ReportState(
                    report = loaded.value.report,
                    cached = loaded.value.cached,
                    provenance = Provenance.NETWORK,
                    loading = false,
                )
                // The cached report stays on screen. Losing the only readable
                // copy because a refresh failed would be a worse app than one
                // that never refreshed.
                is Outcome.Failed -> _report.value =
                    _report.value.copy(loading = false, problem = loaded.problem)
            }
        }
    }

    fun refreshRuns() {
        viewModelScope.launch {
            _runs.value = _runs.value.copy(loading = true, problem = null)
            when (val list = repository.runs(20)) {
                is Outcome.Ok -> _runs.value = _runs.value.copy(
                    runs = list.value, loading = false,
                    watching = _runs.value.watching?.let { watched ->
                        list.value.firstOrNull { it.id == watched.id } ?: watched
                    },
                )
                is Outcome.Failed -> _runs.value =
                    _runs.value.copy(loading = false, problem = list.problem)
            }
        }
    }

    /**
     * Start a run and follow it.
     *
     * `workflow_dispatch` returns 204 with no body, so there is a window where
     * the run exists on GitHub's side and cannot be named here. The UI says
     * "waiting for the run to appear" for exactly that window rather than
     * showing the previous run, which would look like a run that finished
     * impossibly fast.
     */
    fun startRun(scope: String, portals: String, mode: String, ref: String = "main") {
        if (_runs.value.dispatching) return
        viewModelScope.launch {
            _runs.value = _runs.value.copy(dispatching = true, problem = null, note = null)

            val inputs = buildMap {
                put("scope", scope)
                put("mode", mode)
                if (portals.isNotBlank()) put("portals", portals.trim())
            }

            when (val dispatched = repository.dispatch(inputs, ref)) {
                is Outcome.Failed -> {
                    _runs.value = _runs.value.copy(
                        dispatching = false,
                        problem = dispatched.problem,
                    )
                    return@launch
                }

                is Outcome.Ok -> {
                    val previousId = dispatched.value
                    _runs.value = _runs.value.copy(
                        dispatching = false,
                        awaitingNewRun = true,
                        note = "GitHub accepted the request. It does not say which run " +
                            "it started, so the app is watching for a new one to appear.",
                    )
                    watchForNewRun(previousId)
                }
            }
        }
    }

    private suspend fun watchForNewRun(previousId: Long?) {
        // Roughly a minute of looking. GitHub usually registers a dispatched
        // run in a few seconds; if it has not after this long, saying so is
        // better than spinning forever.
        repeat(12) { attempt ->
            delay(if (attempt < 4) 3_000 else 8_000)
            when (val found = repository.runStartedAfter(previousId)) {
                is Outcome.Ok -> {
                    val run = found.value
                    if (run != null) {
                        _runs.value = _runs.value.copy(
                            awaitingNewRun = false,
                            watching = run,
                            note = null,
                        )
                        followRun(run.id)
                        return
                    }
                }

                is Outcome.Failed -> {
                    // A transient failure while watching is not a failed run.
                    if (!found.problem.isTransient) {
                        _runs.value = _runs.value.copy(
                            awaitingNewRun = false, problem = found.problem,
                        )
                        return
                    }
                }
            }
        }
        _runs.value = _runs.value.copy(
            awaitingNewRun = false,
            note = "The run was accepted but has not appeared after a minute. It is " +
                "probably queued -- pull to refresh, or check the Actions tab.",
        )
    }

    /** Poll one run until it finishes, then read its report. */
    fun followRun(runId: Long) {
        viewModelScope.launch {
            repeat(150) {
                when (val current = repository.run(runId)) {
                    is Outcome.Ok -> {
                        _runs.value = _runs.value.copy(watching = current.value)
                        if (current.value.isFinished) {
                            if (current.value.conclusion == "success" ||
                                current.value.conclusion == "failure"
                            ) {
                                // A failed run still wrote its files: the
                                // workflow uploads them with always(), because
                                // a total portal outage is a failed run AND the
                                // most important report to read.
                                loadReport(current.value)
                            }
                            return@launch
                        }
                    }

                    is Outcome.Failed -> {
                        if (!current.problem.isTransient) {
                            _runs.value = _runs.value.copy(problem = current.problem)
                            return@launch
                        }
                    }
                }
                delay(6_000)
            }
            _runs.value = _runs.value.copy(
                note = "Still running after 15 minutes. The app has stopped watching; " +
                    "pull to refresh when you want to check again.",
            )
        }
    }

    fun downloadFiles(run: WorkflowRun) {
        viewModelScope.launch {
            _files.value = _files.value.copy(downloading = true, problem = null)
            when (val downloaded = repository.downloadFiles(run)) {
                is Outcome.Ok -> _files.value = FilesState(files = downloaded.value)
                is Outcome.Failed -> _files.value =
                    _files.value.copy(downloading = false, problem = downloaded.problem)
            }
        }
    }

    fun hasToken(): Boolean = tokens.hasToken()
}
