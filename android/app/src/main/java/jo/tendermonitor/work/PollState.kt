package jo.tendermonitor.work

import android.content.Context
import android.content.SharedPreferences

/**
 * What the background checks have been doing.
 *
 * This is the answer to the only question a notification system cannot answer
 * for itself: **is the silence good news or no news?** With nothing recorded,
 * "you have had no notifications this week" means either no runs worth telling
 * you about or no checks at all, and those are the two states this whole
 * codebase exists to keep apart.
 *
 * So every attempt is recorded, successful or not, and Settings prints it.
 *
 * Plain SharedPreferences, not the encrypted store: none of this is secret,
 * and it is written from a background worker on every check. Nothing here is a
 * credential, and nothing here would matter to anyone reading the file.
 */
class PollState(context: Context) {

    private val prefs: SharedPreferences =
        context.getSharedPreferences("poll-state", Context.MODE_PRIVATE)

    fun lastNotifiedRunId(): Long = prefs.getLong(KEY_LAST_RUN, 0L)

    fun recordNotified(runId: Long) {
        prefs.edit().putLong(KEY_LAST_RUN, runId).apply()
    }

    /** A check that reached GitHub. Clears the consecutive-failure count. */
    fun recordAttempt(success: Boolean, note: String, nowMillis: Long = System.currentTimeMillis()) {
        prefs.edit()
            .putLong(KEY_LAST_ATTEMPT, nowMillis)
            .putString(KEY_LAST_NOTE, note)
            .apply {
                if (success) {
                    putLong(KEY_LAST_SUCCESS, nowMillis)
                    putInt(KEY_FAILURES, 0)
                }
            }
            .apply()
    }

    /** A check that did not. Returns how many have failed in a row. */
    fun recordFailure(note: String, nowMillis: Long = System.currentTimeMillis()): Int {
        val failures = prefs.getInt(KEY_FAILURES, 0) + 1
        prefs.edit()
            .putLong(KEY_LAST_ATTEMPT, nowMillis)
            .putString(KEY_LAST_NOTE, note)
            .putInt(KEY_FAILURES, failures)
            .apply()
        return failures
    }

    fun lastAttemptMillis(): Long = prefs.getLong(KEY_LAST_ATTEMPT, 0L)
    fun lastSuccessMillis(): Long = prefs.getLong(KEY_LAST_SUCCESS, 0L)
    fun lastNote(): String = prefs.getString(KEY_LAST_NOTE, "").orEmpty()
    fun consecutiveFailures(): Int = prefs.getInt(KEY_FAILURES, 0)

    /** Forgetting what has been seen, so the next check reports the latest run. */
    fun reset() {
        prefs.edit().clear().apply()
    }

    private companion object {
        const val KEY_LAST_RUN = "last_notified_run"
        const val KEY_LAST_ATTEMPT = "last_attempt"
        const val KEY_LAST_SUCCESS = "last_success"
        const val KEY_LAST_NOTE = "last_note"
        const val KEY_FAILURES = "consecutive_failures"
    }
}
