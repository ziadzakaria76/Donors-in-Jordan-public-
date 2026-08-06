package jo.tendermonitor.work

import android.content.Context
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import jo.tendermonitor.TenderMonitorApp
import jo.tendermonitor.data.Outcome

/**
 * The background check.
 *
 * It answers one question — has a run finished that you have not been told
 * about? — and it is written so that the answer "no" and the answer "I could
 * not find out" never look the same afterwards. Both are recorded; only one is
 * silence.
 *
 * WHAT IT DELIBERATELY DOES NOT DO. It does not start runs. The monitor has
 * its own weekday schedule on GitHub's servers, which fires whether or not
 * this phone is awake; a client that also dispatched runs would double them
 * and burn the seen-tenders cache for no gain.
 */
class PollWorker(
    context: Context,
    params: WorkerParameters,
) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val app = applicationContext as? TenderMonitorApp ?: return Result.success()
        val graph = app.graph
        val settings = graph.settings.settings()
        val state = graph.pollState
        val notifier = Notifier(applicationContext)

        // Switched off, or never set up. Not a failure, and not something to
        // retry: there is nothing to check.
        if (settings.pollMinutes <= 0) return Result.success()
        if (!graph.settings.hasToken()) {
            state.recordAttempt(success = false, note = "No token yet.")
            return Result.success()
        }

        when (val runs = graph.reports.runs(limit = 5)) {
            is Outcome.Failed -> {
                val failures = state.recordFailure(runs.problem.headline)
                if (settings.notifyOnFailures) {
                    RunNotice.forTrouble(runs.problem, failures)?.let(notifier::post)
                }
                return when (PollPolicy.verdictFor(runs.problem)) {
                    PollPolicy.Verdict.RETRY -> Result.retry()
                    // Not a failure to WorkManager: returning failure would
                    // cancel the periodic work entirely, and an expired token
                    // would then silently end background checking forever.
                    else -> Result.success()
                }
            }

            is Outcome.Ok -> {
                val newest = runs.value
                    .filter { it.isFinished }
                    .maxByOrNull { it.id }

                if (newest == null) {
                    state.recordAttempt(success = true, note = "No finished run yet.")
                    notifier.clearTrouble()
                    return Result.success()
                }

                if (!PollPolicy.isNewsworthy(newest.id, newest.isFinished,
                                             state.lastNotifiedRunId())) {
                    // Nothing new. Recorded, so "no notifications" is
                    // distinguishable from "no checks" in Settings.
                    state.recordAttempt(success = true,
                                        note = "Nothing new since run #${newest.runNumber}.")
                    notifier.clearTrouble()
                    return Result.success()
                }

                return when (val loaded = graph.reports.fetchReport(newest)) {
                    is Outcome.Ok -> {
                        val report = loaded.value.report
                        val notice = RunNotice.forReport(report, newest.runNumber)
                        val wanted = when (notice.channel) {
                            RunNotice.Channel.RESULTS -> settings.notifyOnResults
                            RunNotice.Channel.NEEDS_ATTENTION -> settings.notifyOnFailures
                        }
                        if (wanted) notifier.post(notice)
                        notifier.clearTrouble()
                        // Marked as notified whether or not a notification was
                        // wanted: the run has been seen, and re-announcing it
                        // when the preference flips would be news about
                        // nothing.
                        state.recordNotified(newest.id)
                        state.recordAttempt(
                            success = true,
                            note = "Run #${newest.runNumber}: ${report.run.statusLine}",
                        )
                        Result.success()
                    }

                    is Outcome.Failed -> {
                        // The run finished and its report could not be read.
                        // Not marked as notified, so the next check tries
                        // again rather than skipping a run forever.
                        val failures = state.recordFailure(
                            "Run #${newest.runNumber}: ${loaded.problem.headline}")
                        if (settings.notifyOnFailures) {
                            RunNotice.forTrouble(loaded.problem, failures)?.let(notifier::post)
                        }
                        when (PollPolicy.verdictFor(loaded.problem)) {
                            PollPolicy.Verdict.RETRY -> Result.retry()
                            else -> Result.success()
                        }
                    }
                }
            }
        }
    }

    companion object {
        const val NAME = "jordan-tender-poll"
    }
}
