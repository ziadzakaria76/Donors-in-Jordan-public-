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
 * The splits are not guesses. The expatriate share follows the geographic
 * distribution of inbound remittances to Jordan, and the non-Jordanian share
 * follows the distribution of non-Jordanian ownership transactions by
 * nationality — which is why Iraq takes half the non-Jordanian budget and
 * Kuwait takes a twentieth of the expatriate one.
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

    val nonJordanianMarkets: List<MarketAllocation> = listOf(
        MarketAllocation(Track.NONJO, "IRQ", Jod.ofDinars(1_260)),
        MarketAllocation(Track.NONJO, "GULF", Jod.ofDinars(560)),
        MarketAllocation(Track.NONJO, "PSE", Jod.ofDinars(420)),
        MarketAllocation(Track.NONJO, "TEST", Jod.ofDinars(280)),
    )

    val externalTrackMarkets: List<MarketAllocation> get() = expatriateMarkets + nonJordanianMarkets

    val expatriateTotal: Jod get() = expatriateMarkets.map { it.annual }.sum()
    val nonJordanianTotal: Jod get() = nonJordanianMarkets.map { it.annual }.sum()
    val externalTrackTotal: Jod get() = expatriateTotal + nonJordanianTotal

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
