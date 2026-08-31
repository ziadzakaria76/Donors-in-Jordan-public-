package jo.tendermonitor.data.portals

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Outcome
import jo.tendermonitor.data.Problem
// A top-level extension in the parent package, so it needs naming here even
// though Outcome itself is imported.
import jo.tendermonitor.data.map
import jo.tendermonitor.data.github.DispatchRequest
import jo.tendermonitor.data.github.GitHubClient
import jo.tendermonitor.data.github.PutFileRequest
import jo.tendermonitor.data.github.WorkflowRun
import jo.tendermonitor.data.report.ArtifactZip
import jo.tendermonitor.data.settings.SettingsStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import java.util.Base64

/**
 * Reading and editing the portal list in the repository.
 *
 * Every change is a commit through the Contents API, with a message that says
 * what changed and why in the same voice as the rest of the history -- and the
 * resulting commit is shown back, because "saved" is a claim and a commit sha
 * is evidence.
 */
class PortalsRepository(
    private val client: GitHubClient,
    private val settings: SettingsStore,
) {

    private val probeJson = Json { ignoreUnknownKeys = true; isLenient = true }

    data class LoadedFile(
        val document: PortalsFile.Document,
        /** The blob sha of the file as loaded. Required to commit over it. */
        val sha: String,
        val text: String,
    )

    data class CommitResult(
        val sha: String,
        val url: String,
        val message: String,
    )

    suspend fun load(): Outcome<LoadedFile> = withContext(Dispatchers.IO) {
        val config = settings.settings()
        val path = PortalsFile.pathFor(config.workflowFile)
            ?: return@withContext Outcome.Failed(notThisMonitorsFile(config.workflowFile))
        val response = client.call("reading the portal list") { api ->
            api.fileContents(config.repoOwner, config.repoName, path)
        }
        when (response) {
            is Outcome.Failed -> response
            is Outcome.Ok -> {
                val contents = response.value
                val text = try {
                    // GitHub base64-encodes with embedded newlines; MIME
                    // decoding handles them, the basic decoder does not.
                    String(Base64.getMimeDecoder().decode(contents.content), Charsets.UTF_8)
                } catch (error: Exception) {
                    return@withContext Outcome.Failed(
                        Problem(
                            headline = "The portal list could not be decoded",
                            detail = error.message?.take(200).orEmpty(),
                            kind = Kind.MALFORMED,
                        )
                    )
                }
                try {
                    Outcome.Ok(LoadedFile(PortalsFile.parse(text), contents.sha, text))
                } catch (error: PortalsFile.MalformedException) {
                    Outcome.Failed(
                        Problem(
                            headline = "The portal list is not in the expected shape",
                            detail = error.message.orEmpty(),
                            kind = Kind.MALFORMED,
                            fixHint = "Nothing was changed. This app will not " +
                                "rewrite a file it cannot recognise.",
                        )
                    )
                }
            }
        }
    }

    /**
     * Commit a new version of the file.
     *
     * The `sha` is the one read at load time. If someone else has committed
     * since, GitHub answers 409 and the write is refused rather than silently
     * overwriting their change -- a rule this app follows for the same reason
     * the pipeline never guesses a missing field.
     */
    suspend fun commit(
        root: JsonObject,
        sha: String,
        message: String,
    ): Outcome<CommitResult> = withContext(Dispatchers.IO) {
        val config = settings.settings()
        // Checked again on the way out, not only on the way in: load() is what
        // normally stops this screen being reachable, but a save is the call
        // that writes to somebody's repository and it must not depend on an
        // earlier screen having done the right thing.
        val path = PortalsFile.pathFor(config.workflowFile)
            ?: return@withContext Outcome.Failed(notThisMonitorsFile(config.workflowFile))
        val encoded = Base64.getEncoder()
            .encodeToString(PortalsFile.serialise(root).toByteArray(Charsets.UTF_8))

        val response = client.call("saving the portal list") { api ->
            api.putFile(
                config.repoOwner, config.repoName, path,
                PutFileRequest(message = message, content = encoded, sha = sha),
            )
        }
        when (response) {
            is Outcome.Failed -> {
                val problem = response.problem
                if (problem.detail.contains("does not match", ignoreCase = true) ||
                    problem.detail.contains("conflict", ignoreCase = true)
                ) {
                    Outcome.Failed(
                        problem.copy(
                            headline = "Someone else changed the portal list",
                            fixHint = "Your change was NOT saved and theirs was " +
                                "not overwritten. Reload the list and try again.",
                        )
                    )
                } else {
                    response
                }
            }

            is Outcome.Ok -> Outcome.Ok(
                CommitResult(
                    sha = response.value.commit.sha,
                    url = response.value.commit.htmlUrl.orEmpty(),
                    message = message,
                )
            )
        }
    }

    // -----------------------------------------------------------------------
    // Commit messages.
    //
    // Real messages saying WHY, in the voice of the rest of the history. A
    // commit reading "update portals.json" is a commit nobody can review, and
    // this file is the one a bad edit breaks the next morning's run with.
    // -----------------------------------------------------------------------

    fun enableMessage(entry: PortalsFile.Entry, enabled: Boolean): String =
        if (enabled) {
            "Switch ${entry.name} back on\n\n" +
                "Re-enabled from the phone app. It will be polled on the next " +
                "run and will appear in the portal status table again."
        } else {
            "Stop polling ${entry.name}\n\n" +
                "Disabled from the phone app. The entry is kept rather than " +
                "deleted, so its URLs and selectors survive for whenever it is " +
                "worth trying again -- and so its absence from the report is a " +
                "decision on the record rather than a gap."
        }

    fun addMessage(key: String, name: String, urls: List<String>,
                   probeSummary: String?): String = buildString {
        append("Add $name as a portal\n\n")
        append("Added from the phone app.")
        append(" Source${if (urls.size == 1) "" else "s"}: ${urls.joinToString(", ")}\n")
        if (!probeSummary.isNullOrBlank()) {
            append("\nTested against the live page before saving: ")
            append(probeSummary)
            append("\n")
        }
        append(
            "\nIt goes through the same six-layer cascade as every other " +
                "data-only portal. If it stops reading, it reports as " +
                "unavailable with a diagnosed reason like any other portal -- " +
                "it cannot break the run.\n"
        )
    }

    fun removeMessage(entry: PortalsFile.Entry): String =
        "Remove ${entry.name} from the portal list\n\n" +
            "Removed from the phone app. It was reading " +
            "${entry.urls.firstOrNull() ?: "no source"}.\n\n" +
            "Deleting rather than disabling loses the URLs and selectors. If " +
            "this portal is only temporarily not worth polling, \"enabled\": " +
            "false keeps them."

    // -----------------------------------------------------------------------
    // Testing a candidate before it is saved
    // -----------------------------------------------------------------------

    /**
     * Ask the workflow to fetch a candidate's pages and report what it found.
     *
     * The alternative -- commit it, diagnose it, remove it if it was no good --
     * leaves a half-added portal in the repository and a window where a
     * scheduled run picks up something nobody has looked at. Sending the
     * candidate as data avoids both.
     */
    suspend fun startProbe(candidate: JsonObject, ref: String = "main"): Outcome<Long?> {
        val config = settings.settings()
        // Refused here rather than by the workflow. syria-monitor.yml declares
        // this mode only so the dispatch is not rejected as an unknown input,
        // and fails the run with a message saying --probe is Jordan-only. That
        // is the right server-side answer, but it costs a run and a wait to
        // deliver news the app already had.
        if (PortalsFile.pathFor(config.workflowFile) == null) {
            return Outcome.Failed(notThisMonitorsFile(config.workflowFile))
        }
        val before = client.call("listing the workflow's runs") { api ->
            api.workflowRuns(config.repoOwner, config.repoName, config.workflowFile, 1)
        }.valueOrNull()?.runs?.firstOrNull()?.id

        val dispatched = client.call("starting the portal test") { api ->
            api.dispatch(
                config.repoOwner, config.repoName, config.workflowFile,
                DispatchRequest(
                    ref = ref,
                    inputs = mapOf(
                        "mode" to PROBE_MODE,
                        "candidate" to Json.encodeToString(JsonObject.serializer(), candidate),
                        // Required inputs the workflow declares. They are
                        // ignored in probe mode, but workflow_dispatch
                        // rejects a request that omits a required input.
                        "scope" to "everything currently open",
                    ),
                ),
            )
        }
        return dispatched.map { before }
    }

    /** Recent runs, for spotting the one the probe dispatch started. */
    suspend fun runsForProbe(limit: Int = 5): Outcome<List<WorkflowRun>> {
        val config = settings.settings()
        return client.call("watching for the test run") { api ->
            api.workflowRuns(config.repoOwner, config.repoName, config.workflowFile, limit)
        }.map { it.runs }
    }

    suspend fun run(runId: Long): Outcome<WorkflowRun> {
        val config = settings.settings()
        return client.call("checking the test run") { api ->
            api.run(config.repoOwner, config.repoName, runId)
        }
    }

    /** Download and parse the probe document a finished run produced. */
    suspend fun probeResult(run: WorkflowRun): Outcome<ProbeReport> = withContext(Dispatchers.IO) {
        val config = settings.settings()

        val artifacts = client.call("listing the test's files") { api ->
            api.artifacts(config.repoOwner, config.repoName, run.id)
        }
        val list = when (artifacts) {
            is Outcome.Failed -> return@withContext artifacts
            is Outcome.Ok -> artifacts.value.artifacts
        }

        val artifact = list.firstOrNull { it.name.startsWith("portal-probe") }
            ?: return@withContext Outcome.Failed(
                Problem(
                    headline = "The test produced no result",
                    detail = "Run #${run.runNumber} finished " +
                        "${run.conclusion ?: "with no conclusion"} and uploaded no " +
                        "probe file.",
                    kind = Kind.NOT_FOUND,
                    fixHint = "The run log will say why. A run that failed before " +
                        "fetching writes nothing.",
                )
            )

        val body = when (
            val bytes = client.call("downloading the test result") { api ->
                api.artifactZip(config.repoOwner, config.repoName, artifact.id)
            }
        ) {
            is Outcome.Failed -> return@withContext bytes
            is Outcome.Ok -> bytes.value
        }

        val text = try {
            body.byteStream().use { stream ->
                ArtifactZip.readTextEntry(stream) { it.startsWith("probe_") }
            }
        } catch (error: Exception) {
            return@withContext Outcome.Failed(
                Problem(
                    headline = "The test result could not be opened",
                    detail = error.message?.take(200).orEmpty(),
                    kind = Kind.MALFORMED,
                )
            )
        } ?: return@withContext Outcome.Failed(
            Problem(
                headline = "No probe document in the test's files",
                detail = "The archive downloaded but carried no probe_*.json.",
                kind = Kind.NOT_FOUND,
            )
        )

        try {
            val report = probeJson.decodeFromString(ProbeReport.serializer(), text)
            if (report.schema > ProbeReport.SUPPORTED_SCHEMA) {
                Outcome.Failed(
                    Problem(
                        headline = "This app is older than the test result",
                        detail = "The run wrote schema ${report.schema}; this app " +
                            "understands ${ProbeReport.SUPPORTED_SCHEMA}.",
                        kind = Kind.MALFORMED,
                        fixHint = "Install the newer APK before adding a portal.",
                    )
                )
            } else {
                Outcome.Ok(report)
            }
        } catch (error: Exception) {
            Outcome.Failed(
                Problem(
                    headline = "The test result could not be read",
                    detail = error.message?.take(200).orEmpty(),
                    kind = Kind.MALFORMED,
                )
            )
        }
    }

    companion object {
        /** Must match monitor.yml exactly; a choice input is matched literally. */
        const val PROBE_MODE = "test a candidate portal (--probe)"

        /**
         * Said plainly, because the alternative is worse than an error.
         *
         * Falling back to Jordan's file would show one country's portals while
         * the app is running another's, and a save would commit to it. The
         * screen is not broken and neither is the monitor -- this monitor keeps
         * its portals somewhere this file's schema cannot describe.
         */
        fun notThisMonitorsFile(workflowFile: String) = Problem(
            headline = "This monitor's portals are not editable here",
            detail = "The Portals screen edits ${PortalsFile.PATH}, which belongs " +
                "to the Jordan monitor. Settings is pointed at " +
                "${workflowFile.ifBlank { "no workflow" }}, whose portals are " +
                "configured in its own config.yml and are not in this file's " +
                "format.",
            kind = Kind.NOT_FOUND,
            fixHint = "Point Settings at monitor.yml to edit the Jordan portal " +
                "list. The other monitor's portals are edited in the repository.",
        )
    }
}
