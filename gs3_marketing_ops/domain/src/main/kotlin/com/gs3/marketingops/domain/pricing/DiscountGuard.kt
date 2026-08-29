package com.gs3.marketingops.domain.pricing

import com.gs3.marketingops.domain.inventory.Apartment
import com.gs3.marketingops.domain.money.Jod
import java.math.BigDecimal
import java.math.RoundingMode

/** Something that must be resolved before a contracted price can be saved. */
enum class DiscountBlock {
    /** Over the 3.5% ceiling. Clears only with a written justification. */
    EXCEEDS_CEILING,

    /** Class A carries no cash discount — it is the liquidity driver. */
    CLASS_A_NO_CASH_DISCOUNT,

    /** A discount was entered but no justification was written. */
    JUSTIFICATION_MISSING,
}

/** Something the manager should see but which does not stop the save. */
enum class DiscountWarning {
    /** Policy allows at most two discounted units at any one time. */
    CONCURRENT_DISCOUNT_LIMIT,

    /** The ladder has six non-price steps before this one; they should be spent first. */
    INCENTIVE_LADDER_NOT_EXHAUSTED,
}

data class DiscountAssessment(
    val listPrice: Jod,
    val agreedPrice: Jod,
    val discount: Jod,
    val discountPercent: BigDecimal,
    val blocks: List<DiscountBlock>,
    val warnings: List<DiscountWarning>,
) {
    val isDiscounted: Boolean get() = discount > Jod.ZERO

    /** True when the price may be saved as it stands. */
    val canSave: Boolean get() = blocks.isEmpty()
}

/**
 * The price-ladder guard, applied when a unit is marked contracted.
 *
 * The ceiling is 3.5% of list, at most two units may be discounted at once, and
 * a cash discount is the seventh and last step of the incentive ladder — six
 * non-price concessions come first, because a kitchen costs the company less
 * than the same money off the price and is worth more to the buyer.
 *
 * Note what is deliberately *not* here: nothing silently caps or adjusts the
 * price. A discount over the ceiling is not refused, it is blocked pending a
 * written reason, which is then stored. The distinction matters — a rule that
 * quietly rewrites a manager's number gets worked around within a week.
 */
object DiscountGuard {

    /** 3.5% of list price. */
    val CEILING_PERCENT: BigDecimal = BigDecimal("3.5")

    /** At most two units may carry a discount at the same time. */
    const val MAX_CONCURRENT_DISCOUNTED_UNITS: Int = 2

    fun assess(
        apartment: Apartment,
        agreedPrice: Jod,
        otherDiscountedUnits: Int = 0,
        justification: String? = null,
        nonPriceIncentivesOffered: Int = IncentiveLadder.NON_PRICE_STEPS,
    ): DiscountAssessment {
        require(otherDiscountedUnits >= 0) { "Cannot have a negative number of discounted units" }
        require(agreedPrice >= Jod.ZERO) { "An agreed price cannot be negative" }

        val listPrice = apartment.listPrice
        // An agreed price above list is a premium, not a discount — clamp at zero
        // rather than reporting a negative discount that would read as an alarm.
        val discount = if (agreedPrice >= listPrice) Jod.ZERO else listPrice - agreedPrice

        val percent = if (listPrice.fils == 0L) BigDecimal.ZERO else
            BigDecimal.valueOf(discount.fils)
                .divide(BigDecimal.valueOf(listPrice.fils), 6, RoundingMode.HALF_UP)
                .movePointRight(2)
                .setScale(2, RoundingMode.HALF_UP)

        val blocks = buildList {
            if (discount > Jod.ZERO) {
                if (!apartment.priorityClass.allowsCashDiscount) add(DiscountBlock.CLASS_A_NO_CASH_DISCOUNT)
                if (percent > CEILING_PERCENT) add(DiscountBlock.EXCEEDS_CEILING)
                if (justification.isNullOrBlank()) add(DiscountBlock.JUSTIFICATION_MISSING)
            }
        }

        val warnings = buildList {
            if (discount > Jod.ZERO) {
                if (otherDiscountedUnits >= MAX_CONCURRENT_DISCOUNTED_UNITS) {
                    add(DiscountWarning.CONCURRENT_DISCOUNT_LIMIT)
                }
                if (nonPriceIncentivesOffered < IncentiveLadder.NON_PRICE_STEPS) {
                    add(DiscountWarning.INCENTIVE_LADDER_NOT_EXHAUSTED)
                }
            }
        }

        return DiscountAssessment(listPrice, agreedPrice, discount, percent, blocks, warnings)
    }
}

/**
 * The seven-step incentive ladder, used strictly in order. The first six cost
 * the company less than they are worth to the buyer; the seventh is the only
 * one that comes straight off the price, which is why it is last.
 */
enum class IncentiveStep(val order: Int, val isPriceConcession: Boolean) {
    REGISTRATION_FEE_CONTRIBUTION(1, false),
    FITTED_KITCHEN(2, false),
    AIR_CONDITIONING_UNITS(3, false),
    MASTER_BEDROOM_WARDROBES(4, false),
    SERVICE_FEE_WAIVER(5, false),
    EXTENDED_FINISHING_WARRANTY(6, false),
    CASH_DISCOUNT(7, true),
    ;

    companion object
}

object IncentiveLadder {
    val steps: List<IncentiveStep> = IncentiveStep.entries.sortedBy { it.order }

    /** How many rungs come before the cash discount. */
    val NON_PRICE_STEPS: Int = steps.count { !it.isPriceConcession }

    /** The next rung to offer, or null once the ladder is spent. */
    fun nextStep(stepsAlreadyOffered: Int): IncentiveStep? = steps.getOrNull(stepsAlreadyOffered)
}
