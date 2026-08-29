package jo.tendermonitor.work

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import jo.tendermonitor.R
import jo.tendermonitor.ui.MainActivity

/**
 * Posting the notice.
 *
 * Two channels, deliberately. Someone who mutes "12 new opportunities" during
 * a busy fortnight must not thereby mute "nothing could be read for four
 * days" — those are different messages with different consequences, and
 * Android only lets a person tune them separately if they arrive on separate
 * channels.
 */
class Notifier(private val context: Context) {

    fun ensureChannels() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(NotificationManager::class.java) ?: return

        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_RESULTS,
                "Run results",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "A run finished. Opportunities, or a quiet day " +
                    "where every portal was read."
            }
        )

        manager.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ATTENTION,
                "Needs attention",
                // HIGH so it can make a sound and appear as a heads-up. This
                // is the channel a broken monitor arrives on, and a broken
                // monitor that whispers is the failure this whole system is
                // built to prevent.
                NotificationManager.IMPORTANCE_HIGH,
            ).apply {
                description = "The monitor could not read its sources, or this " +
                    "app can no longer check."
            }
        )
    }

    /** True when Android will actually deliver what we post. */
    fun canPost(): Boolean {
        if (!NotificationManagerCompat.from(context).areNotificationsEnabled()) return false
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return true
        return ContextCompat.checkSelfPermission(
            context, android.Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
    }

    fun post(notice: RunNotice.Notice) {
        if (!canPost()) return
        ensureChannels()

        val channel = when (notice.channel) {
            RunNotice.Channel.RESULTS -> CHANNEL_RESULTS
            RunNotice.Channel.NEEDS_ATTENTION -> CHANNEL_ATTENTION
        }

        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
            putExtra(EXTRA_DESTINATION, notice.destination.name)
        }
        val pending = PendingIntent.getActivity(
            context,
            notice.id,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )

        val notification: Notification = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(notice.title)
            .setContentText(notice.body)
            // The body carries the distinction between a quiet run and a
            // broken one. Truncating it to one line on the lock screen would
            // throw that away, so it expands.
            .setStyle(NotificationCompat.BigTextStyle().bigText(notice.body))
            .setPriority(
                if (notice.channel == RunNotice.Channel.NEEDS_ATTENTION) {
                    NotificationCompat.PRIORITY_HIGH
                } else {
                    NotificationCompat.PRIORITY_DEFAULT
                }
            )
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()

        try {
            NotificationManagerCompat.from(context).notify(notice.id, notification)
        } catch (_: SecurityException) {
            // The permission was revoked between the check and the post.
            // Nothing to do, and nothing worth crashing a background job over.
        }
    }

    fun clearTrouble() {
        NotificationManagerCompat.from(context).cancel(RunNotice.ID_TROUBLE)
    }

    companion object {
        const val CHANNEL_RESULTS = "run-results"
        const val CHANNEL_ATTENTION = "needs-attention"
        const val EXTRA_DESTINATION = "jo.tendermonitor.DESTINATION"
    }
}
