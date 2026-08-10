package com.gs3.marketingops.domain.pricing

import com.gs3.marketingops.domain.inventory.Gs3Schedule
import com.gs3.marketingops.domain.money.Jod
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.math.BigDecimal

class DiscountGuardTest {

    private val classB = Gs3Schedule.apartments.first { it.number == 3 }   // 107,000
    private val classA = Gs3Schedule.apartments.first { it.number == 6 }   // 90,000

    @Test
    fun `selling at list price is not a discount and needs nothing`() {
        val assessment = DiscountGuard.assess(classB, agreedPrice = Jod.ofDinars(107_000))
        assertFalse(assessment.isDiscounted)
        assertEquals(BigDecimal("0.00"), assessment.discountPercent)
        assertTrue(assessment.canSave)
        assertTrue(assessment.warnings.isEmpty())
    }

    @Test
    fun `a discount within the ceiling saves once a reason is written`() {
        // 3,000 off 107,000 is 2.80%.
        val withoutReason = DiscountGuard.assess(classB, Jod.ofDinars(104_000))
        assertEquals(BigDecimal("2.80"), withoutReason.discountPercent)
        assertFalse(withoutReason.canSave)
        assertTrue(withoutReason.blocks.contains(DiscountBlock.JUSTIFICATION_MISSING))

        val withReason = DiscountGuard.assess(classB, Jod.ofDinars(104_000), justification = "Cash buyer, closing in two weeks")
        assertTrue(withReason.canSave)
    }

    @Test
    fun `over the ceiling stays blocked until justified, and is never silently capped`() {
        // 5,000 off 107,000 is 4.67% — over the 3.5% ceiling.
        val assessment = DiscountGuard.assess(classB, Jod.ofDinars(102_000))
        assertEquals(BigDecimal("4.67"), assessment.discountPercent)
        assertTrue(assessment.blocks.contains(DiscountBlock.EXCEEDS_CEILING))
        assertFalse(assessment.canSave)

        // The agreed price comes back exactly as entered. A guard that quietly
        // rewrote a manager's number would be worked around within a week.
        assertEquals(Jod.ofDinars(102_000), assessment.agreedPrice)
        assertEquals(Jod.ofDinars(5_000), assessment.discount)
    }

    @Test
    fun `the ceiling is inclusive at exactly three and a half per cent`() {
        // 3.5% of 90,000 is 3,150.
        val exactly = DiscountGuard.assess(classA, Jod.ofDinars(86_850), justification = "authorised")
        assertEquals(BigDecimal("3.50"), exactly.discountPercent)
        assertFalse(exactly.blocks.contains(DiscountBlock.EXCEEDS_CEILING))
    }

    @Test
    fun `class A carries no cash discount at all`() {
        val assessment = DiscountGuard.assess(classA, Jod.ofDinars(89_000), justification = "buyer pushed hard")
        assertTrue(assessment.blocks.contains(DiscountBlock.CLASS_A_NO_CASH_DISCOUNT))
        assertFalse(assessment.canSave)
    }

    @Test
    fun `a third discounted unit warns without blocking the sale`() {
        val assessment = DiscountGuard.assess(
            classB,
            Jod.ofDinars(105_000),
            otherDiscountedUnits = 2,
            justification = "long-standing referral",
        )
        assertTrue(assessment.warnings.contains(DiscountWarning.CONCURRENT_DISCOUNT_LIMIT))
        assertTrue(assessment.canSave, "policy is a warning here, not a veto — the manager decides")
    }

    @Test
    fun `discounting before the ladder is spent is flagged`() {
        val assessment = DiscountGuard.assess(
            classB,
            Jod.ofDinars(105_000),
            justification = "buyer asked",
            nonPriceIncentivesOffered = 1,
        )
        assertTrue(assessment.warnings.contains(DiscountWarning.INCENTIVE_LADDER_NOT_EXHAUSTED))
    }

    @Test
    fun `a price above list is a premium, not a negative discount`() {
        val assessment = DiscountGuard.assess(classB, Jod.ofDinars(110_000))
        assertEquals(Jod.ZERO, assessment.discount)
        assertFalse(assessment.isDiscounted)
        assertTrue(assessment.canSave)
    }

    @Test
    fun `the ladder runs six non-price steps before the cash discount`() {
        assertEquals(7, IncentiveLadder.steps.size)
        assertEquals(6, IncentiveLadder.NON_PRICE_STEPS)
        assertEquals(IncentiveStep.CASH_DISCOUNT, IncentiveLadder.steps.last())
        assertTrue(IncentiveLadder.steps.dropLast(1).none { it.isPriceConcession })
        assertEquals(IncentiveStep.REGISTRATION_FEE_CONTRIBUTION, IncentiveLadder.nextStep(0))
        assertEquals(IncentiveStep.CASH_DISCOUNT, IncentiveLadder.nextStep(6))
        assertEquals(null, IncentiveLadder.nextStep(7))
    }
}

class PriceEscalationTest {

    @Test
    fun `every third sale earns a rise`() {
        assertEquals(0, PriceEscalation.escalationsEarned(2))
        assertEquals(1, PriceEscalation.escalationsEarned(3))
        assertEquals(1, PriceEscalation.escalationsEarned(5))
        assertEquals(2, PriceEscalation.escalationsEarned(6))
    }

    @Test
    fun `the app counts down to the next trigger`() {
        assertEquals(3, PriceEscalation.unitsUntilNextEscalation(0))
        assertEquals(1, PriceEscalation.unitsUntilNextEscalation(2))
        assertEquals(3, PriceEscalation.unitsUntilNextEscalation(3))
    }

    @Test
    fun `an earned but unapplied rise is flagged`() {
        // An announced escalation that never gets applied teaches buyers the
        // deadline was theatre, and the next one moves nobody.
        assertTrue(PriceEscalation.isEscalationDue(unitsContracted = 3, escalationsApplied = 0))
        assertFalse(PriceEscalation.isEscalationDue(unitsContracted = 3, escalationsApplied = 1))
        assertFalse(PriceEscalation.isEscalationDue(unitsContracted = 2, escalationsApplied = 0))
    }

    @Test
    fun `rises compound`() {
        val base = Jod.ofDinars(90_000)
        assertEquals(base, PriceEscalation.escalatedPrice(base, 0))
        assertEquals(Jod.ofDinars(91_800), PriceEscalation.escalatedPrice(base, 1))
        // 90,000 x 1.02^2 = 93,636, not 93,600.
        assertEquals(Jod.ofDinars(93_636), PriceEscalation.escalatedPrice(base, 2))
    }
}
