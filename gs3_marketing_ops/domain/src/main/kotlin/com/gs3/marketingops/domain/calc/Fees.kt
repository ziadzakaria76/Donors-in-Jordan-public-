package com.gs3.marketingops.domain.calc

import com.gs3.marketingops.domain.money.Jod
import java.math.BigDecimal

/**
 * Rates are editable because they are set by regulation, not by the company,
 * and a rate baked into an app outlives the law it was copied from.
 */
data class FeeRates(
    val registrationPercent: BigDecimal = BigDecimal("3"),
    val salesTaxPercent: BigDecimal = BigDecimal("3"),
)

/**
 * What the company will put toward the buyer's registration fees.
 *
 * A capped *contribution*. Never an exemption — the company has no power to
 * exempt anyone from a government fee, and saying so in writing is a promise it
 * cannot keep. `verifyStrings` fails the build if the word turns up in either
 * string file.
 */
data class CompanyContribution(
    val cap: Jod = Jod.ofDinars(2_500),
    val floor: Jod = Jod.ofDinars(2_000),
) {
    init {
        require(floor <= cap) { "Contribution floor $floor is above its cap $cap" }
    }

    fun applicableTo(totalFees: Jod): Jod = if (totalFees < cap) totalFees else cap
}

data class FeeEstimate(
    val salePrice: Jod,
    val assessedValue: Jod,
    val registrationFee: Jod,
    val salesTax: Jod,
    val companyContribution: Jod,
) {
    val totalFees: Jod get() = registrationFee + salesTax
    val payableByBuyer: Jod get() = totalFees - companyContribution
}

object FeeCalculator {

    /**
     * Registration fee and sales tax are charged on the value the Department of
     * Lands and Survey assesses, **not** on the sale price. The two are not the
     * same number, which is why the assessed value is its own input with its own
     * default rather than being quietly derived and presented as fact.
     *
     * The default is 100% of the sale price on purpose: it is the conservative
     * direction. A buyer quoted a fee that turns out lower is pleased; one
     * quoted a fee that turns out higher was misled at the worst moment.
     */
    val DEFAULT_ASSESSED_VALUE_RATIO: BigDecimal = BigDecimal("1.00")

    fun estimate(
        salePrice: Jod,
        assessedValueRatio: BigDecimal = DEFAULT_ASSESSED_VALUE_RATIO,
        rates: FeeRates = FeeRates(),
        contribution: CompanyContribution = CompanyContribution(),
    ): FeeEstimate {
        require(assessedValueRatio.signum() > 0) { "Assessed value ratio must be positive" }
        return estimateOnAssessedValue(salePrice, salePrice.scaledBy(assessedValueRatio), rates, contribution)
    }

    /** For when the Department's actual assessment is known and should be used as given. */
    fun estimateOnAssessedValue(
        salePrice: Jod,
        assessedValue: Jod,
        rates: FeeRates = FeeRates(),
        contribution: CompanyContribution = CompanyContribution(),
    ): FeeEstimate {
        val registration = assessedValue.percent(rates.registrationPercent)
        val salesTax = assessedValue.percent(rates.salesTaxPercent)
        return FeeEstimate(
            salePrice = salePrice,
            assessedValue = assessedValue,
            registrationFee = registration,
            salesTax = salesTax,
            companyContribution = contribution.applicableTo(registration + salesTax),
        )
    }
}
