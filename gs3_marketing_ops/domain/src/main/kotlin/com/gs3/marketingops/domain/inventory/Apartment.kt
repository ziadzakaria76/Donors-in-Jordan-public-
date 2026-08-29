package com.gs3.marketingops.domain.inventory

import com.gs3.marketingops.domain.money.Jod
import com.gs3.marketingops.domain.money.sum
import java.math.BigDecimal
import java.math.RoundingMode

/**
 * How a unit is meant to be sold. Set by the sales strategy, not by the app,
 * and it changes what the app permits: class A carries no cash discount, and
 * class D is directed selling with a longer cycle, so its lack of enquiries is
 * not the alarm it would be on a class A unit.
 */
enum class PriorityClass {
    /** Liquidity driver — fastest turnover, no cash discount permitted. */
    A,

    /** Distinctive value. */
    B,

    /** Premium roof unit. */
    C,

    /** Flagship — directed selling only, longer cycle. */
    D,
    ;

    val allowsCashDiscount: Boolean get() = this != A
}

/** The three the team actually uses. "On hold" and "Under negotiation" were not wanted (A5). */
enum class UnitStatus { AVAILABLE, RESERVED, CONTRACTED }

/**
 * One of the fourteen apartments.
 *
 * Areas are whole square metres and prices whole dinars, exactly as the sales
 * brochure states them. Nothing here is derived from a formula, because real
 * price schedules do not follow one — unit 3 is 151 m² at 107,000 while unit 6
 * is 151 m² at 90,000, and the difference is the ground floor's thirty metres
 * of terrace, not arithmetic.
 */
data class Apartment(
    val number: Int,
    val positionEn: String,
    val positionAr: String,
    val internalArea: Int,
    val externalArea: Int,
    val listPrice: Jod,
    val priorityClass: PriorityClass,
    val status: UnitStatus = UnitStatus.AVAILABLE,
) {
    init {
        require(number > 0) { "Unit number must be positive, was $number" }
        require(internalArea > 0) { "Unit $number has no internal area" }
        require(externalArea >= 0) { "Unit $number has a negative external area" }
    }

    val hasExternalArea: Boolean get() = externalArea > 0

    /** Price per square metre of internal area — the comparison buyers actually make. */
    val pricePerSquareMetre: Jod
        get() = Jod.ofFils(
            BigDecimal.valueOf(listPrice.fils)
                .divide(BigDecimal.valueOf(internalArea.toLong()), 0, RoundingMode.HALF_UP)
                .toLong()
        )
}

/** Totals across a schedule of units. The brief asserts these, so they are computed, not typed in. */
data class InventoryTotals(
    val unitCount: Int,
    val internalArea: Int,
    val externalArea: Int,
    val grossDevelopmentValue: Jod,
) {
    /**
     * Weighted average price per square metre — the whole schedule's value over
     * its whole internal area. Not the mean of each unit's own rate, which
     * would weight a 151 m² apartment the same as a 235 m² one.
     */
    val weightedPricePerSquareMetre: Jod
        get() = Jod.ofFils(
            BigDecimal.valueOf(grossDevelopmentValue.fils)
                .divide(BigDecimal.valueOf(internalArea.toLong()), 0, RoundingMode.HALF_UP)
                .toLong()
        )
}

fun List<Apartment>.totals(): InventoryTotals = InventoryTotals(
    unitCount = size,
    internalArea = sumOf { it.internalArea },
    externalArea = sumOf { it.externalArea },
    grossDevelopmentValue = map { it.listPrice }.sum(),
)

/** Value of the units in a given status — what "sold" means on the dashboard ring. */
fun List<Apartment>.valueOf(status: UnitStatus): Jod =
    filter { it.status == status }.map { it.listPrice }.sum()
