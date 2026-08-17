package com.gs3.marketingops.domain.money

import java.math.RoundingMode

/** Which digits the team reads: 0-9 or ٠-٩. A Settings toggle, defaulting to Western. */
enum class NumeralStyle { WESTERN, ARABIC_INDIC }

/** The two languages the app is authored in. Arabic is not a translation of English. */
enum class AppLanguage { ARABIC, ENGLISH }

/**
 * Renders money and plain numbers in the reader's digits.
 *
 * Kept in the domain, with no Android dependency, because it is pure string
 * work and this is where it can be tested exhaustively. The Arabic form uses
 * the Arabic thousands separator (U+066C) rather than a comma — a comma between
 * Arabic-Indic digits reads as a decimal point to an Arabic reader.
 */
object MoneyFormat {

    private const val ARABIC_ZERO = '٠'
    private const val ARABIC_THOUSANDS = '٬'
    private const val ARABIC_DECIMAL = '٫'

    /** Wraps text in Unicode isolates so it cannot reverse inside an Arabic sentence. */
    const val ISOLATE_START = '⁦'
    const val ISOLATE_END = '⁩'

    /**
     * A phone number, URL, email or campaign code sitting inside Arabic prose
     * will visually reverse without this. The brief calls it out because it is
     * the single most common way a bilingual app ships a wrong phone number
     * that is technically the right characters.
     */
    fun ltrIsolate(text: String): String = "$ISOLATE_START$text$ISOLATE_END"

    fun formatMoney(
        amount: Jod,
        language: AppLanguage,
        numerals: NumeralStyle = NumeralStyle.WESTERN,
        decimals: Int = 0,
    ): String {
        val currency = if (language == AppLanguage.ARABIC) "د.أ" else "JOD"
        return "${formatDecimal(amount, numerals, decimals)} $currency"
    }

    fun formatDecimal(amount: Jod, numerals: NumeralStyle, decimals: Int): String {
        require(decimals in 0..3) { "The dinar has three decimal places, not $decimals" }
        val rounded = amount.dinars.setScale(decimals, RoundingMode.HALF_UP)
        val text = rounded.abs().toPlainString()
        val whole = text.substringBefore('.')
        val fraction = text.substringAfter('.', "")

        val grouped = groupThousands(whole, numerals)
        val body = if (fraction.isEmpty()) grouped else {
            val point = if (numerals == NumeralStyle.ARABIC_INDIC) ARABIC_DECIMAL else '.'
            "$grouped$point${toDigits(fraction, numerals)}"
        }
        return if (rounded.signum() < 0) "-$body" else body
    }

    fun formatInteger(value: Long, numerals: NumeralStyle): String {
        val grouped = groupThousands(kotlin.math.abs(value).toString(), numerals)
        return if (value < 0) "-$grouped" else grouped
    }

    /** A percentage to one decimal place, e.g. `27.3%` / `٢٧٫٣٪`. */
    fun formatPercent(value: java.math.BigDecimal, numerals: NumeralStyle): String {
        val rounded = value.setScale(1, RoundingMode.HALF_UP).toPlainString()
        val sign = if (numerals == NumeralStyle.ARABIC_INDIC) "٪" else "%"
        val body = rounded.replace(".", if (numerals == NumeralStyle.ARABIC_INDIC) ARABIC_DECIMAL.toString() else ".")
        return "${toDigits(body, numerals)}$sign"
    }

    private fun groupThousands(digits: String, numerals: NumeralStyle): String {
        val separator = if (numerals == NumeralStyle.ARABIC_INDIC) ARABIC_THOUSANDS else ','
        val grouped = digits.reversed().chunked(3).joinToString(separator.toString()).reversed()
        return toDigits(grouped, numerals)
    }

    private fun toDigits(text: String, numerals: NumeralStyle): String =
        if (numerals == NumeralStyle.WESTERN) text
        else text.map { character ->
            if (character in '0'..'9') ARABIC_ZERO + (character - '0') else character
        }.joinToString("")
}
