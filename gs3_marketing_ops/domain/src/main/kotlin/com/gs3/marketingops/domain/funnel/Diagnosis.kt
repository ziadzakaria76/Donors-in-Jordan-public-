package com.gs3.marketingops.domain.funnel

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * What a weak month actually is.
 *
 * The whole point of this type is the [priceIsACandidate] flag. The instinct
 * when sales are slow is to cut the price, and in three of these four cases
 * that is the wrong move — it costs real money and fixes nothing, because the
 * problem was upstream of price. The app names the problem so the conversation
 * starts in the right place.
 */
enum class Diagnosis(val priceIsACandidate: Boolean) {
    /** Plenty of people saw it and did not ask. Price or imagery, not demand. */
    PRICING_OR_IMAGERY(true),

    /** They asked and did not come. Response speed or copy, not price. */
    RESPONSE_SPEED_OR_COPY(false),

    /** They came and did not buy. Product, payment terms or competition, not reach. */
    PRODUCT_TERMS_OR_COMPETITION(false),

    /** Too few people saw it at all. Targeting or budget — cutting price changes nothing. */
    TARGETING_OR_BUDGET(false),

    /** Nothing is wrong. */
    ON_TRACK(false),
}

data class ChannelPerformance(
    val impressions: Long,
    val enquiries: Int,
    val viewings: Int,
    val contracts: Int,
)

/**
 * Expected rates for the channel, and how far below expectation counts as a
 * problem. The default tolerance treats anything under 60% of the expected rate
 * as the weak link — tight enough to catch a real break, loose enough not to
 * fire on a normal quiet fortnight.
 */
data class DiagnosisBenchmarks(
    val minimumImpressions: Long,
    val enquiryRate: BigDecimal,
    val viewingRate: BigDecimal,
    val contractRate: BigDecimal,
    val tolerance: BigDecimal = BigDecimal("0.60"),
)

object FunnelDiagnosis {

    /**
     * Order matters, and it is not the order the strategy document lists them in.
     *
     * Low impressions is tested first, because with too few impressions every
     * downstream count is low too — enquiries, viewings and contracts all look
     * broken, and the app would confidently diagnose a pricing problem on a
     * campaign that simply was not shown to anybody. Reach is the precondition
     * for reading any of the rest.
     */
    fun diagnose(performance: ChannelPerformance, benchmarks: DiagnosisBenchmarks): Diagnosis {
        if (performance.impressions < benchmarks.minimumImpressions) {
            return Diagnosis.TARGETING_OR_BUDGET
        }

        val expectedEnquiries = benchmarks.enquiryRate.multiply(BigDecimal.valueOf(performance.impressions))
        if (isShort(BigDecimal.valueOf(performance.enquiries.toLong()), expectedEnquiries, benchmarks.tolerance)) {
            return Diagnosis.PRICING_OR_IMAGERY
        }

        val expectedViewings = benchmarks.viewingRate.multiply(BigDecimal.valueOf(performance.enquiries.toLong()))
        if (isShort(BigDecimal.valueOf(performance.viewings.toLong()), expectedViewings, benchmarks.tolerance)) {
            return Diagnosis.RESPONSE_SPEED_OR_COPY
        }

        val expectedContracts = benchmarks.contractRate.multiply(BigDecimal.valueOf(performance.viewings.toLong()))
        if (isShort(BigDecimal.valueOf(performance.contracts.toLong()), expectedContracts, benchmarks.tolerance)) {
            return Diagnosis.PRODUCT_TERMS_OR_COMPETITION
        }

        return Diagnosis.ON_TRACK
    }

    private fun isShort(actual: BigDecimal, expected: BigDecimal, tolerance: BigDecimal): Boolean {
        if (expected.signum() <= 0) return false
        val threshold = expected.multiply(tolerance).setScale(4, RoundingMode.HALF_UP)
        return actual < threshold
    }
}
