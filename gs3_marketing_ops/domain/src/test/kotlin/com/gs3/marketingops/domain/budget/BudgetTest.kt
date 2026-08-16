package com.gs3.marketingops.domain.budget

import com.gs3.marketingops.domain.money.Jod
import com.gs3.marketingops.domain.money.sum
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNotNull
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.math.BigDecimal
import java.time.Month

class BudgetAllocationTest {

    @Test
    fun `market rows sum exactly to their track totals`() {
        assertEquals(Jod.ofDinars(4_680), Gs3Budget.expatriateTotal)
        assertEquals(Jod.ofDinars(2_520), Gs3Budget.nonJordanianTotal)
        assertEquals(Jod.ofDinars(7_200), Gs3Budget.externalTrackTotal)
    }

    @Test
    fun `the external track takes forty per cent of paid media, split sixty-five thirty-five`() {
        assertEquals(BigDecimal("0.400000"), Gs3Budget.externalTrackTotal.ratioOf(Gs3Budget.totalPaidMedia))
        assertEquals(BigDecimal("0.650000"), Gs3Budget.expatriateTotal.ratioOf(Gs3Budget.externalTrackTotal))
        assertEquals(BigDecimal("0.350000"), Gs3Budget.nonJordanianTotal.ratioOf(Gs3Budget.externalTrackTotal))
    }

    @Test
    fun `local media is whatever the external track does not take`() {
        assertEquals(Jod.ofDinars(10_800), Gs3Budget.localTrackTotal)
        assertEquals(Gs3Budget.totalPaidMedia, Gs3Budget.localTrackTotal + Gs3Budget.externalTrackTotal)
    }

    @Test
    fun `the displayed monthly figures match the brief's table`() {
        val monthly = Gs3Budget.externalTrackMarkets.associate { it.marketKey to it.monthlyDisplayDinars }
        assertEquals(114L, monthly.getValue("UAE"))
        assertEquals(104L, monthly.getValue("USA"))
        assertEquals(93L, monthly.getValue("KSA"))
        assertEquals(50L, monthly.getValue("QAT"))
        assertEquals(28L, monthly.getValue("KWT"))
        assertEquals(105L, monthly.getValue("IRQ"))
        assertEquals(47L, monthly.getValue("GULF"))
        assertEquals(35L, monthly.getValue("PSE"))
        assertEquals(23L, monthly.getValue("TEST"))
    }

    @Test
    fun `the displayed monthly figures do not re-sum, which is why they are never added up`() {
        // DECISIONS.md D-4, made executable. Rounded to whole dinars the way the
        // strategy document prints them, the five expatriate markets total 389
        // JOD a month against a true 390 — a dinar a month, twelve a year, and
        // it grows with every market added.
        val displayedSum = Gs3Budget.expatriateMarkets.sumOf { it.monthlyDisplayDinars }
        assertEquals(389L, displayedSum)
        assertEquals(Jod.ofDinars(390), Gs3Budget.expatriateTotal.dividedBy(12))
    }

    @Test
    fun `the exact monthly figures do re-sum, which is what the app computes with`() {
        // Held to the fils, the same nine markets add straight back up to the
        // annual figure. This is the reason the app never stores the rounding.
        val exactSum = Gs3Budget.expatriateMarkets.map { it.monthlyIndicative }.sum()
        assertEquals(Gs3Budget.expatriateTotal.dividedBy(12), exactSum)
        assertEquals(Jod.ofDinars(390), exactSum)
        assertTrue(Jod.ofDinars(389) < exactSum)
    }

    @Test
    fun `the four-week test budget is capped at fifteen per cent`() {
        assertEquals(Jod.ofDinars(2_700), Gs3Budget.testBudgetCeiling)
        assertFalse(Gs3Budget.isTestBudgetExceeded(Jod.ofDinars(2_700)))
        assertTrue(Gs3Budget.isTestBudgetExceeded(Jod.ofDinars(2_701)))
    }
}

class SeasonalityTest {

