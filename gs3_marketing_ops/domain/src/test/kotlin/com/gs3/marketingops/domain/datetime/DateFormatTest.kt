package com.gs3.marketingops.domain.datetime

import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.NumeralStyle
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.DisplayName
import org.junit.jupiter.api.Test
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId

class DateFormatTest {

    private val amman = ZoneId.of("Asia/Amman")
    private val toronto = ZoneId.of("America/Toronto")

    @Test
    @DisplayName("English dates read as a Jordanian would write them")
    fun englishDate() {
        val date = LocalDate.of(2026, 8, 15)
        assertEquals("15 August 2026", DateFormat.formatDate(date, AppLanguage.ENGLISH))
    }

    @Test
    @DisplayName("Arabic months are Levantine, not the Egyptian and Gulf set")
    fun arabicMonthsAreLevantine() {
        val january = LocalDate.of(2026, 1, 9)
        val formatted = DateFormat.formatDate(january, AppLanguage.ARABIC)

        // The point of the test: «كانون الثاني», never «يناير». Taking these
        // from the JVM's own ar locale would give the wrong one, and would give
        // a different wrong one on Android than on the JVM.
        assertTrue(formatted.contains("كانون الثاني"), formatted)
        assertFalse(formatted.contains("يناير"), formatted)
    }

    @Test
    @DisplayName("Arabic-Indic digits are used for day and year when selected")
    fun arabicIndicDigits() {
        val date = LocalDate.of(2026, 8, 15)
        assertEquals(
            "١٥ آب ٢٠٢٦",
            DateFormat.formatDate(date, AppLanguage.ARABIC, NumeralStyle.ARABIC_INDIC),
        )
    }

    @Test
    @DisplayName("A year is never grouped — 2026, not 2,026")
    fun yearIsNotGrouped() {
        val date = LocalDate.of(2026, 3, 1)
        assertTrue(DateFormat.formatDate(date, AppLanguage.ENGLISH).endsWith("2026"))
        assertFalse(DateFormat.formatDate(date, AppLanguage.ENGLISH).contains(","))

        val arabic = DateFormat.formatDate(date, AppLanguage.ARABIC, NumeralStyle.ARABIC_INDIC)
        assertTrue(arabic.endsWith("٢٠٢٦"), arabic)
        assertFalse(arabic.contains("٬"), arabic)
    }

    @Test
    @DisplayName("The week is named from Saturday, the first working day here")
    fun weekdayNames() {
        // 15 August 2026 is a Saturday — the first day of the working week
        // under D-5, which the company publishes on its own site.
        val saturday = LocalDate.of(2026, 8, 15)
        assertEquals(java.time.DayOfWeek.SATURDAY, saturday.dayOfWeek)

        assertTrue(
            DateFormat.formatDateWithWeekday(saturday, AppLanguage.ARABIC).startsWith("السبت"),
        )
        assertTrue(
            DateFormat.formatDateWithWeekday(saturday, AppLanguage.ENGLISH).startsWith("Saturday"),
        )
    }

    @Test
    @DisplayName("Arabic uses the Arabic comma between weekday and date")
    fun arabicSeparator() {
        val date = LocalDate.of(2026, 8, 15)
        val arabic = DateFormat.formatDateWithWeekday(date, AppLanguage.ARABIC)
        assertTrue(arabic.contains("، "), arabic)
    }

    @Test
    @DisplayName("Times render in the given zone, not the machine's")
    fun timeRendersInTheGivenZone() {
        // 09:00 in Amman on a summer day. Amman has been UTC+3 with no daylight
        // saving since 2022, so this is 06:00 UTC year-round.
        val instant = Instant.parse("2026-08-15T06:00:00Z")

        assertTrue(DateFormat.formatTime(instant, amman).contains("09:00"))
        // Toronto is UTC-4 in August, so the same instant is 02:00 there.
        assertTrue(DateFormat.formatTime(instant, toronto).contains("02:00"))
    }

    @Test
    @DisplayName("A clock time is isolated so it cannot reverse in Arabic prose")
    fun timeIsIsolated() {
        val instant = Instant.parse("2026-08-15T06:00:00Z")
        val formatted = DateFormat.formatTime(instant, amman)

        assertTrue(formatted.startsWith("⁦"), "missing LTR isolate start")
        assertTrue(formatted.endsWith("⁩"), "missing isolate end")
    }

