package jo.tendermonitor.data

import jo.tendermonitor.data.db.CachedReport
import jo.tendermonitor.data.db.ReportDao
import jo.tendermonitor.data.github.Artifact
import jo.tendermonitor.data.github.DispatchRequest
import jo.tendermonitor.data.github.GitHubClient
import jo.tendermonitor.data.github.WorkflowRun
import jo.tendermonitor.data.report.ArtifactZip
import jo.tendermonitor.data.report.Report
import jo.tendermonitor.data.report.ReportParser
import jo.tendermonitor.data.settings.AppSettings
import jo.tendermonitor.data.settings.SettingsStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Everything the app knows how to do with a run.
 *
 * The shape of this class is set by one fact about GitHub: **there is no API
 * for a job's step summary.** The markdown the workflow renders onto the run
 * page -- which is the report, in full, and is what makes the current phone
 * workflow work at all -- is not reachable by any documented endpoint. So a
 * report is read the only other way it is published: as a file in the run's
 * artifacts.
 *
 * That costs a download and a zip, and buys something better than the summary
 * would have been: structured data, with the portal health table intact.
 */
class ReportRepository(
    private val client: GitHubClient,
    private val dao: ReportDao,
    private val settings: SettingsStore,
    private val artifactDir: File,
) {

    data class LoadedReport(
        val report: Report,
        val run: WorkflowRun?,
        val cached: CachedReport,
        /** True when this came off disk rather than the network. */
        val fromCache: Boolean,
    )

    /** What the app shows before any network call: whatever it last stored. */
    fun cachedLatest() = dao.latest()

    fun history() = dao.history()

    suspend fun runs(limit: Int = 20): Outcome<List<WorkflowRun>> {
        val config = settings.settings()
        return client.call("listing the workflow's runs") { api ->
            api.workflowRuns(config.repoOwner, config.repoName, config.workflowFile, limit)
        }.map { it.runs }
    }

    suspend fun run(runId: Long): Outcome<WorkflowRun> {
        val config = settings.settings()
        return client.call("checking the run") { api ->
            api.run(config.repoOwner, config.repoName, runId)
        }
    }

    /**
     * Ask GitHub to start a run.
     *
     * Returns the id of the newest run that existed BEFORE the dispatch.
     * `workflow_dispatch` answers 204 with no body -- it does not say what it
     * started -- so the caller watches for a run newer than this one to appear.
     * Without that marker the app would show the previous run as if it were
     * the new one, which is the kind of wrong that looks right.
     */
    suspend fun dispatch(inputs: Map<String, String>, ref: String = "main"): Outcome<Long?> {
        val config = settings.settings()
        val before = runs(1).valueOrNull()?.firstOrNull()?.id

        val dispatched = client.call("starting a run") { api ->
            api.dispatch(
                config.repoOwner, config.repoName, config.workflowFile,
                DispatchRequest(ref = ref, inputs = inputs),
            )
        }
        return dispatched.map { before }
    }

    /**
     * The run that started after [afterRunId], if it has appeared yet.
     *
     * Null means "not yet", which is not a failure and must not be shown as
     * one: GitHub takes a few seconds to register a dispatched run.
     */
    suspend fun runStartedAfter(afterRunId: Long?): Outcome<WorkflowRun?> =
        runs(5).map { list ->
            val newest = list.maxByOrNull { it.id }
            when {
                newest == null -> null
                afterRunId == null -> newest
                newest.id > afterRunId -> newest
                else -> null
            }
        }

    /** The files a finished run produced. */
    suspend fun artifacts(runId: Long): Outcome<List<Artifact>> {
        val config = settings.settings()
        return client.call("listing the run's files") { api ->
            api.artifacts(config.repoOwner, config.repoName, runId)
        }.map { it.artifacts }
    }

    /**
     * Download a run's report and store it.
     *
     * Every way this can fail says which way it failed, because they need
     * different responses: an expired artifact is not a download failure, a
     * run that produced no report is not an empty report, and a report from a
     * newer pipeline is not a corrupt one.
     */
    suspend fun fetchReport(run: WorkflowRun): Outcome<LoadedReport> = withContext(Dispatchers.IO) {
        val config = settings.settings()

        val artifacts = when (val found = artifacts(run.id)) {
            is Outcome.Failed -> return@withContext found
            is Outcome.Ok -> found.value
        }

        if (artifacts.isEmpty()) {
            return@withContext Outcome.Failed(
                Problem(
                    headline = "This run produced no files",
                    detail = "Run #${run.runNumber} finished ${run.conclusion ?: "with no conclusion"} " +
                        "and uploaded nothing.",
                    kind = Kind.NOT_FOUND,
                    fixHint = if (run.conclusion == "failure") {
                        "The run failed before it could write a report. Its log says where."
                    } else {
                        "Artifacts are kept for 90 days; older runs lose them."
                    },
                )
            )
        }

        val artifact = artifacts.firstOrNull { it.name.startsWith("jordan-tenders") }
            ?: artifacts.first()

        if (artifact.expired) {
            return@withContext Outcome.Failed(
                Problem(
                    headline = "This run's files have expired",
                    detail = "Artifacts are kept for 90 days. ${artifact.name} is past that " +
                        "and GitHub has deleted it.",
                    kind = Kind.EXPIRED,
                    fixHint = "Nothing is broken. Trigger a run to get a current pack.",
                )
            )
        }

        val bytes = client.call("downloading the run's files") { api ->
            api.artifactZip(config.repoOwner, config.repoName, artifact.id)
        }
        val body = when (bytes) {
            is Outcome.Failed -> return@withContext bytes
            is Outcome.Ok -> bytes.value
        }

        val text = try {
            body.byteStream().use { stream ->
                ArtifactZip.readTextEntry(stream, ArtifactZip::isReportJson)
            }
        } catch (error: Exception) {
            return@withContext Outcome.Failed(
                Problem(
                    headline = "The run's files could not be opened",
                    detail = error.message?.take(200).orEmpty(),
                    kind = Kind.MALFORMED,
                )
            )
        }

        if (text == null) {
            return@withContext Outcome.Failed(
                Problem(
                    headline = "No report in this run's files",
                    detail = "The archive downloaded but carried no report JSON. Runs " +
                        "before the app existed did not write one.",
                    kind = Kind.NOT_FOUND,
                    fixHint = "Trigger a new run -- the current workflow writes it.",
                )
            )
        }

        val report = when (val parsed = ReportParser.parse(text)) {
            is Outcome.Failed -> return@withContext parsed
            is Outcome.Ok -> parsed.value
        }

        val cached = CachedReport(
            runId = run.id,
            runNumber = run.runNumber,
            storedAt = System.currentTimeMillis(),
            runCreatedAt = run.createdAt.orEmpty(),
            runConclusion = run.conclusion.orEmpty(),
            runHtmlUrl = run.htmlUrl.orEmpty(),
            status = report.run.status,
            statusLine = report.run.statusLine,
            opportunityCount = report.run.opportunityCount,
            portalsBroken = report.run.portalsBroken,
            json = text,
        )
        dao.store(cached)
        Outcome.Ok(LoadedReport(report, run, cached, fromCache = false))
    }

    /**
     * Download a run's Word and Excel packs to a directory this app can share
     * out by intent.
     */
    suspend fun downloadFiles(run: WorkflowRun): Outcome<List<File>> = withContext(Dispatchers.IO) {
        val config = settings.settings()

        val artifacts = when (val found = artifacts(run.id)) {
            is Outcome.Failed -> return@withContext found
            is Outcome.Ok -> found.value
        }
        val artifact = artifacts.firstOrNull { it.name.startsWith("jordan-tenders") }
            ?: return@withContext Outcome.Failed(
                Problem(
                    headline = "This run has no report pack",
                    detail = "No artifact named jordan-tenders-* was uploaded.",
                    kind = Kind.NOT_FOUND,
                )
            )

        if (artifact.expired) {
            return@withContext Outcome.Failed(
                Problem(
                    headline = "This run's files have expired",
                    detail = "GitHub keeps run artifacts for 90 days and has deleted these.",
                    kind = Kind.EXPIRED,
                    fixHint = "Trigger a run to get a current pack.",
                )
            )
        }

        val body = when (
            val bytes = client.call("downloading the run's files") { api ->
                api.artifactZip(config.repoOwner, config.repoName, artifact.id)
            }
        ) {
            is Outcome.Failed -> return@withContext bytes
            is Outcome.Ok -> bytes.value
        }

        val destination = File(artifactDir, "run-${run.runNumber}")
        val skipped = mutableListOf<String>()
        val files = try {
            body.byteStream().use { ArtifactZip.extractAll(it, destination, skipped) }
        } catch (error: Exception) {
            return@withContext Outcome.Failed(
                Problem(
                    headline = "The files could not be unpacked",
                    detail = error.message?.take(200).orEmpty(),
                    kind = Kind.MALFORMED,
                )
            )
        }

        if (skipped.isNotEmpty()) {
            // Not silent. An archive with entries we refused to write is worth
            // saying out loud even though the rest extracted fine.
            return@withContext Outcome.Failed(
                Problem(
                    headline = "Some files in the archive were refused",
                    detail = "${skipped.size} entr${if (skipped.size == 1) "y" else "ies"} " +
                        "had a path pointing outside the download folder and were not " +
                        "written: ${skipped.take(3).joinToString()}",
                    kind = Kind.MALFORMED,
                    fixHint = "The ${files.size} other file(s) did extract, in " +
                        "run-${run.runNumber}.",
                )
            )
        }

        Outcome.Ok(files)
    }

    suspend fun settingsNow(): AppSettings = withContext(Dispatchers.IO) { settings.settings() }
}
