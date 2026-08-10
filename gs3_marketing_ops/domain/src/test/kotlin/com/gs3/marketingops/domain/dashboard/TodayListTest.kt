package com.gs3.marketingops.domain.dashboard

import com.gs3.marketingops.domain.lead.LeadStage
import com.gs3.marketingops.domain.lead.NationalityCategory
import com.gs3.marketingops.domain.lead.lead
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.time.Duration
import java.time.Instant

class TodayListTest {

    private val now = Instant.parse("2026-08-10T12:00:00Z")

    @Test
    fun `an overdue first response is surfaced`() {
        val actions = TodayList.compute(
            DashboardInput(
                now = now,
                leads = listOf(lead("L1")),
                firstResponseDueAt = mapOf("L1" to now.minusSeconds(600)),
            )
        )
        assertEquals(1, actions.size)
        assertEquals(ActionKind.OVERDUE_FIRST_RESPONSE, actions.single().kind)
        assertTrue(actions.single().isOverdue)
    }

    @Test
    fun `a first response still inside its window is not an action yet`() {
        val actions = TodayList.compute(
            DashboardInput(
                now = now,
                leads = listOf(lead("L1")),
                firstResponseDueAt = mapOf("L1" to now.plusSeconds(300)),
            )
        )
        assertTrue(actions.isEmpty())
    }

    @Test
    fun `a lead already replied to is not chased for a first response`() {
        val actions = TodayList.compute(
            DashboardInput(
                now = now,
                leads = listOf(lead("L1", stage = LeadStage.QUALIFIED)),
                firstResponseDueAt = mapOf("L1" to now.minusSeconds(6000)),
            )
        )
        assertTrue(actions.isEmpty())
    }

    @Test
    fun `an offer expiring within three days is surfaced before it expires`() {
        val actions = TodayList.compute(
            DashboardInput(
                now = now,
                leads = listOf(lead("L1", stage = LeadStage.NEGOTIATION)),
                offerExpiresAt = mapOf("L1" to now.plus(Duration.ofDays(2))),
            )
        )
        assertEquals(ActionKind.OFFER_EXPIRING, actions.single().kind)
        assertFalse(actions.single().isOverdue)
    }

    @Test
    fun `an external lead not updated for ten days is surfaced`() {
        val stale = lead(
            "L1",
            category = NationalityCategory.JORDANIAN_EXPATRIATE,
            stage = LeadStage.QUALIFIED,
            lastContactedAt = now.minus(Duration.ofDays(11)),
        )
        val actions = TodayList.compute(DashboardInput(now = now, leads = listOf(stale)))
        assertEquals(ActionKind.EXTERNAL_UPDATE_DUE, actions.single().kind)
    }

    @Test
    fun `a local lead is never chased on the external-track clock`() {
        val quiet = lead(
            "L1",
            category = NationalityCategory.JORDANIAN_RESIDENT,
            stage = LeadStage.QUALIFIED,
            lastContactedAt = now.minus(Duration.ofDays(20)),
        )
        assertTrue(TodayList.compute(DashboardInput(now = now, leads = listOf(quiet))).isEmpty())
    }

    @Test
    fun `a unit with no enquiries for thirty days is surfaced`() {
        val actions = TodayList.compute(
            DashboardInput(
                now = now,
                leads = emptyList(),
                unitsWithoutEnquiriesFor = mapOf(1 to Duration.ofDays(31), 6 to Duration.ofDays(5)),
            )
        )
        assertEquals(1, actions.size)
        assertEquals(ActionKind.UNIT_WITHOUT_ENQUIRIES, actions.single().kind)
        assertEquals(1, actions.single().unitNumber)
    }

    @Test
    fun `urgency beats staleness, so the fifteen-minute clock is never buried`() {
        // The unit has been silent for a hundred days and the response is four
        // minutes late. Sorting on elapsed time alone would put the unit first
        // and bury the one action with a fifteen-minute window — every day.
        val actions = TodayList.compute(
            DashboardInput(
                now = now,
                leads = listOf(lead("L1")),
                firstResponseDueAt = mapOf("L1" to now.minusSeconds(240)),
                unitsWithoutEnquiriesFor = mapOf(1 to Duration.ofDays(100)),
            )
        )
        assertEquals(ActionKind.OVERDUE_FIRST_RESPONSE, actions.first().kind)
        assertEquals(ActionKind.UNIT_WITHOUT_ENQUIRIES, actions.last().kind)
    }

    @Test
    fun `the list is capped at five, keeping the most urgent`() {
        val leads = (1..10).map { lead("L$it") }
        val due = leads.associate { it.id to now.minusSeconds(60L * it.id.drop(1).toInt()) }
        val actions = TodayList.compute(
            DashboardInput(now = now, leads = leads, firstResponseDueAt = due)
        )
        assertEquals(TodayList.MAX_ACTIONS, actions.size)
        // The most overdue come first within a kind.
        assertEquals("L10", actions.first().leadId)
    }

    @Test
    fun `an unknown lead id is ignored rather than crashing the dashboard`() {
        val actions = TodayList.compute(
            DashboardInput(
                now = now,
                leads = emptyList(),
                firstResponseDueAt = mapOf("ghost" to now.minusSeconds(600)),
            )
        )
        assertTrue(actions.isEmpty())
    }
}
