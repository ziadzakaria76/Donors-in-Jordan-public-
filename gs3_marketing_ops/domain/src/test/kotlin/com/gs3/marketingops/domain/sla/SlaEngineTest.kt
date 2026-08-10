package com.gs3.marketingops.domain.sla

import com.gs3.marketingops.domain.funnel.Track
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNotEquals
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.time.DayOfWeek
import java.time.Duration
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

class SlaEngineTest {

    private val amman = ZoneId.of("Asia/Amman")
    private val hours = BusinessHours()

    private fun ammanInstant(date: String, time: String) =
        ZonedDateTime.of(LocalDate.parse(date), LocalTime.parse(time), amman).toInstant()

    @Test
    fun `an enquiry inside business hours is due fifteen minutes later`() {
        // Monday 10:00 Amman.
        val enquiry = ammanInstant("2026-08-10", "10:00")
        val deadline = SlaEngine.firstResponseDeadline(enquiry, hours)
        assertEquals(ammanInstant("2026-08-10", "10:15"), deadline.dueAt)
    }

    @Test
    fun `a fifteen-minute clock started before closing does not expire after hours`() {
        // 17:55 leaves five minutes today; the other ten belong to tomorrow morning.
        val enquiry = ammanInstant("2026-08-10", "17:55")
        val deadline = SlaEngine.firstResponseDeadline(enquiry, hours)
        assertEquals(ammanInstant("2026-08-11", "09:10"), deadline.dueAt)
    }

    @Test
    fun `an overnight enquiry is due at ten the next business morning`() {
        // Monday 23:30 — out of hours, so the promise is a human reply by 10:00.
        val enquiry = ammanInstant("2026-08-10", "23:30")
        val deadline = SlaEngine.firstResponseDeadline(enquiry, hours)
        assertEquals(ammanInstant("2026-08-11", "10:00"), deadline.dueAt)
    }

    @Test
    fun `an early morning enquiry is due the same morning, not the next one`() {
        // 07:00 on a working day. Waiting a whole extra day would be the letter
        // of the rule defeating its point.
        val enquiry = ammanInstant("2026-08-10", "07:00")
        val deadline = SlaEngine.firstResponseDeadline(enquiry, hours)
        assertEquals(ammanInstant("2026-08-10", "10:00"), deadline.dueAt)
    }

    @Test
    fun `a Friday enquiry waits for Saturday, because Saturday is a working day here`() {
        // 2026-08-14 is a Friday: the one weekend day. The company publishes
        // Saturday-Thursday on its own website — see DECISIONS.md D-5.
        assertEquals(DayOfWeek.FRIDAY, LocalDate.parse("2026-08-14").dayOfWeek)
        val enquiry = ammanInstant("2026-08-14", "12:00")
        val deadline = SlaEngine.firstResponseDeadline(enquiry, hours)
        assertEquals(ammanInstant("2026-08-15", "10:00"), deadline.dueAt)
    }

    @Test
    fun `with a Sunday-to-Thursday week a Thursday evening enquiry waits until Sunday`() {
        val sundayToThursday = BusinessHours(
            workingDays = setOf(
                DayOfWeek.SUNDAY, DayOfWeek.MONDAY, DayOfWeek.TUESDAY,
                DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY,
            )
        )
        // Thursday 2026-08-13 at 20:00 -> Sunday 2026-08-16 at 10:00.
        assertEquals(DayOfWeek.THURSDAY, LocalDate.parse("2026-08-13").dayOfWeek)
        val deadline = SlaEngine.firstResponseDeadline(ammanInstant("2026-08-13", "20:00"), sundayToThursday)
        assertEquals(ammanInstant("2026-08-16", "10:00"), deadline.dueAt)
    }

    @Test
    fun `viewing follow-up and written offer run on elapsed time`() {
        val viewed = ammanInstant("2026-08-10", "16:00")
        assertEquals(ammanInstant("2026-08-12", "16:00"), SlaEngine.viewingFollowUpDeadline(viewed).dueAt)
        assertEquals(ammanInstant("2026-08-11", "16:00"), SlaEngine.writtenOfferDeadline(viewed).dueAt)
    }

    @Test
    fun `only external-track leads carry the ten-day update promise`() {
        val contacted = ammanInstant("2026-08-10", "12:00")
        assertNull(SlaEngine.externalStatusUpdateDeadline(contacted, Track.LOCAL))
        val expat = SlaEngine.externalStatusUpdateDeadline(contacted, Track.EXPAT)
        assertEquals(ammanInstant("2026-08-20", "12:00"), expat?.dueAt)
    }

    @Test
    fun `an external lead is not judged stale on the local clock`() {
        assertTrue(SlaEngine.staleAfter(Track.EXPAT) > SlaEngine.staleAfter(Track.LOCAL))
        assertEquals(Duration.ofDays(30), SlaEngine.staleAfter(Track.LOCAL))
    }

    @Test
    fun `deadline state moves from due to approaching to breached`() {
        val due = ammanInstant("2026-08-10", "10:15")
        val deadline = SlaDeadline(SlaRule.FIRST_RESPONSE, due, SlaState.DUE)
        assertEquals(SlaState.DUE, deadline.stateAt(ammanInstant("2026-08-10", "10:00")))
        assertEquals(SlaState.APPROACHING, deadline.stateAt(ammanInstant("2026-08-10", "10:12")))
        assertEquals(SlaState.BREACHED, deadline.stateAt(ammanInstant("2026-08-10", "10:16")))
    }

    @Test
    fun `a working week with no working days is rejected rather than looping forever`() {
        val thrown = runCatching { BusinessHours(workingDays = emptySet()) }.exceptionOrNull()
        assertTrue(thrown is IllegalArgumentException)
    }
}

