package com.gs3.marketingops.domain.report

import com.gs3.marketingops.domain.content.AssetChecklist
import com.gs3.marketingops.domain.content.AssetKind
import com.gs3.marketingops.domain.content.AssetStatus
import com.gs3.marketingops.domain.content.ContentPillar
import com.gs3.marketingops.domain.content.PillarMix
import com.gs3.marketingops.domain.content.WeeklyCadence
import com.gs3.marketingops.domain.lead.LeadSource
import com.gs3.marketingops.domain.lead.LeadStage
import com.gs3.marketingops.domain.lead.LossReason
import com.gs3.marketingops.domain.lead.NationalityCategory
import com.gs3.marketingops.domain.lead.lead
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.math.BigDecimal

class ReportsTest {

    @Test
    fun `SLA compliance is a percentage of deadlines met`() {
        assertEquals(BigDecimal("80.0"), Reports.slaCompliance(8, 10))
        assertEquals(BigDecimal("100.0"), Reports.slaCompliance(10, 10))
        assertEquals(BigDecimal("0.0"), Reports.slaCompliance(0, 7))
    }

    @Test
    fun `a week with no deadlines is a hundred per cent, not zero`() {
        // Reporting a quiet week as 0% compliance makes the metric useless on
        // exactly the weeks the team needs to read honestly.
        assertEquals(BigDecimal("100.0"), Reports.slaCompliance(0, 0))
    }

    @Test
    fun `impossible compliance figures are rejected`() {
        assertTrue(runCatching { Reports.slaCompliance(5, 3) }.exceptionOrNull() is IllegalArgumentException)
        assertTrue(runCatching { Reports.slaCompliance(-1, 3) }.exceptionOrNull() is IllegalArgumentException)
    }

    @Test
    fun `the sales mix measures both targets`() {
        val leads = listOf(
            lead("1", LeadStage.CONTRACTED, NationalityCategory.JORDANIAN_EXPATRIATE),
            lead("2", LeadStage.CONTRACTED, NationalityCategory.JORDANIAN_EXPATRIATE),
            lead("3", LeadStage.CONTRACTED, NationalityCategory.JORDANIAN_RESIDENT, LeadSource.REFERRAL),
            lead("4", LeadStage.CONTRACTED, NationalityCategory.JORDANIAN_RESIDENT, LeadSource.REFERRAL),
            lead("5", LeadStage.CONTRACTED, NationalityCategory.JORDANIAN_RESIDENT),
            lead("6", LeadStage.QUALIFIED),
        )
        val mix = Reports.salesMix(leads)
        assertEquals(5, mix.totalContracted)
        assertEquals(2, mix.externalTrackContracted)
        assertEquals(2, mix.referralContracted)
        assertEquals(BigDecimal("0.4000"), mix.externalShare)
        assertTrue(mix.meetsExternalTarget)
        assertTrue(mix.meetsReferralTarget)
    }

    @Test
    fun `the plan's own three-of-eleven clears the external target`() {
        val contracted = (1..11).map { index ->
            lead(
                "$index",
                LeadStage.CONTRACTED,
                if (index <= 3) NationalityCategory.JORDANIAN_EXPATRIATE
                else NationalityCategory.JORDANIAN_RESIDENT,
            )
        }
        val mix = Reports.salesMix(contracted)
        assertEquals(BigDecimal("0.2727"), mix.externalShare)
        assertTrue(mix.meetsExternalTarget, "3 of 11 is 27.3%, which clears the 27% commitment")
    }

    @Test
    fun `no sales yet is a zero share, not a division by zero`() {
        val mix = Reports.salesMix(listOf(lead("1", LeadStage.QUALIFIED)))
        assertEquals(BigDecimal.ZERO, mix.externalShare)
        assertFalse(mix.meetsExternalTarget)
    }

    @Test
    fun `funnel counts are cumulative reach, not current occupancy`() {
        // A lead standing at Negotiation has passed through Qualified and
        // Viewing. Counting only where each lead stands right now would report
        // a conversion of zero on a pipeline that is working perfectly.
        val leads = listOf(
            lead("1", LeadStage.NEGOTIATION),
            lead("2", LeadStage.QUALIFIED),
            lead("3", LeadStage.NEW_ENQUIRY),
        )
        val report = Reports.funnel(leads)
        assertEquals(3, report.stageCounts[LeadStage.NEW_ENQUIRY])
        assertEquals(2, report.stageCounts[LeadStage.QUALIFIED])
        assertEquals(1, report.stageCounts[LeadStage.NEGOTIATION])
        assertEquals(0, report.stageCounts[LeadStage.CONTRACTED])
    }

