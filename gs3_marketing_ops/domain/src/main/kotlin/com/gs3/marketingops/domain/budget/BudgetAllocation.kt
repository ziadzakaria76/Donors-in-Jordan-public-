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
     * adding those up gives 389 JOD a month across the five expatriate markets
     * against a true 390 — a dinar a month, twelve a year, growing with every
     * market added. That is precisely why [monthlyIndicative] is what the app
     * computes with and this is only what it shows.
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
 * buyers. Those four rows are deleted with the track (DECISIONS.md → D-23).
 * [totalPaidMedia] is unchanged at the approved 18,000, so that money is
 * not withdrawn from the plan: all 2,520 of it falls to the local track by the
 * existing arithmetic below, which takes local as whatever the external track
 * does not.
 *
 * The five rows are the brief's original figures, untouched. They were briefly
 * scaled up to 5,805 on 2026-08-29 so the track could fund three units at an
 * assumed 45 JOD per raw lead; the owner removed that assumption on 2026-08-30
 * and the
 * scaling with it. **Nothing here is derived from a cost per lead any more.**
 * These are approved figures, and how many leads they buy is a question
 * the app deliberately does not answer.
 */
object Gs3Budget {

    val totalPaidMedia: Jod = Jod.ofDinars(18_000)

    val expatriateMarkets: List<MarketAllocation> = listOf(
        MarketAllocation(Track.EXPAT, "UAE", Jod.ofDinars(1_370)),
        MarketAllocation(Track.EXPAT, "USA", Jod.ofDinars(1_250)),
        MarketAllocation(Track.EXPAT, "KSA", Jod.ofDinars(1_120)),
        MarketAllocation(Track.EXPAT, "QAT", Jod.ofDinars(600)),
        MarketAllocation(Track.EXPAT, "KWT", Jod.ofDinars(340)),
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
