package com.gs3.marketingops.domain.budget

import com.gs3.marketingops.domain.funnel.FunnelModel
import com.gs3.marketingops.domain.funnel.Track
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
    fun `market rows sum exactly to the external track total`() {
        // 5,805. The four non-Jordanian rows (IRQ 1,260, GULF 560, PSE 420,
        // TEST 280) are deleted with the track — D-23 — and 1,125 of the 2,520
        // they held stays on this track so it can still fund three units.
        // D-28.
        assertEquals(Jod.ofDinars(5_805), Gs3Budget.expatriateTotal)
        assertEquals(Jod.ofDinars(5_805), Gs3Budget.externalTrackTotal)
        assertEquals(5, Gs3Budget.externalTrackMarkets.size)
    }

    @Test
    fun `the external track takes thirty-two and a quarter per cent of paid media, all of it expatriate`() {
        // Was 40%, split 65 expatriate / 35 non-Jordanian. Both of those
        // numbers described a track that no longer exists, and the honest
        // replacement is not a re-split — it is that there is nothing left to
        // split. Total paid media is deliberately unchanged at the approved
        // 18,000, so the share moves rather than the budget.
        assertEquals(BigDecimal("0.322500"), Gs3Budget.externalTrackTotal.ratioOf(Gs3Budget.totalPaidMedia))
        assertEquals(BigDecimal("1.000000"), Gs3Budget.expatriateTotal.ratioOf(Gs3Budget.externalTrackTotal))
        assertTrue(Gs3Budget.externalTrackMarkets.all { it.track == Track.EXPAT })
    }

    @Test
    fun `local media is whatever the external track does not take`() {
        // 12,195, up from 10,800 by the 1,395 left over once the external
        // track has taken the 1,125 it needs. Same subtraction as always;
        // nothing was re-derived to make this number.
        assertEquals(Jod.ofDinars(12_195), Gs3Budget.localTrackTotal)
        assertEquals(Gs3Budget.totalPaidMedia, Gs3Budget.localTrackTotal + Gs3Budget.externalTrackTotal)
    }

    @Test
    fun `rescaling the track left every market's share of it where it was`() {
        // D-28 scaled the five rows by 5,805/4,680 and rounded to the nearest
        // 5 JOD. The property that matters is not the individual figures but
        // that the weighting did not drift: the split follows the geographic
        // distribution of remittances, and a rounding that quietly moved money
        // from Kuwait to the Emirates would be a strategy change disguised as
        // arithmetic. No market moves by more than a tenth of a point.
        val before = mapOf("UAE" to 1_370, "USA" to 1_250, "KSA" to 1_120, "QAT" to 600, "KWT" to 340)
        val beforeTotal = before.values.sum().toBigDecimal()

        Gs3Budget.expatriateMarkets.forEach { market ->
            val was = before.getValue(market.marketKey).toBigDecimal()
                .divide(beforeTotal, 6, java.math.RoundingMode.HALF_UP)
            val now = market.annual.ratioOf(Gs3Budget.externalTrackTotal)
            assertTrue(
                (was - now).abs() < BigDecimal("0.001"),
                "${market.marketKey} share moved from $was to $now",
            )
        }
    }

    @Test
    fun `the displayed monthly figures are the annual rows over twelve`() {
        val monthly = Gs3Budget.externalTrackMarkets.associate { it.marketKey to it.monthlyDisplayDinars }
        assertEquals(142L, monthly.getValue("UAE"))
        assertEquals(129L, monthly.getValue("USA"))
        assertEquals(116L, monthly.getValue("KSA"))
        assertEquals(62L, monthly.getValue("QAT"))
        assertEquals(35L, monthly.getValue("KWT"))
        // IRQ 105, GULF 47, PSE 35 and TEST 23 were here. Their rows are gone.
        assertEquals(setOf("UAE", "USA", "KSA", "QAT", "KWT"), monthly.keys)
    }

    @Test
    fun `the displayed monthly figures do not re-sum, which is why they are never added up`() {
        // DECISIONS.md D-4, made executable. Rounded to whole dinars the way
        // the strategy document prints them, the five expatriate markets total
        // 484 JOD a month against a true 483.75.
        //
        // Note the direction. On the pre-D-28 figures these same five rounded
        // *down*, to 389 against a true 390, and the D-4 note was written
        // around a shortfall. It is an overshoot now. Which way it lands is an
        // accident of five roundings, and that is the whole argument for never
        // adding this column up rather than for correcting it by a dinar.
        val displayedSum = Gs3Budget.expatriateMarkets.sumOf { it.monthlyDisplayDinars }
        assertEquals(484L, displayedSum)
        assertEquals(Jod.ofFils(483_750), Gs3Budget.expatriateTotal.dividedBy(12))
        assertTrue(Jod.ofDinars(484) > Gs3Budget.expatriateTotal.dividedBy(12))
    }

    @Test
    fun `the exact monthly figures do re-sum, which is what the app computes with`() {
        // Held to the fils, the same five markets add straight back up to the
        // annual figure. This is the reason the app never stores the rounding.
        val exactSum = Gs3Budget.expatriateMarkets.map { it.monthlyIndicative }.sum()
        assertEquals(Gs3Budget.expatriateTotal.dividedBy(12), exactSum)
        assertEquals(Jod.ofFils(483_750), exactSum)
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
    fun `the only target is per qualified lead, and the budget's arithmetic still meets it`() {
        // D-3, answered 2026-08-16: the owner removed the 45 JOD figure, so the
        // raw-lead target is gone. Cost per raw lead is still measured; nothing
        // scores against it — and it is still exactly 45 to the fils, which was
        // always the reason 45 could not have been a qualified-lead target.
        //
        // D-26 and D-28. Removing the non-Jordanian track briefly broke the
        // agreement between the target and the budget: at 4,680 the same
        // division gave 97.500 against a target of 150. Sizing the track at
        // 5,805 so it can still fund three units brings it back to 148.846,
        // and the 150 did not have to move.
        val plannedExternalSpend = Gs3Budget.externalTrackTotal
        assertEquals(Jod.ofDinars(5_805), plannedExternalSpend)

        val planned = FunnelModel.EXTERNAL.project()
        val onPlan = ChannelSpend(
            "external", "UAE", plannedExternalSpend,
            rawLeads = planned.rawLeads,
            qualifiedLeads = planned.qualified,
        )

        // The budget and the funnel are wired to each other here rather than
        // being two hardcoded numbers that can drift apart silently. 45 JOD a
        // raw lead is the assumption both rest on.
        assertEquals(Jod.ofDinars(45), onPlan.costPerRawLead)
        assertEquals(Jod.ofFils(148_846), onPlan.costPerQualifiedLead)

        val targets = CplTargets()
        assertEquals(Jod.ofDinars(150), targets.perQualifiedLead)
        assertTrue(
            onPlan.costPerQualifiedLead!! < targets.perQualifiedLead,
            "the target must stay at or above what the plan spends, never below — see D-3 and D-26",
        )
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
