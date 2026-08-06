package jo.tendermonitor

import android.app.NotificationManager
import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import jo.tendermonitor.work.Notifier
import jo.tendermonitor.work.PollState
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Notification channels and the poll record, on a real device.
 *
 * Channels are a framework object. Creating one wrong -- the same id for both,
 * or an importance that makes failures silent -- is invisible to a unit test
 * and produces an app that never tells anyone anything.
 *
 * The separation matters more than it looks: results and failures are separate
 * channels precisely so someone can silence "12 new opportunities" without also
 * silencing "3 portals unavailable". One channel would make that impossible,
 * and would look identical in code review.
 */
@RunWith(AndroidJUnit4::class)
class NotifierInstrumentedTest {

    private val context: Context
        get() = ApplicationProvider.getApplicationContext()

    private val manager: NotificationManager
        get() = context.getSystemService(NotificationManager::class.java)

    @Before
    fun setUp() {
        Notifier(context).ensureChannels()
    }

    @Test
    fun both_channels_exist_after_ensure() {
        assertNotNull(
            "the results channel was not created",
            manager.getNotificationChannel(Notifier.CHANNEL_RESULTS),
        )
        assertNotNull(
            "the attention channel was not created",
            manager.getNotificationChannel(Notifier.CHANNEL_ATTENTION),
        )
    }

    @Test
    fun results_and_failures_are_genuinely_two_channels() {
        // If these ever became the same id, silencing routine results would
        // silence outage alerts too, and nothing in the code would look wrong.
        assertTrue(Notifier.CHANNEL_RESULTS != Notifier.CHANNEL_ATTENTION)

        val results = manager.getNotificationChannel(Notifier.CHANNEL_RESULTS)
        val attention = manager.getNotificationChannel(Notifier.CHANNEL_ATTENTION)

        assertTrue(results.id != attention.id)
        assertTrue(
            "a portal outage must not be quieter than a routine result",
            attention.importance >= results.importance,
        )
    }

    @Test
    fun ensuring_channels_twice_is_harmless() {
        // Called on every launch and again before every post. If that were
        // destructive it would reset a user's own channel settings each time.
        Notifier(context).ensureChannels()
        Notifier(context).ensureChannels()

        assertNotNull(manager.getNotificationChannel(Notifier.CHANNEL_RESULTS))
        assertNotNull(manager.getNotificationChannel(Notifier.CHANNEL_ATTENTION))
    }

    @Test
    fun the_poll_record_survives_a_new_instance() {
        val state = PollState(context)
        state.reset()

        state.recordNotified(4242)
        state.recordAttempt(success = true, note = "Nothing new since run #7")

        val reread = PollState(context)
        assertEquals(4242L, reread.lastNotifiedRunId())
        assertEquals("Nothing new since run #7", reread.lastNote())
        assertTrue(reread.lastSuccessMillis() > 0)

        state.reset()
    }

    @Test
    fun consecutive_failures_count_up_and_a_success_clears_them() {
        val state = PollState(context)
        state.reset()

        assertEquals(1, state.recordFailure("first"))
        assertEquals(2, state.recordFailure("second"))
        assertEquals(2, state.consecutiveFailures())

        // A success has to clear the count, or a single bad afternoon would
        // leave the app permanently claiming it is in trouble.
        state.recordAttempt(success = true, note = "fine now")
        assertEquals(0, state.consecutiveFailures())

        state.reset()
    }

    @Test
    fun a_failed_attempt_does_not_count_as_a_successful_check() {
        // This is the distinction the whole Settings line rests on: "no
        // notifications" means either no news or no checks, and only the last
        // successful check tells you which.
        val state = PollState(context)
        state.reset()

        state.recordFailure("offline")

        assertEquals(0L, state.lastSuccessMillis())
        assertTrue(state.lastAttemptMillis() > 0)

        state.reset()
    }
}
