package com.gs3.marketingops.domain.datetime

import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.MoneyFormat
import com.gs3.marketingops.domain.money.NumeralStyle
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.chrono.HijrahDate
import java.time.temporal.ChronoField

/**
 * Dates, in the reader's language, calendar and digits.
 *
 * This lives in `:domain` next to [MoneyFormat] for the same reason that does:
 * it is pure string work over plain data, so it is tested exhaustively at JVM
 * speed rather than on a device. The Android layer decides *when* to call it and
 * with which settings; it contributes no formatting of its own.
 *
 * Everything takes an explicit [ZoneId]. Timestamps are stored in UTC
 * throughout, and a lead in Toronto and a lead in Amman are the same code path
 * — so the only place a time zone is allowed to enter is here, as an argument.
 */
object DateFormat {

    /**
     * Levantine month names, written out rather than taken from the JVM's
     * locale data.
     *
     * `Locale("ar")` yields «يناير, فبراير, مارس» — the Egyptian and Gulf
     * names. Jordan writes «كانون الثاني, شباط, آذار», and the two sets are not
     * interchangeable to a reader: a Jordanian client seeing «يناير» on a
     * payment schedule reads it as a foreign document. Worse, the JVM's answer
     * is not the same as Android's for the same locale tag, so the date on the
     * screen and the date in an exported PDF could disagree while both were
     * "correct".
     */
    private val ARABIC_MONTHS = listOf(
        "كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران",
        "تموز", "آب", "أيلول", "تشرين الأول", "تشرين الثاني", "كانون الأول",
    )

    private val ENGLISH_MONTHS = listOf(
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
    )

    /** Hijri months, likewise explicit. */
    private val HIJRI_MONTHS = listOf(
        "محرم", "صفر", "ربيع الأول", "ربيع الآخر", "جمادى الأولى", "جمادى الآخرة",
        "رجب", "شعبان", "رمضان", "شوال", "ذو القعدة", "ذو الحجة",
    )

    /**
     * Weekday names. Saturday first, because the working week here runs
     * Saturday to Thursday (DECISIONS.md → D-5 and B1) and a week that starts
     * on Monday puts the weekend in the middle of the row.
     */
    private val ARABIC_DAYS = mapOf(
        java.time.DayOfWeek.SATURDAY to "السبت",
        java.time.DayOfWeek.SUNDAY to "الأحد",
        java.time.DayOfWeek.MONDAY to "الاثنين",
        java.time.DayOfWeek.TUESDAY to "الثلاثاء",
        java.time.DayOfWeek.WEDNESDAY to "الأربعاء",
        java.time.DayOfWeek.THURSDAY to "الخميس",
        java.time.DayOfWeek.FRIDAY to "الجمعة",
    )

    private val ENGLISH_DAYS = mapOf(
        java.time.DayOfWeek.SATURDAY to "Saturday",
        java.time.DayOfWeek.SUNDAY to "Sunday",
        java.time.DayOfWeek.MONDAY to "Monday",
        java.time.DayOfWeek.TUESDAY to "Tuesday",
        java.time.DayOfWeek.WEDNESDAY to "Wednesday",
        java.time.DayOfWeek.THURSDAY to "Thursday",
        java.time.DayOfWeek.FRIDAY to "Friday",
    )

    /** `15 August 2026` / `١٥ آب ٢٠٢٦`. */
    fun formatDate(
        date: LocalDate,
        language: AppLanguage,
        numerals: NumeralStyle = NumeralStyle.WESTERN,
    ): String {
        val month = monthName(date.monthValue, language)
        val day = digits(date.dayOfMonth.toString(), numerals)
        // The year is never grouped: 2026 is a year, not two thousand and
        // twenty-six dinars, and `2,026` on a contract date looks like a typo.
        val year = digits(date.year.toString(), numerals)
        return "$day $month $year"
    }

    /** The same date with its weekday in front. */
    fun formatDateWithWeekday(
        date: LocalDate,
        language: AppLanguage,
        numerals: NumeralStyle = NumeralStyle.WESTERN,
    ): String {
        val days = if (language == AppLanguage.ARABIC) ARABIC_DAYS else ENGLISH_DAYS
        val separator = if (language == AppLanguage.ARABIC) "، " else ", "
        return "${days.getValue(date.dayOfWeek)}$separator${formatDate(date, language, numerals)}"
    }

    /**
     * A 24-hour clock time, `14:30` / `١٤:٣٠`.
     *
     * 24-hour in both languages on purpose. An SLA that reads "due 7:15" is
     * ambiguous by twelve hours, and the one thing a response deadline cannot
     * be is ambiguous.
     */
    fun formatTime(
        instant: Instant,
        zone: ZoneId,
        numerals: NumeralStyle = NumeralStyle.WESTERN,
    ): String {
        val local = instant.atZone(zone)
        val hour = digits(local.hour.toString().padStart(2, '0'), numerals)
        val minute = digits(local.minute.toString().padStart(2, '0'), numerals)
        // Wrapped so a clock time cannot visually reverse to ٣٠:١٤ inside an
        // Arabic sentence. Same reasoning as MoneyFormat.ltrIsolate.
        return MoneyFormat.ltrIsolate("$hour:$minute")
    }

    /** Date and time together, rendered in the given zone. */
    fun formatDateTime(
        instant: Instant,
        zone: ZoneId,
        language: AppLanguage,
        numerals: NumeralStyle = NumeralStyle.WESTERN,
    ): String {
        val date = formatDate(instant.atZone(zone).toLocalDate(), language, numerals)
        return "$date — ${formatTime(instant, zone, numerals)}"
    }

    /**
     * The Hijri date, e.g. `٢ ربيع الأول ١٤٤٨`.
     *
     * Offered as a toggle rather than shown always (DECISIONS.md → C4's
     * neighbour, `settings_show_hijri`). It is always the *companion* to the
     * Gregorian date and never a replacement for it: contracts, payment
     * schedules and government deadlines in Jordan are Gregorian, so a screen
     * showing only a Hijri date would be a screen nobody can act on.
     */
    fun formatHijri(
        date: LocalDate,
        numerals: NumeralStyle = NumeralStyle.WESTERN,
    ): String {
        val hijri = HijrahDate.from(date)
        val day = digits(hijri.get(ChronoField.DAY_OF_MONTH).toString(), numerals)
        val month = HIJRI_MONTHS[hijri.get(ChronoField.MONTH_OF_YEAR) - 1]
        val year = digits(hijri.get(ChronoField.YEAR).toString(), numerals)
        return "$day $month $year"
    }

    /** Gregorian, with the Hijri date in brackets after it when asked for. */
    fun formatDate(
        date: LocalDate,
        language: AppLanguage,
        numerals: NumeralStyle,
        showHijri: Boolean,
    ): String {
        val gregorian = formatDate(date, language, numerals)
        return if (!showHijri) gregorian else "$gregorian (${formatHijri(date, numerals)})"
    }

    private fun monthName(monthValue: Int, language: AppLanguage): String =
        if (language == AppLanguage.ARABIC) ARABIC_MONTHS[monthValue - 1]
        else ENGLISH_MONTHS[monthValue - 1]

    /** Digit substitution only — no grouping. Delegates the mapping to one place. */
    private fun digits(text: String, numerals: NumeralStyle): String =
        if (numerals == NumeralStyle.WESTERN) text
        else text.map { if (it in '0'..'9') '٠' + (it - '0') else it }.joinToString("")
}
