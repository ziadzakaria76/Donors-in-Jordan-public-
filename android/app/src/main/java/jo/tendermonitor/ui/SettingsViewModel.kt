package jo.tendermonitor.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import jo.tendermonitor.data.Outcome
import jo.tendermonitor.data.github.GitHubClient
import jo.tendermonitor.data.settings.AppSettings
import jo.tendermonitor.data.settings.Redact
import jo.tendermonitor.data.settings.SettingsStore
import jo.tendermonitor.data.settings.TokenStore
import jo.tendermonitor.work.PollState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** What the background checks have been doing, for the Settings screen. */
data class PollStatus(
    val lastAttemptMillis: Long = 0L,
    val lastSuccessMillis: Long = 0L,
    val lastNote: String = "",
    val consecutiveFailures: Int = 0,
    val lastNotifiedRunId: Long = 0L,
)

class SettingsViewModel(
    private val tokens: TokenStore,
    private val settingsStore: SettingsStore,
    private val client: GitHubClient,
    private val pollState: PollState,
    /** Applied whenever the schedule changes. Injected so the view model
     *  stays free of Android context. */
    private val onScheduleChanged: (AppSettings) -> Unit = {},
) : ViewModel() {

    private val _settings = MutableStateFlow(settingsStore.settings())
    val settings: StateFlow<AppSettings> = _settings.asStateFlow()

    private val _fingerprint = MutableStateFlow(Redact.fingerprint(tokens.token()))
    val fingerprint: StateFlow<String> = _fingerprint.asStateFlow()

    private val _verifyResult = MutableStateFlow<String?>(null)
    val verifyResult: StateFlow<String?> = _verifyResult.asStateFlow()

    private val _pollStatus = MutableStateFlow(readPollStatus())
    val pollStatus: StateFlow<PollStatus> = _pollStatus.asStateFlow()

    private fun readPollStatus() = PollStatus(
        lastAttemptMillis = pollState.lastAttemptMillis(),
        lastSuccessMillis = pollState.lastSuccessMillis(),
        lastNote = pollState.lastNote(),
        consecutiveFailures = pollState.consecutiveFailures(),
        lastNotifiedRunId = pollState.lastNotifiedRunId(),
    )

    /** Re-read when the Settings screen comes back into view. */
    fun refreshPollStatus() {
        _pollStatus.value = readPollStatus()
    }

    fun saveToken(token: String) {
        tokens.saveToken(token)
        _fingerprint.value = Redact.fingerprint(tokens.token())
        _verifyResult.value = "Saved. Tap 'Check it works' to confirm GitHub accepts it."
    }

    fun clearToken() {
        tokens.saveToken(null)
        _fingerprint.value = Redact.fingerprint(null)
        _verifyResult.value = "Removed from this phone."
    }

    fun saveSettings(settings: AppSettings) {
        settingsStore.save(settings)
        val saved = settingsStore.settings()
        _settings.value = saved
        // Re-registered immediately rather than on next launch: a schedule
        // that only takes effect after a restart is a setting that looks
        // applied and is not.
        onScheduleChanged(saved)
        _verifyResult.value = null
    }

    /**
     * Two calls, deliberately.
     *
     * `GET /user` proves the token is a valid credential. It says nothing about
     * whether it can see THIS repository -- a token scoped to the wrong
     * repository passes it perfectly and then 404s on everything that matters.
     * So the repository is checked too, and the result says which of the two
     * worked.
     */
    fun verify() {
        viewModelScope.launch {
            _verifyResult.value = "Checking..."
            val config = settingsStore.settings()

            when (val user = client.call("checking the token") { it.user() }) {
                is Outcome.Failed -> {
                    _verifyResult.value = Redact.scrub(
                        "The token itself was rejected: ${user.problem.headline}. " +
                            "${user.problem.detail}",
                        tokens.token(),
                    )
                    return@launch
                }

                is Outcome.Ok -> {
                    val who = user.value.login.ifBlank { "an account" }
                    when (
                        val runs = client.call("checking the repository") { api ->
                            api.workflowRuns(
                                config.repoOwner, config.repoName, config.workflowFile, 1,
                            )
                        }
                    ) {
                        is Outcome.Ok -> {
                            _verifyResult.value =
                                "Works. Authenticated as $who, and ${config.repoSlug} " +
                                    "answered with ${runs.value.totalCount} run(s) of " +
                                    "${config.workflowFile}."
                        }

                        is Outcome.Failed -> {
                            _verifyResult.value = Redact.scrub(
                                "The token is valid (authenticated as $who) but " +
                                    "${config.repoSlug} did not answer: " +
                                    "${runs.problem.headline}. ${runs.problem.detail} " +
                                    (runs.problem.fixHint ?: ""),
                                tokens.token(),
                            )
                        }
                    }
                }
            }
        }
    }
}
