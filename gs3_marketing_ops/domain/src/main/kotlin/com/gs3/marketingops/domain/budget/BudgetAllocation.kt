package com.gs3.marketingops.domain.budget

import com.gs3.marketingops.domain.funnel.Track
import com.gs3.marketingops.domain.money.Jod
import com.gs3.marketingops.domain.money.sum
import java.math.BigDecimal

/** A market the external track buys media in. */
data class MarketAllocation(
    val track: Track,
    val marketKey: String,
    val annual: Jod,
) {
    /**
     * Derived, never stored — see DECISIONS.md → D-4. Exact to the fils, so the
     * twelve months of a market add back up to its annual figure.
     */
    val monthlyIndicative: Jod get() = annual.dividedBy(12)

    /**
     * The same figure as the strategy document prints it: whole dinars.
     *
     * Display only, and never summed. Rounding each market to the dinar and
     * adding those up gives 484 JOD a month across the five expatriate markets
     * against a true 483.75 — and the direction is not fixed either: on the
     * previous figures the same five rounded *down* to 389 against a true 390.
     * Either way the displayed column does not re-sum, which is precisely why
     * [monthlyIndicative] is what the app computes with and this is only what
     * it shows.
     */
    val monthlyDisplayDinars: Long
        get() = monthlyIndicative.dinars.setScale(0, java.math.RoundingMode.HALF_UP).toLong()
}

/**
 * The approved annual media allocation.
 *
 * The split is not a guess. The expatriate share follows the geographic
 * distribution of inbound remittances to Jordan, which is why the Emirates take
 * roughly four times what Kuwait does.
 *
 * **The external track is expatriates, and nothing else.** It used to carry a
 * second half — 2,520 JOD across IRQ, GULF, PSE and TEST — for non-Jordanian
 * buyers. Those four rows are deleted with the track (DECISIONS.md → D-23,
 * D-24). [totalPaidMedia] is unchanged at the approved 18,000, so that money is
 * not withdrawn from the plan; where it lands is D-28.
 *
 * **Of the 2,520, 1,125 stays on this track and 1,395 falls to local.** The
 * external track keeps a three-unit target and a ≥27% share of sales, and at
 * the plan's own 45 JOD per raw external lead those need 129 raw leads —
 * 5,805 JOD. Left at 4,680 the same funnel yields two units, not three, and
 * the dashboard would have reported the track at risk from its first month
 * while it performed exactly to budget. The five rows below are the original
 * remittance weighting scaled to 5,805 and rounded to the nearest 5 JOD; no
 * market's share of the track moves by more than 0.03 of a percentage point.
 * See DECISIONS.md → D-28, including why 1,125 is a floor rather than an
 * estimate.
 */
object Gs3Budget {

    val totalPaidMedia: Jod = Jod.ofDinars(18_000)

    val expatriateMarkets: List<MarketAllocation> = listOf(
        MarketAllocation(Track.EXPAT, "UAE", Jod.ofDinars(1_700)),
        MarketAllocation(Track.EXPAT, "USA", Jod.ofDinars(1_550)),
        MarketAllocation(Track.EXPAT, "KSA", Jod.ofDinars(1_390)),
        MarketAllocation(Track.EXPAT, "QAT", Jod.ofDinars(745)),
        MarketAllocation(Track.EXPAT, "KWT", Jod.ofDinars(420)),
    )

    /**
     * Kept as its own name even though it is now exactly [expatriateMarkets].
     * The two are the same list today and are not the same idea: "the markets
     * the external track buys media in" is what the seed and the reports mean,
     * and collapsing it would hide where a second external market would go.
     */
    val externalTrackMarkets: List<MarketAllocation> get() = expatriateMarkets

    val expatriateTotal: Jod get() = expatriateMarkets.map { it.annual }.sum()
    val externalTrackTotal: Jod get() = expatriateTotal

    /** Whatever is not committed to the external track — Meta, portals, Google, Snapchat, TikTok. */
    val localTrackTotal: Jod get() = totalPaidMedia - externalTrackTotal

    /**
     * The first four weeks of paid spend must stay under 15% of the annual
     * budget. Testing is meant to be cheap; a test that eats a fifth of the
     * year in a month is not a test, it is the campaign.
     */
    val TEST_BUDGET_SHARE: BigDecimal = BigDecimal("0.15")

    val testBudgetCeiling: Jod get() = totalPaidMedia.scaledBy(TEST_BUDGET_SHARE)

    fun isTestBudgetExceeded(firstFourWeeksSpend: Jod): Boolean = firstFourWeeksSpend > testBudgetCeiling
}
