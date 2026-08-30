package com.gs3.marketingops.domain.budget

import com.gs3.marketingops.domain.money.Jod
import com.gs3.marketingops.domain.money.sum
import java.math.BigDecimal

/**
 * Cost-per-lead targets for the external track.
 *
 * **There is one target, and it is per qualified lead.** D-3 is answered
 * (2026-08-16): the owner removed the 45 JOD figure, so the raw-lead target is
 * gone rather than reinterpreted.
 *
 * That left the track judged on the basis its own budget planned for — when the
 * external track was 7,200 JOD, its 48 expected qualified leads came to 150
 * each, with a recorded decision forced above 200. Carrying a second target on
 * a different basis would have meant two numbers that can disagree about
 * whether the same month went well.
 *
 * **150 no longer comes out of the budget's arithmetic, and is kept anyway.**
 * Removing the non-Jordanian track (D-23) took the external budget to 4,680, so
 * the same division over the same 48 qualified leads gives 97.500. The target
 * stays at 150 — see DECISIONS.md → D-26 and D-29. It is an approved figure and
 * moving it down would tighten an alarm on a funnel nobody has re-estimated,
 * which is the D-3 failure again: an alarm that fires from week one and teaches
 * the team to ignore it. Loose is the safe direction for an unconfirmed
 * threshold.
 *
 * **No cost per raw lead is assumed anywhere.** The owner removed that figure
 * on 2026-08-30 (D-29), so nothing in this app converts a budget into a lead
 * count or a lead count into a budget. The external track's 4,680 JOD and the
 * external funnel's 160 raw leads are both approved figures that stand on their
 * own; whether the first can buy the second is an open question, and the app no
 * longer answers it by assumption.
 *
 * Cost per raw lead is still *measured* — see [ChannelSpend.costPerRawLead].
 * What does not exist is a target to score it against, or a planning figure to
 * derive anything from.
 *
 * Both remaining figures are editable in Settings.
 */
data class CplTargets(
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
