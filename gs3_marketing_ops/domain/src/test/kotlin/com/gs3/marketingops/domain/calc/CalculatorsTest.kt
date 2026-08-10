package com.gs3.marketingops.domain.calc

import com.gs3.marketingops.domain.money.Jod
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.math.BigDecimal

class FeeCalculatorTest {

    @Test
    fun `three per cent plus three per cent on a ninety thousand dinar unit`() {
        val estimate = FeeCalculator.estimate(Jod.ofDinars(90_000))
        assertEquals(Jod.ofDinars(2_700), estimate.registrationFee)
        assertEquals(Jod.ofDinars(2_700), estimate.salesTax)
        assertEquals(Jod.ofDinars(5_400), estimate.totalFees)
    }

    @Test
    fun `fees are charged on the assessed value, not the sale price`() {
        // The distinction the disclaimer exists for. An assessment at 80% of the
        // sale price changes the fee by more than a thousand dinars.
        val estimate = FeeCalculator.estimate(Jod.ofDinars(90_000), assessedValueRatio = BigDecimal("0.80"))
        assertEquals(Jod.ofDinars(72_000), estimate.assessedValue)
        assertEquals(Jod.ofDinars(4_320), estimate.totalFees)
        assertEquals(Jod.ofDinars(90_000), estimate.salePrice)
    }

    @Test
    fun `the default assessment is the sale price, which is the conservative direction`() {
        // A buyer quoted a fee that turns out lower is pleased; one quoted a fee
        // that turns out higher was misled at the worst possible moment.
        val estimate = FeeCalculator.estimate(Jod.ofDinars(131_000))
        assertEquals(Jod.ofDinars(131_000), estimate.assessedValue)
        assertEquals(BigDecimal("1.00"), FeeCalculator.DEFAULT_ASSESSED_VALUE_RATIO)
    }

    @Test
    fun `a known assessment from the Department is used as given`() {
        val estimate = FeeCalculator.estimateOnAssessedValue(
            salePrice = Jod.ofDinars(151_000),
            assessedValue = Jod.ofDinars(140_000),
        )
        assertEquals(Jod.ofDinars(8_400), estimate.totalFees)
    }

    @Test
    fun `the company contribution is capped and never exceeds the fees themselves`() {
        val big = FeeCalculator.estimate(Jod.ofDinars(151_000))
        assertEquals(Jod.ofDinars(2_500), big.companyContribution)
        assertEquals(Jod.ofDinars(9_060) - Jod.ofDinars(2_500), big.payableByBuyer)

        // On a tiny fee the company pays the fee, not the cap — it is a
        // contribution toward a cost, so it cannot exceed the cost.
        val small = FeeCalculator.estimateOnAssessedValue(Jod.ofDinars(10_000), Jod.ofDinars(10_000))
        assertEquals(Jod.ofDinars(600), small.totalFees)
        assertEquals(Jod.ofDinars(600), small.companyContribution)
        assertEquals(Jod.ZERO, small.payableByBuyer)
    }

    @Test
    fun `rates are editable, because regulation changes and an app outlives its copy of the law`() {
        val estimate = FeeCalculator.estimate(
            Jod.ofDinars(100_000),
            rates = FeeRates(registrationPercent = BigDecimal("2"), salesTaxPercent = BigDecimal("1.5")),
        )
        assertEquals(Jod.ofDinars(2_000), estimate.registrationFee)
        assertEquals(Jod.ofDinars(1_500), estimate.salesTax)
    }

    @Test
    fun `a contribution floor above its cap is rejected`() {
        val thrown = runCatching {
            CompanyContribution(cap = Jod.ofDinars(2_000), floor = Jod.ofDinars(2_500))
        }.exceptionOrNull()
        assertTrue(thrown is IllegalArgumentException)
    }
}

class InstalmentCalculatorTest {

    @Test
    fun `an interest-free plan is simply the balance divided by the term`() {
        val plan = InstalmentCalculator.plan(
            price = Jod.ofDinars(90_000),
            downPayment = Jod.ofDinars(18_000),
            termMonths = 60,
            annualRatePercent = BigDecimal.ZERO,
        )
        assertEquals(Jod.ofDinars(72_000), plan.financed)
        assertEquals(Jod.ofDinars(1_200), plan.monthlyPayment)
        assertEquals(Jod.ZERO, plan.totalCostOfCredit)
    }

    @Test
    fun `a financed plan uses the annuity formula`() {
        // 72,000 over 240 months at 6% nominal is 515.830 JOD a month.
        val plan = InstalmentCalculator.plan(
            price = Jod.ofDinars(90_000),
            downPayment = Jod.ofDinars(18_000),
            termMonths = 240,
            annualRatePercent = BigDecimal("6"),
        )
        assertEquals(Jod.ofFils(515_830), plan.monthlyPayment)
        assertTrue(plan.totalCostOfCredit > Jod.ZERO)
    }

    @Test
    fun `a down payment larger than the price is rejected`() {
        val thrown = runCatching {
            InstalmentCalculator.plan(Jod.ofDinars(90_000), Jod.ofDinars(95_000), 60, BigDecimal.ZERO)
        }.exceptionOrNull()
        assertTrue(thrown is IllegalArgumentException)
    }

    @Test
    fun `a zero-month term is rejected rather than dividing by zero`() {
        val thrown = runCatching {
            InstalmentCalculator.plan(Jod.ofDinars(90_000), Jod.ZERO, 0, BigDecimal.ZERO)
        }.exceptionOrNull()
        assertTrue(thrown is IllegalArgumentException)
    }

    @Test
    fun `rent against instalment is the argument for a family already renting`() {
        val comparison = RentComparison(
            monthlyRent = Jod.ofDinars(450),
            monthlyInstalment = Jod.ofDinars(490),
            years = 10,
        )
        assertEquals(Jod.ofDinars(54_000), comparison.totalRent)
        assertEquals(Jod.ofDinars(58_800), comparison.totalInstalments)
        assertEquals(Jod.ofDinars(40), comparison.monthlyDifference)
        assertTrue(comparison.isComparable(), "40 dinars on 450 is inside the 15% band where the argument lands")
    }

    @Test
    fun `an instalment far above the rent is not comparable and the app should not pretend otherwise`() {
        val comparison = RentComparison(
            monthlyRent = Jod.ofDinars(300),
            monthlyInstalment = Jod.ofDinars(700),
            years = 10,
        )
        assertFalse(comparison.isComparable())
    }
}
