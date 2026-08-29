package jo.tendermonitor

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Problem
import jo.tendermonitor.work.PollPolicy
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * When the background check retries, gives up, and stays quiet.
 *
 * Pure and tested here because the alternative way to find out is to leave a
 * phone alone for a day and see what happened — which is not a way to find out
 * anything, and certainly not a way to find out that nothing did.
 */
class PollPolicyTest {

    @Test
    fun `a rate limit is retried and a revoked token is not`() {
        // Retrying a 401 in fifteen minutes produces another 401, and a
        // backoff loop against a dead credential gets the app rate-limited on
        // top of being broken. A rate limit, by contrast, lifts by itself.
        assertEquals(
            PollPolicy.Verdict.RETRY,
            PollPolicy.verdictFor(Problem("x", kind = Kind.RATE_LIMITED)),
        )
        assertEquals(
            PollPolicy.Verdict.RETRY,
            PollPolicy.verdictFor(Problem("x", kind = Kind.OFFLINE)),
        )
        assertEquals(
            PollPolicy.Verdict.RETRY,
            PollPolicy.verdictFor(Problem("x", kind = Kind.SERVER)),
        )

        for (kind in listOf(Kind.UNAUTHORIZED, Kind.FORBIDDEN, Kind.NOT_FOUND,
                            Kind.NO_TOKEN, Kind.MALFORMED)) {
            assertEquals(
                kind.name,
                PollPolicy.Verdict.GIVE_UP,
                PollPolicy.verdictFor(Problem("x", kind = kind)),
            )
        }
    }

    @Test
    fun `a rate limit is waited out for exactly as long as it says`() {
        val now = 1_000_000L
        val problem = Problem(
            "rate limited", kind = Kind.RATE_LIMITED,
            retryAtEpochSeconds = now + 30 * 60,
        )
        val minutes = PollPolicy.backoffMinutes(problem, attempt = 0, nowEpochSeconds = now)
        // 30 minutes, plus a margin: coming back the instant the window rolls
        // over is how you get rate-limited again.
        assertTrue("got $minutes", minutes in 31..33)
    }

    @Test
    fun `a stale reset time does not produce a negative wait`() {
        val now = 1_000_000L
        val problem = Problem(
            "rate limited", kind = Kind.RATE_LIMITED,
            retryAtEpochSeconds = now - 60,
        )
        val minutes = PollPolicy.backoffMinutes(problem, attempt = 0, nowEpochSeconds = now)
        assertTrue("got $minutes", minutes > 0)
    }

    @Test
    fun `everything else doubles and then stops doubling`() {
        val problem = Problem("offline", kind = Kind.OFFLINE)
        val first = PollPolicy.backoffMinutes(problem, 0, 0)
        val second = PollPolicy.backoffMinutes(problem, 1, 0)
        val far = PollPolicy.backoffMinutes(problem, 20, 0)

        assertEquals(15, first)
        assertEquals(30, second)
        assertEquals(PollPolicy.MAX_BACKOFF_MINUTES, far)
        assertTrue(far <= PollPolicy.MAX_BACKOFF_MINUTES)
    }

    @Test
    fun `only a finished run that has not been announced is news`() {
        assertTrue(PollPolicy.isNewsworthy(runId = 10, finished = true, lastNotifiedRunId = 9))
        assertFalse(
            "the same run must not be announced twice",
            PollPolicy.isNewsworthy(runId = 10, finished = true, lastNotifiedRunId = 10),
        )
        assertFalse(
            "an older run is not news",
            PollPolicy.isNewsworthy(runId = 8, finished = true, lastNotifiedRunId = 10),
        )
        assertFalse(
            "a run in progress has no report to announce",
            PollPolicy.isNewsworthy(runId = 11, finished = false, lastNotifiedRunId = 10),
        )
    }

    @Test
    fun `the first ever check announces the newest finished run`() {
        assertTrue(PollPolicy.isNewsworthy(runId = 1, finished = true, lastNotifiedRunId = 0))
    }

    @Test
    fun `the interval list starts with off and offers nothing sillier than hourly`() {
        val minutes = PollPolicy.INTERVALS.map { it.first }
        assertEquals(0, minutes.first())
        // WorkManager's floor is 15 minutes, and the monitor produces a run
        // once a weekday. Anything under an hour is checking for something
        // that changes daily.
        assertTrue(minutes.filter { it > 0 }.all { it >= 60 })
        assertEquals(minutes.sorted(), minutes)
    }

    @Test
    fun `the cost is stated in both checks and requests`() {
        val off = PollPolicy.describeCost(0)
        assertTrue(off, off.contains("No background checks"))

        val hourly = PollPolicy.describeCost(60)
        assertTrue(hourly, hourly.contains("24 checks a day"))
        assertTrue(hourly, hourly.contains("5,000"))
        // And says which resource actually constrains it, so nobody chooses a
        // longer interval to protect a rate limit that was never at risk.
        assertTrue(hourly, hourly.contains("battery and data"))
    }

    @Test
    fun `the last check is described so silence is legible`() {
        val now = 1_000_000_000L
        assertTrue(PollPolicy.describeLastCheck(0, now).contains("Never"))
        assertTrue(
            PollPolicy.describeLastCheck(now - 30 * 60_000, now).contains("30 minutes"),
        )
        assertTrue(
            PollPolicy.describeLastCheck(now - 3 * 3_600_000, now).contains("3 hours"),
        )
        assertTrue(
            PollPolicy.describeLastCheck(now - 26 * 3_600_000L, now).contains("1 day"),
        )
        // Singular, because "1 hours ago" reads as a bug and makes the rest of
        // the screen less believable.
        assertTrue(
            PollPolicy.describeLastCheck(now - 3_600_000, now).contains("1 hour ago"),
        )
    }
}
