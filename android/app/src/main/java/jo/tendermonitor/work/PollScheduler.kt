package jo.tendermonitor.work

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
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

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(PollWorker.NAME)
    }
}