    @Test
    fun `a month in no season takes one`() {
        val calendar = SeasonCalendar()
        assertEquals(BigDecimal.ONE, calendar.multiplierFor(Month.FEBRUARY))
        assertEquals(BigDecimal("1.8"), calendar.multiplierFor(Month.JULY))
        assertEquals(BigDecimal("0.7"), calendar.multiplierFor(Month.SEPTEMBER))
    }

    @Test
    fun `overlapping seasons compose by the larger, never by multiplying`() {
        // Ramadan landing inside the summer return. Multiplying would give
        // 1.8 x 1.1 = 1.98 and pay for it by starving the rest of the year.
        val calendar = SeasonCalendar(ramadanMonths = setOf(Month.JULY))
        assertEquals(BigDecimal("1.8"), calendar.multiplierFor(Month.JULY))
    }

    @Test
    fun `a moving feast raises an otherwise ordinary month`() {
        val calendar = SeasonCalendar(eidMonths = setOf(Month.MARCH))
        assertEquals(BigDecimal("1.2"), calendar.multiplierFor(Month.MARCH))
    }

    @Test
    fun `the twelve monthly budgets add back up to the annual figure exactly`() {
        // The property that matters: normalising and rounding twelve ways must
        // not lose or invent a single fils.
        val calendar = SeasonCalendar(ramadanMonths = setOf(Month.FEBRUARY), eidMonths = setOf(Month.MARCH))
        val annual = Gs3Budget.totalPaidMedia
        val plan = SeasonalPlan.monthlySpend(annual, calendar)
        assertEquals(12, plan.size)
        assertEquals(annual, plan.values.sum())
    }

    @Test
    fun `it holds for awkward totals too`() {
        val calendar = SeasonCalendar()
        listOf(1L, 7L, 999L, 4_680L, 18_001L).forEach { dinars ->
            val annual = Jod.ofDinars(dinars)
            assertEquals(annual, SeasonalPlan.monthlySpend(annual, calendar).values.sum())
        }
    }

    @Test
    fun `the money follows the audience`() {
        val plan = SeasonalPlan.monthlySpend(Gs3Budget.totalPaidMedia, SeasonCalendar())
        val july = plan.getValue(Month.JULY)
        val february = plan.getValue(Month.FEBRUARY)
        val september = plan.getValue(Month.SEPTEMBER)

        assertTrue(july > february, "July is peak return and must outspend a quiet February")
        assertTrue(september < february, "Gulf school year start is the quietest month")
        // 18,000 x 1.8 / 14.7 = 2,204.08
        assertEquals(Jod.ofFils(2_204_081), july)
    }
}

class StopRulesTest {

    private fun channel(key: String, spend: Long, raw: Int, qualified: Int) =
        ChannelSpend(key, "UAE", Jod.ofDinars(spend), raw, qualified)

    @Test
    fun `cost per lead is null with no leads, not zero`() {
        val empty = channel("meta", 500, 0, 0)
        assertNull(empty.costPerRawLead)
        assertNull(empty.costPerQualifiedLead)
    }

    @Test
    fun `the only target is per qualified lead, and the budget's arithmetic meets it`() {
        // D-3, answered 2026-08-16: the owner removed the 45 JOD figure, so the
        // raw-lead target is gone. Cost per raw lead is still measured — and
        // 7,200 / 160 is 45 to the fils, which is exactly why that number was
        // never a qualified-lead target — but nothing scores against it now.
        val track = channel("external", 7_200, 160, 48)
        assertEquals(Jod.ofDinars(45), track.costPerRawLead)
        assertEquals(Jod.ofDinars(150), track.costPerQualifiedLead)

        val targets = CplTargets()
        assertEquals(track.costPerQualifiedLead, targets.perQualifiedLead)
    }

    @Test
    fun `no raw-lead target survives to be scored against`() {
        // Structural rather than a value assertion. If a `perRawLead` target is
        // ever reintroduced this fails, sending whoever did it back to D-3
        // instead of letting a second, contradictory target reappear quietly.
        val fields = CplTargets::class.java.declaredFields.map { it.name }
        assertFalse(fields.contains("perRawLead"), "a raw-lead target has come back: $fields")
    }

