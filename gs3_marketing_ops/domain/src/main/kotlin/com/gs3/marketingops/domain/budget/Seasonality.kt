package com.gs3.marketingops.domain.budget

import com.gs3.marketingops.domain.money.Jod
import java.math.BigDecimal
import java.time.Month

/**
 * When the money should be spent.
 *
 * Expatriates come home in July and August, research the market in May and
 * June, and have cash at year end. Gulf families disappear in September when
 * school restarts. The multipliers redistribute the same annual budget toward
 * the months when the audience is actually reachable.
 */
enum class Season(val multiplier: BigDecimal) {
    PEAK_SUMMER_RETURN(BigDecimal("1.8")),
    PRE_SUMMER_RESEARCH(BigDecimal("1.4")),
    RAMADAN(BigDecimal("1.1")),
    EID(BigDecimal("1.2")),
    YEAR_END_BONUSES(BigDecimal("1.3")),
    GULF_SCHOOL_YEAR_START(BigDecimal("0.7")),
}

/**
 * Which months each season falls in for a given year.
 *
 * Ramadan and the two Eids move about eleven days earlier every Gregorian year,
 * so they are supplied per year and never hardcoded — a table baked in today
 * would be a month wrong within three years and silently misplace the budget.
 */
data class SeasonCalendar(
    val ramadanMonths: Set<Month> = emptySet(),
    val eidMonths: Set<Month> = emptySet(),
) {
    private val fixed: Map<Month, Season> = mapOf(
        Month.JULY to Season.PEAK_SUMMER_RETURN,
        Month.AUGUST to Season.PEAK_SUMMER_RETURN,
        Month.MAY to Season.PRE_SUMMER_RESEARCH,
        Month.JUNE to Season.PRE_SUMMER_RESEARCH,
        Month.DECEMBER to Season.YEAR_END_BONUSES,
        Month.JANUARY to Season.YEAR_END_BONUSES,
        Month.SEPTEMBER to Season.GULF_SCHOOL_YEAR_START,
    )

    fun seasonsIn(month: Month): Set<Season> = buildSet {
        fixed[month]?.let { add(it) }
        if (month in ramadanMonths) add(Season.RAMADAN)
        if (month in eidMonths) add(Season.EID)
    }

    /**
     * Where seasons overlap — an Eid landing inside the summer return, say —
     * the multipliers compose by taking the **larger, not the product**.
     *
     * Multiplying would let one month claim 1.8 × 1.2 = 2.16 and, because the
     * annual total is fixed, pay for it by starving every other month. Taking
     * the maximum keeps the strongest signal for that month without letting a
     * coincidence of the lunar calendar rewrite the whole year's plan.
     * A month in no season takes 1.0.
     */
    fun multiplierFor(month: Month): BigDecimal =
        seasonsIn(month).maxOfOrNull { it.multiplier } ?: BigDecimal.ONE

    fun multipliers(): Map<Month, BigDecimal> =
        Month.entries.associateWith { multiplierFor(it) }
}

object SeasonalPlan {

    /**
     * Spreads an annual budget across the twelve months in proportion to their
     * multipliers, preserving the annual total exactly.
     *
     * The multipliers scale the monthly base while the annual figure stays
     * fixed, so the shares are normalised by their sum rather than applied
     * directly — applying 1.8 to a month without normalising would spend more
     * than the year has.
     */
    fun monthlySpend(annual: Jod, calendar: SeasonCalendar): Map<Month, Jod> {
        val months = Month.entries
        val weights = months.map { calendar.multiplierFor(it) }
        val shares = Jod.splitEvenly(annual, weights)
        return months.zip(shares).toMap()
    }
}
