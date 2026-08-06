package jo.tendermonitor.work

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Problem

/**
 * When to check, when to give up, and when to say nothing at all.
 *
 * Pure and tested, because the alternative is a background job whose
 * behaviour can only be observed by leaving a phone alone for a day.
 */
object PollPolicy {

    /**
     * The intervals offered, in minutes. 0 means off.
     *
     * WorkManager's floor for periodic work is 15 minutes; nothing here is
     * anywhere near it. The monitor itself runs on a weekday schedule at 07:17
     * Amman, so anything shorter than an hour is checking for something that
     * changes once a day.
     */
    val INTERVALS = listOf(
        0 to "Off",
        60 to "Every hour",
        180 to "Every 3 hours",
        360 to "Every 6 hours",
        1440 to "Once a day",
    )

    /**
     * What one check costs GitHub, at worst.
     *
     * A check is one request to list runs, plus — only when there is a new
     * finished run to read — an artifacts listing and a download. Against
     * 5,000 requests an hour for an authenticated token, hourly checks use
     * roughly 0.05% of the budget. The reason not to check more often is
     * battery and data, not the rate limit.
     */
    const val REQUESTS_PER_CHECK = 3

    fun describeCost(intervalMinutes: Int): String = when {
        intervalMinutes <= 0 -> "No background checks. The app only looks when " +
            "you open it."
        else -> {
            val perDay = (24 * 60) / intervalMinutes
            "About $perDay checks a day, up to ${perDay * REQUESTS_PER_CHECK} " +
                "requests against a budget of 5,000 an hour. The cost is " +
                "battery and data, not the rate limit."
        }
    }

    /** What the worker should do after an attempt. */
    enum class Verdict {
        /** Nothing to do, and nothing wrong. */
        DONE,

        /** Try again later, with backoff. The failure is temporary. */
        RETRY,

        /** Do not retry this interval. Something needs a person. */
        GIVE_UP,
    }

    /**
     * Whether a failed check is worth retrying before the next interval.
     *
     * Retrying a 401 in fifteen minutes will produce another 401 — and a
     * backoff loop against a revoked credential is how an app gets its
     * requests rate-limited on top of being broken. A rate limit, by
     * contrast, lifts on its own and is exactly what backoff is for.
     */
    fun verdictFor(problem: Problem): Verdict = when (problem.kind) {
        Kind.OFFLINE, Kind.SERVER, Kind.RATE_LIMITED -> Verdict.RETRY
        Kind.UNAUTHORIZED, Kind.FORBIDDEN, Kind.NOT_FOUND, Kind.NO_TOKEN -> Verdict.GIVE_UP
        else -> Verdict.GIVE_UP
    }

    /**
     * How long to wait before retrying, in minutes.
     *
     * A rate limit says when it lifts; waiting exactly that long is both
     * politer and faster than doubling blindly. Everything else doubles from
     * fifteen minutes, capped so a long outage does not push the next attempt
     * past the next scheduled interval anyway.
     */
    fun backoffMinutes(problem: Problem, attempt: Int, nowEpochSeconds: Long): Int {
        problem.retryAtEpochSeconds?.let { resetAt ->
            val seconds = resetAt - nowEpochSeconds
            if (seconds > 0) {
                // Round up, and add a minute: coming back the instant the
                // window rolls over is how you get rate-limited again.
                return ((seconds / 60) + 2).toInt().coerceAtMost(MAX_BACKOFF_MINUTES)
            }
        }
        val doubled = 15 * (1 shl attempt.coerceIn(0, 5))
        return doubled.coerceAtMost(MAX_BACKOFF_MINUTES)
    }

    const val MAX_BACKOFF_MINUTES = 6 * 60

    /**
     * Whether this run is one the user has not been told about.
     *
     * Only finished runs count. A run in progress is not news, and notifying
     * on it would mean notifying twice for the same run — which trains people
     * to ignore the second one, and the second one is the one with the report
     * in it.
     */
    fun isNewsworthy(
        runId: Long,
        finished: Boolean,
        lastNotifiedRunId: Long,
    ): Boolean = finished && runId > lastNotifiedRunId

    /**
     * How stale the last successful check is, in words.
     *
     * Shown in Settings, and it exists because silence is the one thing this
     * app cannot distinguish for you: no notifications means either no news or
     * no checks, and only this line says which.
     */
    fun describeLastCheck(lastCheckMillis: Long, nowMillis: Long): String {
        if (lastCheckMillis <= 0) return "Never checked in the background yet."
        val minutes = ((nowMillis - lastCheckMillis) / 60_000).coerceAtLeast(0)
        return when {
            minutes < 2 -> "Checked just now."
            minutes < 60 -> "Checked $minutes minutes ago."
            minutes < 60 * 24 -> "Checked ${minutes / 60} hour${s(minutes / 60)} ago."
            else -> "Checked ${minutes / (60 * 24)} day${s(minutes / (60 * 24))} ago."
        }
    }

    private fun s(n: Long) = if (n == 1L) "" else "s"
}