    @Test
    fun `a channel at more than twice the blend is flagged`() {
        val channels = listOf(
            channel("meta", 1_000, 40, 20),      // 50 per qualified
            channel("google", 1_000, 30, 20),    // 50 per qualified
            channel("tiktok", 1_000, 10, 2),     // 500 per qualified
        )
        // 3,000 JOD across 42 qualified leads, held to the fils.
        val blended = StopRules.blendedCostPerQualifiedLead(channels)
        assertEquals(Jod.ofFils(71_429), blended)

        val flags = StopRules.channelsAboveTwiceBlended(channels)
        assertEquals(1, flags.size)
        assertEquals("tiktok", flags.single().channelKey)
        assertEquals(StopRule.CHANNEL_ABOVE_TWICE_BLENDED, flags.single().rule)
    }

    @Test
    fun `a bad month everywhere does not flag every channel`() {
        // All three equally expensive: the rule looks for the outlier, not the weather.
        val channels = listOf(
            channel("meta", 2_000, 10, 4),
            channel("google", 2_000, 10, 4),
            channel("tiktok", 2_000, 10, 4),
        )
        assertTrue(StopRules.channelsAboveTwiceBlended(channels).isEmpty())
    }

    @Test
    fun `an ad set needs two consecutive bad weeks, not one`() {
        val target = Jod.ofDinars(100)
        val oneBadWeek = listOf(Jod.ofDinars(200), Jod.ofDinars(90), Jod.ofDinars(80))
        assertNull(StopRules.adSetOverTarget(oneBadWeek, target))

        val twoInARow = listOf(Jod.ofDinars(90), Jod.ofDinars(160), Jod.ofDinars(200))
        val flag = StopRules.adSetOverTarget(twoInARow, target)
        assertNotNull(flag)
        assertEquals(StopRule.AD_SET_OVER_TARGET_TWO_WEEKS, flag?.rule)
    }

    @Test
    fun `exactly at the threshold is not a breach`() {
        // 50% over a 100 target is 150. At 150 the ad set is not yet flagged.
        val atThreshold = listOf(Jod.ofDinars(150), Jod.ofDinars(150))
        assertNull(StopRules.adSetOverTarget(atThreshold, Jod.ofDinars(100)))
    }

    @Test
    fun `the external track sensitivity decision needs a sustained breach`() {
        val targets = CplTargets()
        val threeWeeks = List(3) { Jod.ofDinars(250) }
        assertNull(StopRules.externalTrackSensitivity(threeWeeks, targets))

        val fourWeeks = List(4) { Jod.ofDinars(250) }
        val flag = StopRules.externalTrackSensitivity(fourWeeks, targets)
        assertNotNull(flag)
        assertEquals(StopRule.EXTERNAL_TRACK_SENSITIVITY_DECISION, flag?.rule)

        // One good week inside the window clears it — the rule is about persistence.
        val withRecovery = listOf(Jod.ofDinars(250), Jod.ofDinars(190), Jod.ofDinars(250), Jod.ofDinars(250))
        assertNull(StopRules.externalTrackSensitivity(withRecovery, targets))
    }

    @Test
    fun `the plan's own numbers do not trip the alarm`() {
        // The point of D-3. On the corrected basis, a track running exactly to
        // plan at 150 per qualified lead sits quietly below the 200 threshold.
        val onPlan = List(8) { Jod.ofDinars(150) }
        assertNull(StopRules.externalTrackSensitivity(onPlan, CplTargets()))

        // Read the brief literally, with a 60 threshold, and the same on-plan
        // track screams from week four onwards and never stops.
        val literalReading = CplTargets(qualifiedStopThreshold = Jod.ofDinars(60))
        assertNotNull(StopRules.externalTrackSensitivity(onPlan, literalReading))
    }

    @Test
    fun `all three sensitivity choices are offered, because doing nothing is not one`() {
        assertEquals(3, SensitivityChoice.entries.size)
    }
}
