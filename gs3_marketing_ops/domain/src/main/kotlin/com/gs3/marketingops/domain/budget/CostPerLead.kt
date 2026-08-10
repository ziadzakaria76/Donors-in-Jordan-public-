package com.gs3.marketingops.domain.budget

import com.gs3.marketingops.domain.money.Jod
import com.gs3.marketingops.domain.money.sum
import java.math.BigDecimal

/**
 * Cost-per-lead targets for the external track.
 *
 * On the two numbers here — see DECISIONS.md → D-3. The brief calls 45 JOD the
 * target cost per *qualified* lead, but 45 is exactly 7,200 ÷ 160 raw leads,
 * to the fils. The same budget over the 48 qualified leads it plans for gives
 * 150 JOD. Taken as written the app would judge the track against a target
 * 3.3× harder than its own budget allows, and the stop-rule alarm would come on
 * in the first week and never go off — which trains a team to ignore alarms.
 *
 * So both bases are held here, both are editable in Settings, and the defaults
 * are internally consistent with the plan. Awaiting the owner's confirmation.
 */
data class CplTargets(
    val perRawLead: Jod = Jod.ofDinars(45),
    val perQualifiedLead: Jod = Jod.ofDinars(150),
    /** Sustained cost above this on the external track forces a recorded decision. */
    val qualifiedStopThreshold: Jod = Jod.ofDinars(200),
)

data class ChannelSpend(
    val channelKey: String,
    val marketKey: String,
    val spend: Jod,
    val rawLeads: Int,
    val qualifiedLeads: Int,
) {
    /** Null rather than zero when there are no leads — no leads is not a cost of zero. */
    val costPerRawLead: Jod? get() = if (rawLeads <= 0) null else spend.dividedBy(rawLeads)

    val costPerQualifiedLead: Jod? get() = if (qualifiedLeads <= 0) null else spend.dividedBy(qualifiedLeads)
}

/** What the app recommends, never what it does on its own. */
enum class StopRule {
    /** Cost per qualified lead above twice the blended average for a full month. */
    CHANNEL_ABOVE_TWICE_BLENDED,

    /** An ad set over target by 50% for two consecutive weeks. */
    AD_SET_OVER_TARGET_TWO_WEEKS,

    /** External-track cost persistently above the stop threshold: a decision, not a pause. */
    EXTERNAL_TRACK_SENSITIVITY_DECISION,
}

/**
 * The choices when the external track will not come in on budget. The app makes
 * the manager record which one was taken, rather than letting the track quietly
 * overspend for a year — all three are legitimate, and doing nothing is not.
 */
enum class SensitivityChoice {
    REDUCE_ACTIVE_MARKETS_TO_THREE,
    REDUCE_TRACK_TARGET_TO_TWO_UNITS,
    TOP_UP_BUDGET,
}

data class StopRuleFlag(
    val rule: StopRule,
    val channelKey: String?,
    val observed: Jod,
    val threshold: Jod,
)

object StopRules {

    /** Blended cost per qualified lead across every channel given. */
    fun blendedCostPerQualifiedLead(channels: List<ChannelSpend>): Jod? {
        val qualified = channels.sumOf { it.qualifiedLeads }
        if (qualified <= 0) return null
        return channels.map { it.spend }.sum().dividedBy(qualified)
    }

    /**
     * A channel running at more than twice the blended average for a full month.
     * Judged against the blend rather than a fixed number so that a bad month
     * everywhere does not flag every channel at once — the rule is looking for
     * the outlier, not the weather.
     */
    fun channelsAboveTwiceBlended(channels: List<ChannelSpend>): List<StopRuleFlag> {
        val blended = blendedCostPerQualifiedLead(channels) ?: return emptyList()
        val threshold = blended * 2
        return channels.mapNotNull { channel ->
            val cost = channel.costPerQualifiedLead
            if (cost != null && cost > threshold) {
                StopRuleFlag(StopRule.CHANNEL_ABOVE_TWICE_BLENDED, channel.channelKey, cost, threshold)
            } else null
        }
    }

    /** An ad set over its target by 50% in each of two consecutive weeks. */
    fun adSetOverTarget(
        weeklyCost: List<Jod>,
        target: Jod,
        overBy: BigDecimal = BigDecimal("1.5"),
    ): StopRuleFlag? {
        val threshold = target.scaledBy(overBy)
        val breach = weeklyCost.windowed(2).any { pair -> pair.all { it > threshold } }
        if (!breach) return null
        return StopRuleFlag(
            rule = StopRule.AD_SET_OVER_TARGET_TWO_WEEKS,
            channelKey = null,
            observed = weeklyCost.maxOrNull() ?: Jod.ZERO,
            threshold = threshold,
        )
    }

    /**
     * The external track sitting above the stop threshold for [sustainedWeeks]
     * or more. This one does not recommend a pause — pausing the external track
     * abandons three of the eleven units. It forces an explicit, recorded choice.
     */
    fun externalTrackSensitivity(
        weeklyCostPerQualifiedLead: List<Jod>,
        targets: CplTargets = CplTargets(),
        sustainedWeeks: Int = 4,
    ): StopRuleFlag? {
        if (weeklyCostPerQualifiedLead.size < sustainedWeeks) return null
        val recent = weeklyCostPerQualifiedLead.takeLast(sustainedWeeks)
        if (recent.any { it <= targets.qualifiedStopThreshold }) return null
        return StopRuleFlag(
            rule = StopRule.EXTERNAL_TRACK_SENSITIVITY_DECISION,
            channelKey = null,
            observed = recent.min(),
            threshold = targets.qualifiedStopThreshold,
        )
    }
}
