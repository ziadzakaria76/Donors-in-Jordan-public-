package com.gs3.marketingops.domain.report

import com.gs3.marketingops.domain.funnel.Track
import com.gs3.marketingops.domain.inventory.Gs3Schedule
import com.gs3.marketingops.domain.lead.Lead
import com.gs3.marketingops.domain.lead.LeadSource
import com.gs3.marketingops.domain.lead.LeadStage
import com.gs3.marketingops.domain.lead.LossReason
import com.gs3.marketingops.domain.lead.Pipeline
import java.math.BigDecimal
import java.math.RoundingMode

data class ConversionRate(val from: LeadStage, val to: LeadStage, val rate: BigDecimal)

data class FunnelReport(
    val stageCounts: Map<LeadStage, Int>,
    val conversions: List<ConversionRate>,
)

data class SalesMixReport(
    val totalContracted: Int,
    val externalTrackContracted: Int,
    val referralContracted: Int,
) {
    val externalShare: BigDecimal get() = share(externalTrackContracted)
    val referralShare: BigDecimal get() = share(referralContracted)

    /** Target ≥ 27% of sales from the external track. */
    val meetsExternalTarget: Boolean get() = externalShare >= Gs3Schedule.externalTrackShareTarget

    /** Target ≥ 20% from referrals. */
    val meetsReferralTarget: Boolean get() = referralShare >= Gs3Schedule.referralShareTarget

    private fun share(count: Int): BigDecimal =
        if (totalContracted == 0) BigDecimal.ZERO
        else BigDecimal.valueOf(count.toLong())
            .divide(BigDecimal.valueOf(totalContracted.toLong()), 4, RoundingMode.HALF_UP)
}

object Reports {

    /**
     * Stage counts plus the conversion between each consecutive pair.
     *
     * Counts are *cumulative reach*, not current occupancy: a lead sitting at
     * Negotiation has passed through Qualified and Viewing, and counting only
     * where each lead is standing right now would show a conversion of zero on
     * a pipeline that is working perfectly. Lost leads count toward every stage
     * they genuinely reached before they were lost — otherwise losing a buyer
     * retroactively improves the viewing rate, which is exactly backwards.
     */
    fun funnel(leads: List<Lead>, furthestStageReached: Map<String, LeadStage> = emptyMap()): FunnelReport {
        // Resolve every lead to the furthest selling stage it actually reached.
        // A lost lead whose history was not recorded still got as far as being
        // an enquiry, so it counts there rather than nowhere.
        val reached = leads.associate { lead ->
            val resolved = furthestStageReached[lead.id] ?: lead.stage
            lead.id to if (resolved == LeadStage.LOST) LeadStage.NEW_ENQUIRY else resolved
        }

        val counts = Pipeline.sellingStages.associateWith { stage ->
            reached.values.count { it.order >= stage.order }
        }

        val conversions = Pipeline.sellingStages.zipWithNext { from, to ->
            val fromCount = counts[from] ?: 0
            val toCount = counts[to] ?: 0
            val rate = if (fromCount == 0) BigDecimal.ZERO else
                BigDecimal.valueOf(toCount.toLong())
                    .divide(BigDecimal.valueOf(fromCount.toLong()), 4, RoundingMode.HALF_UP)
            ConversionRate(from, to, rate)
        }

        return FunnelReport(counts + mapOf(LeadStage.LOST to leads.count { it.stage == LeadStage.LOST }), conversions)
    }

    /**
     * SLA compliance as a percentage of deadlines met.
     *
     * With no deadlines in the period this returns 100%, not zero: a week with
     * no enquiries is not a week of failure, and reporting it as 0% compliance
     * would make the metric useless on exactly the quiet weeks the team needs
     * to read honestly.
     */
    fun slaCompliance(deadlinesMet: Int, deadlinesTotal: Int): BigDecimal {
        require(deadlinesMet >= 0 && deadlinesTotal >= 0) { "Counts cannot be negative" }
        require(deadlinesMet <= deadlinesTotal) { "Met ($deadlinesMet) cannot exceed total ($deadlinesTotal)" }
        if (deadlinesTotal == 0) return BigDecimal("100.0")
        return BigDecimal.valueOf(deadlinesMet.toLong())
            .divide(BigDecimal.valueOf(deadlinesTotal.toLong()), 4, RoundingMode.HALF_UP)
            .movePointRight(2)
            .setScale(1, RoundingMode.HALF_UP)
    }

    fun lossReasons(leads: List<Lead>): List<Pair<LossReason, Int>> = Pipeline.lossReasonsRanked(leads)

    fun salesMix(leads: List<Lead>): SalesMixReport {
        val contracted = leads.filter { it.stage == LeadStage.CONTRACTED }
        return SalesMixReport(
            totalContracted = contracted.size,
            externalTrackContracted = contracted.count { it.track.isExternal },
            referralContracted = contracted.count { it.source == LeadSource.REFERRAL },
        )
    }

    /** Leads by source, for judging where the money should go next. */
    fun bySource(leads: List<Lead>): Map<LeadSource, Int> =
        leads.groupingBy { it.source }.eachCount()

    fun byTrack(leads: List<Lead>): Map<Track, Int> =
        leads.groupingBy { it.track }.eachCount()
}
