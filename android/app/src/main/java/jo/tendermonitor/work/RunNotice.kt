package jo.tendermonitor.work

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Problem
import jo.tendermonitor.data.report.Report

/**
 * What a finished run says, in the two lines a notification gets.
 *
 * Pure, and separated from everything Android for one reason: this is where
 * the backend's central rule either survives onto the lock screen or dies
 * there. "No new opportunities" and "nothing could be read" must never render
 * the same, and a notification is the most compressed place in the whole
 * system — the easiest place to collapse them by accident, and the worst,
 * because it is the only part most people will read.
 *
 * So the mapping is a table with a test on it rather than a string built at
 * the call site.
 */
object RunNotice {

    /**
     * Two channels, so failures can be made noisier than results.
     *
     * A person who mutes "12 new opportunities" on a busy week must not
     * thereby mute "nothing could be read for four days".
     */
    enum class Channel { RESULTS, NEEDS_ATTENTION }

    /** Where tapping it should land. */
    enum class Destination { LATEST, HEALTH, SETTINGS }

    data class Notice(
        val channel: Channel,
        val title: String,
        val body: String,
        val destination: Destination,
        /** Stable per subject, so a later notice replaces an earlier one. */
        val id: Int,
    )

    const val ID_RUN = 1001
    const val ID_TROUBLE = 1002

    /**
     * The notice for a finished run.
     *
     * Four outcomes, four sentences. The counts are always both numbers where
     * two exist: "4 opportunities, 3 of 13 portals unavailable" says something
     * "4 opportunities" does not, and the thing it says is the reason to open
     * the app.
     */
    fun forReport(report: Report, runNumber: Int): Notice {
        val run = report.run
        val opportunities = run.opportunityCount
        val broken = run.portalsBroken
        val total = run.portalsTotal

        return when (run.status) {
            "action_needed" -> Notice(
                channel = Channel.NEEDS_ATTENTION,
                title = "ACTION NEEDED — nothing could be read",
                body = "Run #$runNumber could not reach any of its $total portals. " +
                    "This report is empty because nothing was read, not because " +
                    "nothing was published.",
                destination = Destination.HEALTH,
                id = ID_RUN,
            )

            "partial" -> Notice(
                channel = Channel.NEEDS_ATTENTION,
                title = if (opportunities == 0) {
                    "ACTION NEEDED — $broken of $total portals unavailable"
                } else {
                    "$opportunities ${plural(opportunities)}, $broken of $total " +
                        "portals unavailable"
                },
                body = "The picture is incomplete: whatever those portals " +
                    "published is missing from this report, and the report " +
                    "cannot say what.",
                destination = Destination.HEALTH,
                id = ID_RUN,
            )

            "quiet" -> Notice(
                channel = Channel.RESULTS,
                title = "No new opportunities — all $total portals read",
                body = "Run #$runNumber read ${run.scanned} notices and nothing " +
                    "new matched. A genuine quiet run, not a failure.",
                destination = Destination.LATEST,
                id = ID_RUN,
            )

            else -> Notice(
                channel = Channel.RESULTS,
                title = "$opportunities new ${plural(opportunities)}",
                body = "Run #$runNumber read ${run.scanned} notices across " +
                    "$total portals. All of them were read successfully.",
                destination = Destination.LATEST,
                id = ID_RUN,
            )
        }
    }

    /**
     * The notice for the app not being able to check at all.
     *
     * This is the gap that matters most and is easiest to leave open. A token
     * that expired, a repository that moved, a permission that was narrowed:
     * all of them stop the checks, and without this the app simply goes quiet
     * — which looks exactly like a week with no new tenders.
     *
     * Returns null for the failures that are genuinely not worth waking anyone
     * for: no connection, GitHub having a bad afternoon, a rate limit that
     * lifts by itself. Those retry.
     */
    fun forTrouble(problem: Problem, consecutiveFailures: Int): Notice? = when (problem.kind) {
        Kind.UNAUTHORIZED -> Notice(
            channel = Channel.NEEDS_ATTENTION,
            title = "The monitor cannot check — token refused",
            body = "GitHub is rejecting the token, so this app has stopped " +
                "seeing runs. Fine-grained tokens expire without warning. " +
                "Open Settings and paste a new one.",
            destination = Destination.SETTINGS,
            id = ID_TROUBLE,
        )

        Kind.FORBIDDEN -> Notice(
            channel = Channel.NEEDS_ATTENTION,
            title = "The monitor cannot check — permission denied",
            body = "The token is valid but is not allowed to read this " +
                "repository's runs. It needs Actions: read.",
            destination = Destination.SETTINGS,
            id = ID_TROUBLE,
        )

        Kind.NOT_FOUND -> Notice(
            channel = Channel.NEEDS_ATTENTION,
            title = "The monitor cannot check — repository not found",
            body = "Either the repository or the workflow file is wrong, or the " +
                "token cannot see it. GitHub answers 404 for both.",
            destination = Destination.SETTINGS,
            id = ID_TROUBLE,
        )

        Kind.NO_TOKEN -> null   // Nothing has been set up yet. Not a fault.

        // Transient. One bad afternoon is not worth a notification; several
        // days of them is, because by then the silence is indistinguishable
        // from "no new tenders".
        else -> if (consecutiveFailures >= TROUBLE_AFTER_FAILURES) {
            Notice(
                channel = Channel.NEEDS_ATTENTION,
                title = "The monitor has not checked in for a while",
                body = "$consecutiveFailures checks in a row have failed: " +
                    "${problem.headline}. Nothing is necessarily wrong with the " +
                    "monitor itself — but this app cannot tell you either way " +
                    "while it cannot reach GitHub.",
                destination = Destination.SETTINGS,
                id = ID_TROUBLE,
            )
        } else {
            null
        }
    }

    /**
     * How many consecutive failures before saying so.
     *
     * At an hourly interval this is most of a day. Low enough that a dead
     * token is caught before a whole week of reports is missed, high enough
     * that a train journey does not produce a notification.
     */
    const val TROUBLE_AFTER_FAILURES = 8

    private fun plural(n: Int) = if (n == 1) "opportunity" else "opportunities"
}