    @Test
    fun `a lost lead still counts toward the stages it actually reached`() {
        // Otherwise losing a buyer retroactively improves the viewing rate,
        // which is exactly backwards.
        val leads = listOf(
            lead("1", LeadStage.LOST, lossReason = LossReason.PRICE),
            lead("2", LeadStage.VIEWING_DONE),
        )
        val report = Reports.funnel(leads, furthestStageReached = mapOf("1" to LeadStage.VIEWING_DONE))
        assertEquals(2, report.stageCounts[LeadStage.VIEWING_DONE])
        assertEquals(1, report.stageCounts[LeadStage.LOST])
    }

    @Test
    fun `conversions are computed between consecutive stages`() {
        val leads = listOf(
            lead("1", LeadStage.QUALIFIED),
            lead("2", LeadStage.QUALIFIED),
            lead("3", LeadStage.NEW_ENQUIRY),
            lead("4", LeadStage.NEW_ENQUIRY),
        )
        val report = Reports.funnel(leads)
        val firstStep = report.conversions.first()
        assertEquals(LeadStage.NEW_ENQUIRY, firstStep.from)
        assertEquals(LeadStage.QUALIFIED, firstStep.to)
        assertEquals(BigDecimal("0.5000"), firstStep.rate)
    }

    @Test
    fun `loss reasons and sources are broken out for the reports hub`() {
        val leads = listOf(
            lead("1", LeadStage.LOST, lossReason = LossReason.PRICE),
            lead("2", LeadStage.LOST, lossReason = LossReason.PRICE),
            lead("3", LeadStage.QUALIFIED, source = LeadSource.REFERRAL),
        )
        assertEquals(LossReason.PRICE to 2, Reports.lossReasons(leads).first())
        assertEquals(1, Reports.bySource(leads)[LeadSource.REFERRAL])
        assertEquals(3, Reports.byTrack(leads).values.sum())
    }
}

class ContentPlanTest {

    @Test
    fun `the four pillars sum to one`() {
        val total = ContentPillar.entries.fold(BigDecimal.ZERO) { sum, p -> sum + p.targetShare }
        assertEquals(BigDecimal("1.00"), total)
    }

    @Test
    fun `an all-product month is flagged as off target`() {
        // The natural drift of a developer's feed, and it stops working within
        // a month.
        val balance = PillarMix.balance(mapOf(ContentPillar.PRODUCT to 10))
        val product = balance.first { it.pillar == ContentPillar.PRODUCT }
        assertEquals(BigDecimal("1.0000"), product.actualShare)
        assertTrue(product.isOffTarget)
        assertTrue(balance.filter { it.pillar != ContentPillar.PRODUCT }.all { it.isOffTarget })
    }

    @Test
    fun `an empty month reads as zero, not as balanced`() {
        val balance = PillarMix.balance(emptyMap())
        assertTrue(balance.all { it.actualShare == BigDecimal.ZERO })
    }

    @Test
    fun `a balanced month passes`() {
        val balance = PillarMix.balance(
            mapOf(
                ContentPillar.PRODUCT to 8,
                ContentPillar.TRUST to 5,
                ContentPillar.EDUCATION to 4,
                ContentPillar.PLACE to 3,
            )
        )
        assertTrue(balance.none { it.isOffTarget }, balance.toString())
    }

    @Test
    fun `the app names the pillar to write next`() {
        val published = mapOf(ContentPillar.PRODUCT to 10, ContentPillar.TRUST to 5)
        assertEquals(ContentPillar.EDUCATION, PillarMix.mostUnderRepresented(published))
    }

    @Test
    fun `the weekly cadence is nine scheduled items plus a daily story`() {
        assertEquals(9, WeeklyCadence.scheduledItemsPerWeek)
        assertEquals(1, WeeklyCadence.STORIES_PER_DAY)
    }

    @Test
    fun `the asset checklist starts empty and reports real progress`() {
        val initial = AssetChecklist.initial()
        assertEquals(AssetKind.entries.size, initial.size)
        assertEquals(BigDecimal("0.0"), AssetChecklist.completionPercent(initial))

        val halfDone = initial.mapIndexed { index, item ->
            if (index < 5) item.copy(status = AssetStatus.DELIVERED) else item
        }
        assertEquals(BigDecimal("50.0"), AssetChecklist.completionPercent(halfDone))
    }
}
