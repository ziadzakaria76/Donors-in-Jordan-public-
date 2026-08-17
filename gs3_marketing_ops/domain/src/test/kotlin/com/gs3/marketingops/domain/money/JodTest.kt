package com.gs3.marketingops.domain.money

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.math.BigDecimal

class JodTest {

    @Test
    fun `a dinar is a thousand fils`() {
        assertEquals(1_000L, Jod.ofDinars(1).fils)
        assertEquals(BigDecimal("90.000"), Jod.ofDinars(90).dinars)
    }

    @Test
    fun `amounts add and subtract without drift`() {
        val total = (1..1_000).map { Jod.ofFils(1) }.sum()
        assertEquals(Jod.ofDinars(1), total)
    }

    @Test
    fun `percentages round half-up to the fils`() {
        assertEquals(Jod.ofDinars(2_700), Jod.ofDinars(90_000).percent(BigDecimal("3")))
        // 3% of 107,000 is 3,210 exactly; 3% of 98,000 is 2,940.
        assertEquals(Jod.ofDinars(3_210), Jod.ofDinars(107_000).percent(BigDecimal("3")))
        assertEquals(Jod.ofDinars(2_940), Jod.ofDinars(98_000).percent(BigDecimal("3")))
    }

    @Test
    fun `splitting preserves the total exactly, however awkward the weights`() {
        // The property that keeps a twelve-month budget adding up. Rounding each
        // share independently loses money; largest-remainder does not.
        val weights = listOf(BigDecimal("1.8"), BigDecimal("1.4"), BigDecimal("0.7"))
        val shares = Jod.splitEvenly(Jod.ofDinars(1_000), weights)
        assertEquals(Jod.ofDinars(1_000), shares.sum())
        assertTrue(shares[0] > shares[1] && shares[1] > shares[2])
    }

    @Test
    fun `splitting one fils three ways still totals one fils`() {
        val shares = Jod.splitEvenly(Jod.ofFils(1), List(3) { BigDecimal.ONE })
        assertEquals(Jod.ofFils(1), shares.sum())
        assertEquals(3, shares.size)
    }

    @Test
    fun `splitting across zero weights falls back to equal shares rather than losing the total`() {
        val shares = Jod.splitEvenly(Jod.ofDinars(12), List(12) { BigDecimal.ZERO })
        assertEquals(Jod.ofDinars(12), shares.sum())
        assertTrue(shares.all { it == Jod.ofDinars(1) })
    }

    @Test
    fun `a ratio of zero is zero, not a division by zero`() {
        assertEquals(BigDecimal.ZERO, Jod.ofDinars(5).ratioOf(Jod.ZERO))
    }

    @Test
    fun `dividing by zero parts is rejected`() {
        assertTrue(runCatching { Jod.ofDinars(10).dividedBy(0) }.exceptionOrNull() is IllegalArgumentException)
    }

    @Test
    fun `amounts compare and sort`() {
        val sorted = listOf(Jod.ofDinars(90_000), Jod.ofDinars(151_000), Jod.ofDinars(98_000)).sorted()
        assertEquals(listOf(Jod.ofDinars(90_000), Jod.ofDinars(98_000), Jod.ofDinars(151_000)), sorted)
    }
}

class MoneyFormatTest {

    @Test
    fun `prices carry no decimals and group in thousands`() {
        assertEquals(
            "90,000 JOD",
            MoneyFormat.formatMoney(Jod.ofDinars(90_000), AppLanguage.ENGLISH),
        )
        assertEquals(
            "1,496,000 JOD",
            MoneyFormat.formatMoney(Jod.ofDinars(1_496_000), AppLanguage.ENGLISH),
        )
    }

    @Test
    fun `Arabic uses the dinar's Arabic abbreviation`() {
        assertEquals("90,000 د.أ", MoneyFormat.formatMoney(Jod.ofDinars(90_000), AppLanguage.ARABIC))
    }

    @Test
    fun `Arabic-Indic digits use the Arabic thousands separator, not a comma`() {
        // A comma between Arabic-Indic digits reads as a decimal point to an
        // Arabic reader, which would turn 90,000 dinars into ninety.
        assertEquals(
            "٩٠٬٠٠٠ د.أ",
            MoneyFormat.formatMoney(Jod.ofDinars(90_000), AppLanguage.ARABIC, NumeralStyle.ARABIC_INDIC),
        )
    }

    @Test
    fun `fils appear only where asked for`() {
        val perSquareMetre = Jod.ofFils(644_828)
        assertEquals("645 JOD", MoneyFormat.formatMoney(perSquareMetre, AppLanguage.ENGLISH))
        assertEquals("644.828 JOD", MoneyFormat.formatMoney(perSquareMetre, AppLanguage.ENGLISH, decimals = 3))
        assertEquals(
            "٦٤٤٫٨٢٨ د.أ",
            MoneyFormat.formatMoney(perSquareMetre, AppLanguage.ARABIC, NumeralStyle.ARABIC_INDIC, decimals = 3),
        )
    }

    @Test
    fun `more than three decimals is rejected, because the dinar has three`() {
        assertTrue(
            runCatching {
                MoneyFormat.formatMoney(Jod.ofDinars(1), AppLanguage.ENGLISH, decimals = 4)
            }.exceptionOrNull() is IllegalArgumentException
        )
    }

    @Test
    fun `negative amounts keep their sign in front`() {
        assertEquals("-1,200 JOD", MoneyFormat.formatMoney(Jod.ZERO - Jod.ofDinars(1_200), AppLanguage.ENGLISH))
    }

    @Test
    fun `percentages render in both digit styles`() {
        assertEquals("27.3%", MoneyFormat.formatPercent(BigDecimal("27.27"), NumeralStyle.WESTERN))
        assertEquals("٢٧٫٣٪", MoneyFormat.formatPercent(BigDecimal("27.27"), NumeralStyle.ARABIC_INDIC))
    }

    @Test
    fun `plain integers group too`() {
        assertEquals("2,320", MoneyFormat.formatInteger(2_320, NumeralStyle.WESTERN))
        assertEquals("٢٬٣٢٠", MoneyFormat.formatInteger(2_320, NumeralStyle.ARABIC_INDIC))
        assertEquals("14", MoneyFormat.formatInteger(14, NumeralStyle.WESTERN))
    }

    @Test
    fun `a phone number is isolated so it cannot reverse inside Arabic prose`() {
        // Without the isolate, a Latin-digit phone number embedded in an Arabic
        // sentence renders with its parts in the wrong visual order — the
        // characters are right and the number a client dials is wrong.
        val isolated = MoneyFormat.ltrIsolate("+962790730903")
        assertEquals(MoneyFormat.ISOLATE_START, isolated.first())
        assertEquals(MoneyFormat.ISOLATE_END, isolated.last())
        assertTrue(isolated.contains("+962790730903"))
    }
}
