package com.gs3.marketingops.domain.money

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * An amount in Jordanian dinars, held as whole fils.
 *
 * Money is never a `Double` here. A dinar is a thousand fils, so fils are the
 * smallest unit that exists and every amount is an exact integer count of them
 * — which is what lets a twelve-month budget split add back up to the annual
 * figure to the fils, instead of drifting by a few hundred over a year.
 *
 * Prices are shown without decimals; fils appear only where a fils-level value
 * genuinely occurs, such as a price per square metre or a monthly instalment.
 */
@JvmInline
value class Jod private constructor(val fils: Long) : Comparable<Jod> {

    /** The amount in dinars, exact, for percentage and ratio arithmetic. */
    val dinars: BigDecimal get() = BigDecimal.valueOf(fils).movePointLeft(3)

    operator fun plus(other: Jod): Jod = Jod(Math.addExact(fils, other.fils))

    operator fun minus(other: Jod): Jod = Jod(Math.subtractExact(fils, other.fils))

    operator fun times(count: Int): Jod = Jod(Math.multiplyExact(fils, count.toLong()))

    /** Scales the amount, rounding half-up to the nearest fils. */
    fun scaledBy(factor: BigDecimal): Jod = ofDinars(dinars.multiply(factor))

    /** Takes a percentage of the amount — `percentOf("3")` is three per cent. */
    fun percent(rate: BigDecimal): Jod = scaledBy(rate.movePointLeft(2))

    /** Divides into [parts] equal shares, rounding half-up; see [splitEvenly] to divide without loss. */
    fun dividedBy(parts: Int): Jod {
        require(parts > 0) { "Cannot divide an amount into $parts parts" }
        return Jod(BigDecimal.valueOf(fils).divide(BigDecimal.valueOf(parts.toLong()), 0, RoundingMode.HALF_UP).toLong())
    }

    /** This amount as a proportion of [total], to six places. Zero when [total] is zero. */
    fun ratioOf(total: Jod): BigDecimal =
        if (total.fils == 0L) BigDecimal.ZERO
        else BigDecimal.valueOf(fils).divide(BigDecimal.valueOf(total.fils), 6, RoundingMode.HALF_UP)

    override fun compareTo(other: Jod): Int = fils.compareTo(other.fils)

    /** Deliberately plain. User-facing text goes through [MoneyFormat], which knows the locale. */
    override fun toString(): String = "${dinars.toPlainString()} JOD"

    companion object {
        val ZERO: Jod = Jod(0)

        fun ofDinars(dinars: Long): Jod = Jod(Math.multiplyExact(dinars, 1_000L))

        fun ofDinars(dinars: BigDecimal): Jod =
            Jod(dinars.movePointRight(3).setScale(0, RoundingMode.HALF_UP).longValueExact())

        fun ofFils(fils: Long): Jod = Jod(fils)

        /**
         * Splits [total] across [parts] weights so that the shares add back up to
         * [total] exactly — the largest-remainder method.
         *
         * Rounding each share independently is the obvious approach and it loses
         * money: twelve monthly budgets each rounded to the dinar do not re-sum
         * to the annual figure. Here every share is floored, and the fils left
         * over are handed out one at a time to the shares with the largest
         * discarded fraction, so the total is preserved by construction.
         */
        fun splitEvenly(total: Jod, weights: List<BigDecimal>): List<Jod> {
            require(weights.isNotEmpty()) { "Cannot split an amount across no weights" }
            require(weights.none { it.signum() < 0 }) { "A share weight cannot be negative" }

            val weightTotal = weights.fold(BigDecimal.ZERO, BigDecimal::add)
            if (weightTotal.signum() == 0) {
                // No weights at all: fall back to equal shares rather than losing the total.
                return splitEvenly(total, weights.map { BigDecimal.ONE })
            }

            val exact = weights.map { weight ->
                BigDecimal.valueOf(total.fils).multiply(weight)
                    .divide(weightTotal, 10, RoundingMode.HALF_UP)
            }
            val floored = exact.map { it.setScale(0, RoundingMode.FLOOR).longValueExact() }
            var remainder = total.fils - floored.sum()

            val order = exact.indices.sortedByDescending { index ->
                exact[index].subtract(BigDecimal.valueOf(floored[index]))
            }
            val shares = floored.toMutableList()
            var cursor = 0
            while (remainder > 0 && order.isNotEmpty()) {
                shares[order[cursor % order.size]] += 1
                remainder -= 1
                cursor += 1
            }
            return shares.map { Jod(it) }
        }
    }
}

/** Sums a collection of amounts. */
fun Iterable<Jod>.sum(): Jod = fold(Jod.ZERO, Jod::plus)
