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
         * **The four rates are untouched; only the lead volume follows the
         * budget.** 160 raw leads was what 7,200 JOD bought at the plan's own
         * 45 JOD each, when the external track meant expatriates *and*
         * non-Jordanians. That track is gone (D-23) and its budget is now
         * 5,805, which buys 129 — and 129 still yields three contracts, which
         * is why 5,805 is the figure D-28 settled on rather than any rounder
         * number. Drop below 129 and the third unit goes with it.
         *
         * Nothing here is a re-estimate. The qualification, viewing and
         * contract rates are the strategy's, unchanged; re-deriving them for an
         * expatriate-only audience would be invention, and is deliberately not
         * done. What is assumed is that an expatriate raw lead still costs
         * about 45 JOD — a *blended* figure that included cheaper
         * non-Jordanian markets, so it may prove optimistic. See D-28.
         */
        val EXTERNAL = FunnelModel(
            rawLeads = 129,
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
