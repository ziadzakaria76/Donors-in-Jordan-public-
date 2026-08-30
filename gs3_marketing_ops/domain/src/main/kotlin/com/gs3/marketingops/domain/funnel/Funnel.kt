package com.gs3.marketingops.domain.funnel

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * The two tracks the strategy runs, which convert at genuinely different rates.
 *
 * There was a third, `NONJO`, for non-Jordanian buyers. It is gone from v1 —
 * see DECISIONS.md → D-23. Nothing here is waiting to be switched back on: the
 * track and everything it carried were deleted, not disabled, and adding it
 * back is a deliberate piece of work rather than flipping a flag.
 */
enum class Track {
    /** Buyers already in Jordan. */
    LOCAL,

    /** Jordanian expatriates abroad. */
    EXPAT,
    ;

    /**
     * External-track leads decide over 90–150 days against 60–75 for a local
     * buyer, so they must not be judged stale on the local clock. Marking an
     * expatriate lead dead at thirty days is how a live buyer gets dropped.
     */
    val isExternal: Boolean get() = this != LOCAL
}

/** A funnel expressed as the rates between its stages. */
data class FunnelModel(
    val rawLeads: Int,
    val qualifiedRate: BigDecimal,
    val viewingRate: BigDecimal,
    val offerRate: BigDecimal,
    val contractRate: BigDecimal,
) {
    /**
     * Each stage is computed from the *rounded* stage before it, not from an
     * unrounded chain. That is how the strategy's own numbers were derived —
     * 315 qualified gives 94.5 viewings, which the plan calls 95, and 95 is
     * what the offer count is then taken from. Carrying the fraction through
     * instead would give 52 offers from 94.5 and quietly disagree with the
     * document the team is working to.
     */
    fun project(): FunnelProjection {
        val qualified = scale(rawLeads, qualifiedRate)
        val viewings = scale(qualified, viewingRate)
        val offers = scale(viewings, offerRate)
        val contracts = scale(offers, contractRate)
        return FunnelProjection(rawLeads, qualified, viewings, offers, contracts)
    }

    private fun scale(from: Int, rate: BigDecimal): Int =
        BigDecimal.valueOf(from.toLong()).multiply(rate).setScale(0, RoundingMode.HALF_UP).toInt()

    companion object {
        /** The whole project: 900 raw leads to 11 contracts. */
        val OVERALL = FunnelModel(
            rawLeads = 900,
            qualifiedRate = BigDecimal("0.35"),
            viewingRate = BigDecimal("0.30"),
            offerRate = BigDecimal("0.55"),
            contractRate = BigDecimal("0.21"),
        )

        /**
         * The external track: fewer leads, harder to qualify, but a live tour
         * converts far better because someone who books one from Dubai is
         * further through the decision than a local walk-in.
         *
         * **All five numbers are the strategy's own, and none is derived from
         * the budget.** A 2026-08-29 decision briefly made the lead count
         * follow the money, at an assumed 45 JOD per raw lead; the owner removed
         * that assumption on
         * 2026-08-30, so 160 is once more simply what the plan says the
         * external track brings in.
         *
         * **What that leaves open, deliberately.** The 160 was modelled when
         * the external track meant expatriates *and* non-Jordanians. That track
         * is gone (D-23) and its budget is 4,680 rather than 7,200, so
         * expatriate marketing alone now has to supply all 160 on two thirds of
         * the money. Whether it can is not answered here and is not answerable
         * without a cost per lead, which is precisely the figure that was
         * removed. It is a question for the first month of real spend —
         * `ChannelSpend.costPerRawLead` measures it — not for an assumption.
         */
        val EXTERNAL = FunnelModel(
            rawLeads = 160,
            qualifiedRate = BigDecimal("0.30"),
            viewingRate = BigDecimal("0.35"),
            offerRate = BigDecimal.ONE, // the external track goes from live tour to contract
            contractRate = BigDecimal("0.18"),
        )
    }
}

data class FunnelProjection(
    val rawLeads: Int,
    val qualified: Int,
    val viewings: Int,
    val offers: Int,
    val contracts: Int,
)

/** Where a stage stands against its target — the dashboard's colour state. */
enum class TargetState { ON_TARGET, BEHIND, AT_RISK }

object FunnelTargets {
    /** Within 10% of target is on target; below 70% is at risk. */
    private val onTarget = BigDecimal("0.90")
    private val atRisk = BigDecimal("0.70")

    fun stateOf(actual: Int, target: Int): TargetState {
        if (target <= 0) return TargetState.ON_TARGET
        val ratio = BigDecimal.valueOf(actual.toLong())
            .divide(BigDecimal.valueOf(target.toLong()), 4, RoundingMode.HALF_UP)
        return when {
            ratio >= onTarget -> TargetState.ON_TARGET
            ratio >= atRisk -> TargetState.BEHIND
            else -> TargetState.AT_RISK
        }
    }
}
