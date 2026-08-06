package jo.tendermonitor.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import jo.tendermonitor.data.Outcome
import jo.tendermonitor.data.Problem
import jo.tendermonitor.data.portals.EntryRules
import jo.tendermonitor.data.portals.PortalsFile
import jo.tendermonitor.data.portals.PortalsRepository
import jo.tendermonitor.data.portals.ProbeReport
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject

data class PortalsState(
    val entries: List<PortalsFile.Entry> = emptyList(),
    val loading: Boolean = false,
    /** The key currently being committed, so only that row shows a spinner. */
    val busyKey: String? = null,
    val problem: Problem? = null,
    val lastCommit: PortalsRepository.CommitResult? = null,
    val loaded: Boolean = false,
)

data class AddPortalState(
    val key: String = "",
    val name: String = "",
    val urls: String = "",
    val tier: Int = 2,
    val selectors: String = "",
    val anchorHint: String = "",
    val currency: String = "",
    val filterToJordan: Boolean = true,
    val notes: String = "",
    /** A validation message from the same rules the backend applies. */
    val formProblem: String? = null,
    val testing: Boolean = false,
    val testStage: String? = null,
    val probe: ProbeReport? = null,
    val problem: Problem? = null,
    val saving: Boolean = false,
) {
    val urlList: List<String>
        get() = urls.split('\n', ',')
            .map { it.trim() }
            .filter { it.isNotEmpty() }

    val selectorList: List<String>
        get() = selectors.split('\n')
            .map { it.trim() }
            .filter { it.isNotEmpty() }

    /**
     * Saving is allowed only after a test has run.
     *
     * Not because a bad portal would break anything -- it reports as
     * unavailable like every other failure -- but because committing a URL
     * nobody has looked at is how a portal ends up reporting "unavailable"
     * forever while looking like an honest failure. The test is one tap and
     * it answers the question.
     */
    val canSave: Boolean get() = probe != null && !saving
}