/**
 * The trap test the brief calls for by name.
 *
 * Amman has been UTC+3 with no daylight saving since 2022. Toronto has not:
 * it moves in March and November. A reminder stored as an offset rather than a
 * zone fires an hour wrong for six months of the year, and nobody notices,
 * because a message arriving at 08:00 instead of 09:00 looks like nothing at
 * all — until it is a call at 05:00 to a client who then stops replying.
 */
class DaylightSavingTest {

    private val toronto = ZoneId.of("America/Toronto")
    private val amman = ZoneId.of("Asia/Amman")

    @Test
    fun `outreach lands at nine in the morning in Toronto on both sides of the spring change`() {
        // Toronto springs forward on Sunday 8 March 2026.
        val beforeChange = ZonedDateTime.of(LocalDate.parse("2026-03-05"), LocalTime.of(14, 0), toronto).toInstant()

        val dayOne = com.gs3.marketingops.domain.sla.NurtureScheduler.scheduleAt(beforeChange, 1, toronto)
        val dayTen = com.gs3.marketingops.domain.sla.NurtureScheduler.scheduleAt(beforeChange, 10, toronto)

        assertEquals(LocalTime.of(9, 0), dayOne.atZone(toronto).toLocalTime())
        assertEquals(LocalTime.of(9, 0), dayTen.atZone(toronto).toLocalTime())

        // The proof it is a zone and not an offset: the same 09:00 sits at a
        // different UTC offset on either side of 8 March.
        assertNotEquals(dayOne.atZone(toronto).offset, dayTen.atZone(toronto).offset)
    }

    @Test
    fun `outreach lands at nine in the morning across the autumn change too`() {
        // Toronto falls back on Sunday 1 November 2026.
        val beforeChange = ZonedDateTime.of(LocalDate.parse("2026-10-29"), LocalTime.of(14, 0), toronto).toInstant()

        val dayOne = com.gs3.marketingops.domain.sla.NurtureScheduler.scheduleAt(beforeChange, 1, toronto)
        val dayTen = com.gs3.marketingops.domain.sla.NurtureScheduler.scheduleAt(beforeChange, 10, toronto)

        assertEquals(LocalTime.of(9, 0), dayOne.atZone(toronto).toLocalTime())
        assertEquals(LocalTime.of(9, 0), dayTen.atZone(toronto).toLocalTime())
        assertNotEquals(dayOne.atZone(toronto).offset, dayTen.atZone(toronto).offset)
    }

    @Test
    fun `the same nine o'clock is a different Amman hour either side of the change`() {
        // This is the failure a naive implementation produces: the salesperson in
        // Amman sees the reminder move by an hour and assumes the app is broken,
        // when in fact the client's country moved.
        val beforeChange = ZonedDateTime.of(LocalDate.parse("2026-03-05"), LocalTime.of(14, 0), toronto).toInstant()
        val dayOne = com.gs3.marketingops.domain.sla.NurtureScheduler.scheduleAt(beforeChange, 1, toronto)
        val dayTen = com.gs3.marketingops.domain.sla.NurtureScheduler.scheduleAt(beforeChange, 10, toronto)

        // 09:00 in Toronto is 17:00 in Amman while Toronto is on EST (UTC-5),
        // and 16:00 once it moves to EDT (UTC-4) on 8 March.
        assertEquals(LocalTime.of(17, 0), dayOne.atZone(amman).toLocalTime())
        assertEquals(LocalTime.of(16, 0), dayTen.atZone(amman).toLocalTime())
    }

    @Test
    fun `a nine o'clock that does not exist is moved forward, not thrown away`() {
        // 02:30 on a spring-forward Sunday is a time that never happens. Scheduling
        // a reminder there must not crash and must not silently vanish.
        val friday = ZonedDateTime.of(LocalDate.parse("2026-03-06"), LocalTime.of(12, 0), toronto).toInstant()
        val inTheGap = com.gs3.marketingops.domain.sla.NurtureScheduler
            .scheduleAt(friday, 2, toronto, LocalTime.of(2, 30))

        val local = inTheGap.atZone(toronto)
        assertEquals(LocalDate.parse("2026-03-08"), local.toLocalDate())
        assertEquals(LocalTime.of(3, 30), local.toLocalTime())
    }

    @Test
    fun `Amman itself never shifts, so a local lead is unaffected`() {
        val start = ZonedDateTime.of(LocalDate.parse("2026-03-05"), LocalTime.of(14, 0), amman).toInstant()
        val dayOne = com.gs3.marketingops.domain.sla.NurtureScheduler.scheduleAt(start, 1, amman)
        val dayTen = com.gs3.marketingops.domain.sla.NurtureScheduler.scheduleAt(start, 10, amman)
        assertEquals(dayOne.atZone(amman).offset, dayTen.atZone(amman).offset)
        assertFalse(amman.rules.isDaylightSavings(dayTen))
    }

    @Test
    fun `the whole nurture sequence stays at nine local through a change`() {
        val start = ZonedDateTime.of(LocalDate.parse("2026-03-01"), LocalTime.of(18, 0), toronto).toInstant()
        val sequence = com.gs3.marketingops.domain.sla.NurtureScheduler.sequenceFor(start, toronto)
        assertEquals(6, sequence.size)
        assertTrue(sequence.all { it.atZone(toronto).toLocalTime() == LocalTime.of(9, 0) })
        // The sequence spans 1 March to 31 March, so it straddles 8 March.
        assertNotEquals(sequence.first().atZone(toronto).offset, sequence.last().atZone(toronto).offset)
    }
}