    @Test
    @DisplayName("The same instant is a different calendar day either side of the world")
    fun sameInstantDifferentDay() {
        // 01:30 UTC. Still the previous evening in Toronto, already morning in
        // Amman — the case that makes a stored local date wrong for one of the
        // two tracks.
        val instant = Instant.parse("2026-08-15T01:30:00Z")

        val inAmman = DateFormat.formatDateTime(instant, amman, AppLanguage.ENGLISH)
        val inToronto = DateFormat.formatDateTime(instant, toronto, AppLanguage.ENGLISH)

        assertTrue(inAmman.startsWith("15 August 2026"), inAmman)
        assertTrue(inToronto.startsWith("14 August 2026"), inToronto)
    }

    @Test
    @DisplayName("Times are 24-hour in both languages, so a deadline cannot be ambiguous")
    fun timesAre24Hour() {
        val evening = Instant.parse("2026-08-15T16:15:00Z") // 19:15 in Amman
        assertTrue(DateFormat.formatTime(evening, amman).contains("19:15"))
    }

    @Test
    @DisplayName("Hijri is offered alongside the Gregorian date, never instead of it")
    fun hijriAccompaniesGregorian() {
        val date = LocalDate.of(2026, 8, 15)

        val without = DateFormat.formatDate(date, AppLanguage.ARABIC, NumeralStyle.WESTERN, false)
        val with = DateFormat.formatDate(date, AppLanguage.ARABIC, NumeralStyle.WESTERN, true)

        assertEquals("15 آب 2026", without)
        // The Gregorian date survives intact, with the Hijri date after it.
        assertTrue(with.startsWith("15 آب 2026 ("), with)
        assertTrue(with.endsWith(")"), with)
    }

    @Test
    @DisplayName("The Hijri date names a real month and follows the Gregorian year")
    fun hijriIsPlausible() {
        val hijri = DateFormat.formatHijri(LocalDate.of(2026, 8, 15))
        val parts = hijri.split(" ")

        // 2026 CE falls in 1447-1448 AH.
        val year = parts.last().toInt()
        assertTrue(year in 1447..1448, hijri)
        assertTrue(hijri.first().isDigit(), hijri)
    }

    @Test
    @DisplayName("Hijri renders in Arabic-Indic digits when those are selected")
    fun hijriInArabicIndicDigits() {
        val hijri = DateFormat.formatHijri(LocalDate.of(2026, 8, 15), NumeralStyle.ARABIC_INDIC)
        assertFalse(hijri.any { it in '0'..'9' }, hijri)
        assertTrue(hijri.any { it in '٠'..'٩' }, hijri)
    }

    @Test
    @DisplayName("Every Gregorian month has a distinct name in both languages")
    fun everyMonthIsNamed() {
        val arabic = (1..12).map {
            DateFormat.formatDate(LocalDate.of(2026, it, 1), AppLanguage.ARABIC)
        }
        val english = (1..12).map {
            DateFormat.formatDate(LocalDate.of(2026, it, 1), AppLanguage.ENGLISH)
        }

        assertEquals(12, arabic.toSet().size)
        assertEquals(12, english.toSet().size)
    }

    @Test
    @DisplayName("Every Hijri month name is reachable across a full Hijri year")
    fun everyHijriMonthIsNamed() {
        // A Hijri year is ~354 days, so 13 Gregorian months of samples covers
        // all twelve of them and catches an off-by-one in the month lookup.
        val names = (0L until 400L)
            .map { DateFormat.formatHijri(LocalDate.of(2026, 1, 1).plusDays(it)) }
            .map { it.dropWhile { character -> character.isDigit() }.trim().dropLastWhile { character -> character.isDigit() }.trim() }
            .toSet()

        assertEquals(12, names.size, names.toString())
    }

    @Test
    @DisplayName("Every weekday is named in both languages")
    fun everyWeekdayIsNamed() {
        val week = (0L until 7L).map { LocalDate.of(2026, 8, 15).plusDays(it) }

        assertEquals(7, week.map { DateFormat.formatDateWithWeekday(it, AppLanguage.ARABIC) }.toSet().size)
        assertEquals(7, week.map { DateFormat.formatDateWithWeekday(it, AppLanguage.ENGLISH) }.toSet().size)
    }
}