class PortalsViewModel(
    private val repository: PortalsRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(PortalsState())
    val state: StateFlow<PortalsState> = _state.asStateFlow()

    private val _add = MutableStateFlow(AddPortalState())
    val add: StateFlow<AddPortalState> = _add.asStateFlow()

    private var root: JsonObject? = null
    private var sha: String = ""

    fun load() {
        if (_state.value.loading) return
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, problem = null)
            when (val loaded = repository.load()) {
                is Outcome.Ok -> {
                    root = loaded.value.document.root
                    sha = loaded.value.sha
                    _state.value = _state.value.copy(
                        entries = loaded.value.document.entries,
                        loading = false,
                        loaded = true,
                    )
                }

                is Outcome.Failed -> _state.value =
                    _state.value.copy(loading = false, problem = loaded.problem)
            }
        }
    }

    fun setEnabled(entry: PortalsFile.Entry, enabled: Boolean) {
        val current = root ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(busyKey = entry.key, problem = null)
            val updated = PortalsFile.withEnabled(current, entry.key, enabled)
            commit(updated, repository.enableMessage(entry, enabled))
        }
    }

    fun remove(entry: PortalsFile.Entry) {
        val current = root ?: return
        viewModelScope.launch {
            _state.value = _state.value.copy(busyKey = entry.key, problem = null)
            commit(PortalsFile.withRemoved(current, entry.key),
                   repository.removeMessage(entry))
        }
    }

    private suspend fun commit(updated: JsonObject, message: String) {
        when (val result = repository.commit(updated, sha, message)) {
            is Outcome.Ok -> {
                _state.value = _state.value.copy(
                    busyKey = null,
                    lastCommit = result.value,
                )
                // Reload rather than patch the local copy: the sha has moved,
                // and a stale one turns the next edit into a 409 that reads as
                // someone else's change.
                load()
            }

            is Outcome.Failed -> _state.value =
                _state.value.copy(busyKey = null, problem = result.problem)
        }
    }

    // -----------------------------------------------------------------------
    // Adding
    // -----------------------------------------------------------------------

    fun updateAdd(transform: (AddPortalState) -> AddPortalState) {
        // Any edit invalidates a previous test: the probe was for the old
        // values, and showing it beside changed ones would be a result
        // attached to the wrong question.
        val next = transform(_add.value)
        _add.value = if (next == _add.value) next
        else next.copy(probe = null, formProblem = null, problem = null)
    }

    fun resetAdd() {
        _add.value = AddPortalState()
    }

    private fun validate(form: AddPortalState): String? =
        EntryRules.keyProblem(form.key.trim(), _state.value.entries.map { it.key })
            ?: EntryRules.urlProblem(form.urlList)
            ?: EntryRules.tierProblem(form.tier)
            ?: if (form.name.isBlank()) {
                "A name is required. It is what the report calls this portal."
            } else null

    private fun candidate(form: AddPortalState): JsonObject = PortalsFile.buildEntry(
        key = form.key.trim(),
        name = form.name.trim(),
        urls = form.urlList,
        tier = form.tier,
        selectors = form.selectorList,
        anchorHint = form.anchorHint.trim().ifBlank { null },
        currency = form.currency.trim().ifBlank { null },
        filterToJordan = form.filterToJordan,
        notes = form.notes.trim(),
    )

    /**
     * Fetch the candidate's pages on GitHub's runner and report what came back.
     *
     * Several minutes end to end: dispatch, wait for the run to appear, wait
     * for it to finish, download the artifact. The stage is shown throughout,
     * because a spinner with no words is indistinguishable from a hang.
     */
    fun test() {
        val form = _add.value
        val invalid = validate(form)
        if (invalid != null) {
            _add.value = form.copy(formProblem = invalid, probe = null)
            return
        }
        if (form.testing) return

        viewModelScope.launch {
            _add.value = form.copy(
                testing = true, probe = null, problem = null, formProblem = null,
                testStage = "Asking GitHub to fetch the page...",
            )

            val previousId = when (val started = repository.startProbe(candidate(form))) {
                is Outcome.Failed -> {
                    _add.value = _add.value.copy(
                        testing = false, testStage = null, problem = started.problem,
                    )
                    return@launch
                }

                is Outcome.Ok -> started.value
            }

            _add.value = _add.value.copy(
                testStage = "Waiting for the run to appear -- GitHub does not " +
                    "say which run it started, so the app watches for a new one.",
            )

            var run = awaitNewRun(previousId)
            if (run == null) {
                _add.value = _add.value.copy(
                    testing = false,
                    testStage = null,
                    problem = Problem(
                        headline = "The test was accepted but no run appeared",
                        detail = "GitHub took the request and has not registered " +
                            "a run after a minute. It is probably queued.",
                        fixHint = "Check the Actions tab, then try again.",
                    ),
                )
                return@launch
            }

            _add.value = _add.value.copy(
                testStage = "Run #${run.runNumber} is fetching the page...",
            )

            run = awaitFinish(run.id) ?: run
            _add.value = _add.value.copy(testStage = "Reading the result...")

            when (val report = repository.probeResult(run)) {
                is Outcome.Ok -> _add.value = _add.value.copy(
                    testing = false, testStage = null, probe = report.value,
                )

                is Outcome.Failed -> _add.value = _add.value.copy(
                    testing = false, testStage = null, problem = report.problem,
                )
            }
        }
    }

    private suspend fun awaitNewRun(previousId: Long?): jo.tendermonitor.data.github.WorkflowRun? {
        repeat(12) { attempt ->
            delay(if (attempt < 4) 3_000 else 8_000)
            val runs = repository.runsForProbe()
            val newest = runs.valueOrNull()?.maxByOrNull { it.id } ?: return@repeat
            if (previousId == null || newest.id > previousId) return newest
        }
        return null
    }

    private suspend fun awaitFinish(runId: Long): jo.tendermonitor.data.github.WorkflowRun? {
        repeat(60) {
            val current = repository.run(runId)
            val value = current.valueOrNull()
            if (value != null && value.isFinished) return value
            delay(6_000)
        }
        return null
    }

    /**
     * Commit the candidate.
     *
     * The probe's verdict travels into the commit message, so the history says
     * what the page looked like on the day it was added -- which is the first
     * thing anyone wants when it stops working.
     */
    fun save() {
        val form = _add.value
        val current = root ?: return
        val invalid = validate(form)
        if (invalid != null) {
            _add.value = form.copy(formProblem = invalid)
            return
        }
        viewModelScope.launch {
            _add.value = form.copy(saving = true, problem = null)
            val summary = form.probe?.verdict?.let { verdict ->
                "${verdict.headline}. ${verdict.detail}".trim()
            }
            val message = repository.addMessage(
                form.key.trim(), form.name.trim(), form.urlList, summary,
            )
            when (val result = repository.commit(
                PortalsFile.withAdded(current, candidate(form)), sha, message)
            ) {
                is Outcome.Ok -> {
                    _state.value = _state.value.copy(lastCommit = result.value)
                    _add.value = AddPortalState()
                    load()
                }

                is Outcome.Failed -> _add.value =
                    _add.value.copy(saving = false, problem = result.problem)
            }
        }
    }

    fun dismissCommit() {
        _state.value = _state.value.copy(lastCommit = null)
    }
}
