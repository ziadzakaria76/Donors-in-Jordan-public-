package jo.tendermonitor.work

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import jo.tendermonitor.data.settings.AppSettings
import java.util.concurrent.TimeUnit

/**
 * Registering the background check with WorkManager.
 *
 * TWO CONSTRAINTS, BOTH DELIBERATE.
 *
 * **Not on a metered connection unless asked.** Checking hourly over mobile
 * data to find out that nothing has changed spends someone's allowance without
 * asking. The default is unmetered only, and turning it off is a switch with
 * the consequence written next to it.
 *
 * **Backoff on failure, exponential, from fifteen minutes.** A rate limit or
 * an outage should not be met with the same request every fifteen minutes
 * forever — that is how a temporarily throttled app becomes a permanently
 * throttled one.
 */
object PollScheduler {

    fun apply(context: Context, settings: AppSettings) {
        val manager = WorkManager.getInstance(context)

        if (settings.pollMinutes <= 0) {
            manager.cancelUniqueWork(PollWorker.NAME)
            return
        }

        val constraints = Constraints.Builder()
            .setRequiredNetworkType(
                if (settings.pollOnMetered) NetworkType.CONNECTED else NetworkType.UNMETERED
            )
            // Not while the battery is critically low. A tender report is
            // never worth the last 5% of someone's phone.
            .setRequiresBatteryNotLow(true)
            .build()

        val request = PeriodicWorkRequestBuilder<PollWorker>(
            settings.pollMinutes.toLong(), TimeUnit.MINUTES,
        )
            .setConstraints(constraints)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 15, TimeUnit.MINUTES)
            .build()

        manager.enqueueUniquePeriodicWork(
            PollWorker.NAME,
            // UPDATE rather than KEEP: changing the interval in Settings has
            // to take effect, and KEEP would silently leave the old one
            // running — a setting that looks applied and is not.
            ExistingPeriodicWorkPolicy.UPDATE,
            request,
        )
    }

    /**
     * One extra check, at a time GitHub named.
     *
     * WorkManager's own backoff doubles blindly, which is the right shape when
     * nobody knows how long the trouble lasts. A rate limit is the case where
     * somebody does: the response carries the reset time. Doubling past it
     * wastes hours; doubling short of it earns another rejection. So the reset
     * time is honoured with a one-off request instead.
     *
     * REPLACE, not append: a second rate limit before the first retry fires
     * should move the appointment, not queue a second one.
     */
    fun scheduleRetry(context: Context, delayMinutes: Int) {
        val request = OneTimeWorkRequestBuilder<PollWorker>()
            .setInitialDelay(delayMinutes.toLong(), TimeUnit.MINUTES)
            // Deliberately no network constraint. The periodic check owns the
            // unmetered-only policy; this one is already scheduled for a
            // moment that was chosen, and adding a constraint could delay it
            // past the next ordinary check, making it pointless.
            .build()

        WorkManager.getInstance(context).enqueueUniqueWork(
            RETRY_NAME,
            ExistingWorkPolicy.REPLACE,
            request,
        )
    }

    fun cancel(context: Context) {
        val manager = WorkManager.getInstance(context)
        manager.cancelUniqueWork(PollWorker.NAME)
        // Otherwise switching background checks off leaves a pending retry
        // that fires once more afterwards -- a notification from a feature the
        // user had just turned off.
        manager.cancelUniqueWork(RETRY_NAME)
    }

    const val RETRY_NAME = "jordan-tender-poll-retry"
}
