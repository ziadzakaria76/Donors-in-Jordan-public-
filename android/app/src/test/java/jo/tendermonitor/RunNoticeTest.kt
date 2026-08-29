package jo.tendermonitor

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Problem
import jo.tendermonitor.data.report.Report
import jo.tendermonitor.data.report.RunSummary
import jo.tendermonitor.work.RunNotice
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The two lines a notification gets.
 *
 * This is the most compressed place in the whole system and therefore the
 * easiest place to lose the distinction the backend spent months building: a
 * run that read everything and found nothing, and a run that could not read
 * anything, must not arrive as the same sentence. On a lock screen, that
 * sentence is all most people will ever see.
 */
class RunNoticeTest {

    private fun report(
        status: String,
        opportunities: Int = 0,
        broken: Int = 0,
        total: Int = 13,
        scanned: Int = 812,
    ) = Report(
        schema = 1,
        run = RunSummary(
            status = status,
            statusLine = "…",
            opportunityCount = opportunities,
            scanned = scanned,
            portalsTotal = total,
            portalsOk = total - broken,
            portalsBroken = broken,
        ),
    )

    @Test
    fun `a quiet run and a dead run are different notifications`() {
        val quiet = RunNotice.forReport(report("quiet"), 42)
        val dead = RunNotice.forReport(report("action_needed", broken = 13), 42)

        assertNotEquals(quiet.title, dead.title)
        assertTrue(quiet.title.contains("No new opportunities"))
        assertTrue(quiet.title.contains("all 13 portals read"))
        assertTrue(dead.title.contains("ACTION NEEDED"))

        // And they arrive on different channels, so muting one does not mute
        // the other.
        assertEquals(RunNotice.Channel.RESULTS, quiet.channel)
        assertEquals(RunNotice.Channel.NEEDS_ATTENTION, dead.channel)
    }

    @Test
    fun `a dead run says the emptiness is not the news`() {
        val dead = RunNotice.forReport(report("action_needed", broken = 13), 42)
        assertTrue(
            dead.body,
            dead.body.contains("not because") && dead.body.contains("published"),
        )
    }

    @Test
    fun `a good run leads with the count`() {
        val notice = RunNotice.forReport(report("ok", opportunities = 12), 42)
        assertTrue(notice.title.startsWith("12 new opportunities"))
        assertEquals(RunNotice.Channel.RESULTS, notice.channel)
        assertEquals(RunNotice.Destination.LATEST, notice.destination)
    }

    @Test
    fun `one opportunity is not plural`() {
        val notice = RunNotice.forReport(report("ok", opportunities = 1), 7)
        assertTrue(notice.title, notice.title.contains("1 new opportunity"))
        assertFalse(notice.title.contains("opportunities"))
    }

    @Test
    fun `a partial run carries both numbers`() {
        // "4 opportunities" alone hides that the picture is incomplete, which
        // is the only reason to open the app rather than read the notification
        // and move on.
        val notice = RunNotice.forReport(
            report("partial", opportunities = 4, broken = 3), 42,
        )
        assertTrue(notice.title, notice.title.contains("4 opportunities"))
        assertTrue(notice.title, notice.title.contains("3 of 13 portals unavailable"))
        assertEquals(RunNotice.Channel.NEEDS_ATTENTION, notice.channel)
        assertEquals(RunNotice.Destination.HEALTH, notice.destination)
    }

    @Test
    fun `a partial run with nothing found leads with the problem`() {
        val notice = RunNotice.forReport(
            report("partial", opportunities = 0, broken = 3), 42,
        )
        assertTrue(notice.title, notice.title.startsWith("ACTION NEEDED"))
    }

    @Test
    fun `a run that needs attention opens the health screen, not the list`() {
        // Opening the opportunity list from a "3 portals unreachable" notice
        // would show a short report and no reason for it.
        for (status in listOf("action_needed", "partial")) {
            assertEquals(
                status,
                RunNotice.Destination.HEALTH,
                RunNotice.forReport(report(status, broken = 3), 1).destination,
            )
        }
    }

    @Test
    fun `every run notice replaces the previous one rather than stacking`() {
        val a = RunNotice.forReport(report("ok", opportunities = 1), 1)
        val b = RunNotice.forReport(report("quiet"), 2)
        assertEquals(a.id, b.id)
        assertEquals(RunNotice.ID_RUN, a.id)
    }

    // -----------------------------------------------------------------------
    // The app being unable to check at all
    // -----------------------------------------------------------------------

    @Test
    fun `a refused token is reported at once, not after a week of silence`() {
        val notice = RunNotice.forTrouble(
            Problem("GitHub refused the token", kind = Kind.UNAUTHORIZED), 1,
        )
        assertNotNull(notice)
        assertEquals(RunNotice.Channel.NEEDS_ATTENTION, notice!!.channel)
        assertEquals(RunNotice.Destination.SETTINGS, notice.destination)
        assertTrue(notice.body, notice.body.contains("expire"))
    }

    @Test
    fun `a permission problem and a missing repository get their own sentences`() {
        val forbidden = RunNotice.forTrouble(
            Problem("x", kind = Kind.FORBIDDEN), 1)!!
        val missing = RunNotice.forTrouble(
            Problem("x", kind = Kind.NOT_FOUND), 1)!!
        assertNotEquals(forbidden.title, missing.title)
        assertTrue(forbidden.body.contains("Actions: read"))
        assertTrue(missing.body, missing.body.contains("404 for both"))
    }

    @Test
    fun `one bad afternoon is not a notification`() {
        for (kind in listOf(Kind.OFFLINE, Kind.SERVER, Kind.RATE_LIMITED)) {
            assertNull(
                kind.name,
                RunNotice.forTrouble(Problem("x", kind = kind), 1),
            )
        }
    }

    @Test
    fun `but days of them is`() {
        // By then the silence is indistinguishable from "no new tenders",
        // which is exactly the state this app exists to make impossible.
        val notice = RunNotice.forTrouble(
            Problem("No connection", kind = Kind.OFFLINE),
            RunNotice.TROUBLE_AFTER_FAILURES,
        )
        assertNotNull(notice)
        assertTrue(notice!!.body, notice.body.contains("cannot tell you either way"))
    }

    @Test
    fun `no token at all is never a notification`() {
        // Nothing has been set up. That is a setup step, not a fault, and
        // waking someone for it would be the app complaining about itself.
        assertNull(RunNotice.forTrouble(Problem("x", kind = Kind.NO_TOKEN), 99))
    }

    @Test
    fun `trouble notices replace each other and never a run notice`() {
        val trouble = RunNotice.forTrouble(Problem("x", kind = Kind.UNAUTHORIZED), 1)!!
        val run = RunNotice.forReport(report("ok", opportunities = 3), 1)
        assertNotEquals(trouble.id, run.id)
        assertEquals(RunNotice.ID_TROUBLE, trouble.id)
    }
}
