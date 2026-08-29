package com.gs3.marketingops.domain.calc

import com.gs3.marketingops.domain.money.Jod
import java.math.BigDecimal
import java.math.MathContext
import java.math.RoundingMode

data class InstalmentPlan(
    val price: Jod,
    val downPayment: Jod,
    val financed: Jod,
    val termMonths: Int,
    val annualRatePercent: BigDecimal,
    val monthlyPayment: Jod,
) {
    val totalPaid: Jod get() = downPayment + (monthlyPayment * termMonths)
    val totalCostOfCredit: Jod get() = totalPaid - price
}

object InstalmentCalculator {

    /**
     * A standard annuity payment. Indicative only — the bank sets the real
     * terms, and the disclaimer saying so is shown inline every time, not
     * buried in an About screen.
     */
    fun plan(
        price: Jod,
        downPayment: Jod,
        termMonths: Int,
        annualRatePercent: BigDecimal,
    ): InstalmentPlan {
        require(termMonths > 0) { "A term of $termMonths months is not a term" }
        require(downPayment <= price) { "Down payment $downPayment exceeds the price $price" }
        require(annualRatePercent.signum() >= 0) { "A negative interest rate is not supported" }

        val financed = price - downPayment
        val monthly = if (annualRatePercent.signum() == 0) {
            financed.dividedBy(termMonths)
        } else {
            annuityPayment(financed, termMonths, annualRatePercent)
        }

        return InstalmentPlan(price, downPayment, financed, termMonths, annualRatePercent, monthly)
    }

    private fun annuityPayment(financed: Jod, termMonths: Int, annualRatePercent: BigDecimal): Jod {
        val context = MathContext.DECIMAL128
        val monthlyRate = annualRatePercent.movePointLeft(2).divide(BigDecimal(12), context)
        val growth = (BigDecimal.ONE + monthlyRate).pow(termMonths, context)
        // payment = P · i · (1+i)^n / ((1+i)^n − 1)
        val numerator = financed.dinars.multiply(monthlyRate, context).multiply(growth, context)
        val denominator = growth.subtract(BigDecimal.ONE, context)
        return Jod.ofDinars(numerator.divide(denominator, context).setScale(3, RoundingMode.HALF_UP))
    }
}

/**
 * Rent against instalment — the strongest argument available to a family
 * already renting, because it reframes the question from "can I afford to buy"
 * to "what am I getting for money I am already spending".
 */
data class RentComparison(
    val monthlyRent: Jod,
    val monthlyInstalment: Jod,
    val years: Int,
) {
    val totalRent: Jod get() = monthlyRent * (years * 12)
    val totalInstalments: Jod get() = monthlyInstalment * (years * 12)
    val monthlyDifference: Jod get() = monthlyInstalment - monthlyRent

    /** True when the instalment is within [tolerance] of the rent — the moment the argument lands. */
    fun isComparable(tolerance: BigDecimal = BigDecimal("0.15")): Boolean {
        if (monthlyRent.fils == 0L) return false
        val ceiling = monthlyRent.scaledBy(BigDecimal.ONE + tolerance)
        return monthlyInstalment <= ceiling
    }
}
