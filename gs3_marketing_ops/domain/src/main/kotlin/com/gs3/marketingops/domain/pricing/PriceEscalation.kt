package com.gs3.marketingops.domain.pricing

import com.gs3.marketingops.domain.money.Jod
import java.math.BigDecimal

/**
 * The announced escalation: prices rise 2% after every three units sold.
 *
 * The app tracks progress toward the next trigger and prompts the manager to
 * apply it, because an announced escalation that is not applied is worse than
 * never announcing one — it teaches buyers that the deadline was theatre, and
 * the next one will not move anybody.
 */
object PriceEscalation {

    val STEP_PERCENT: BigDecimal = BigDecimal("2")
    const val UNITS_PER_STEP: Int = 3

    private val multiplier: BigDecimal = BigDecimal.ONE + STEP_PERCENT.movePointLeft(2)

    /** How many 2% rises the sales to date have earned. */
    fun escalationsEarned(unitsContracted: Int): Int {
        require(unitsContracted >= 0) { "Cannot have sold $unitsContracted units" }
        return unitsContracted / UNITS_PER_STEP
    }

    /** Sales still needed before the next rise triggers. */
    fun unitsUntilNextEscalation(unitsContracted: Int): Int {
        require(unitsContracted >= 0) { "Cannot have sold $unitsContracted units" }
        return UNITS_PER_STEP - (unitsContracted % UNITS_PER_STEP)
    }

    /** True when sales have earned a rise that has not been applied yet. */
    fun isEscalationDue(unitsContracted: Int, escalationsApplied: Int): Boolean =
        escalationsEarned(unitsContracted) > escalationsApplied

    /** The list price after [escalations] compounding 2% rises. */
    fun escalatedPrice(basePrice: Jod, escalations: Int): Jod {
        require(escalations >= 0) { "Cannot apply $escalations escalations" }
        var price = basePrice
        repeat(escalations) { price = price.scaledBy(multiplier) }
        return price
    }
}
