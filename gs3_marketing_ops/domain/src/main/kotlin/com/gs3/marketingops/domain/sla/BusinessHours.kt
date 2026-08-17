package com.gs3.marketingops.domain.sla

import java.time.DayOfWeek
import java.time.Duration
import java.time.Instant
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime

/**
 * The company's working week, in the company's own zone.
 *
 * Note the default is Saturday to Thursday, not the Sunday-to-Thursday that the
 * discovery interview proposed: the company publishes «السبت – الخميس، ٩:٠٠ صباحاً – ٦:٠٠ مساءً»
 * on its own website, and its own site is better evidence than a default.
 * Recorded as DECISIONS.md → D-5, and editable in Settings either way. It is
 * not cosmetic — it decides whether a Saturday enquiry starts a 15-minute clock
 * or waits until Sunday morning.
 *
 * Amman is UTC+3 the year round, with no daylight saving since 2022. Even so
 * this holds a [ZoneId] rather than an offset, because an offset is a fact
 * about one instant and a zone is a fact about a place.
 */
data class BusinessHours(
    val zone: ZoneId = ZoneId.of("Asia/Amman"),
    val workingDays: Set<DayOfWeek> = setOf(
        DayOfWeek.SATURDAY,
        DayOfWeek.SUNDAY,
        DayOfWeek.MONDAY,
        DayOfWeek.TUESDAY,
        DayOfWeek.WEDNESDAY,
        DayOfWeek.THURSDAY,
    ),
    val opensAt: LocalTime = LocalTime.of(9, 0),
    val closesAt: LocalTime = LocalTime.of(18, 0),
    /** When an out-of-hours enquiry must have a human reply by. */
    val outOfHoursReplyBy: LocalTime = LocalTime.of(10, 0),
) {
    init {
        require(workingDays.isNotEmpty()) { "A working week with no working days would never fire an SLA" }
        require(opensAt < closesAt) { "Opening time $opensAt is not before closing time $closesAt" }
    }

    fun isWithinBusinessHours(instant: Instant): Boolean {
        val local = instant.atZone(zone)
        return local.dayOfWeek in workingDays &&
            !local.toLocalTime().isBefore(opensAt) &&
            local.toLocalTime().isBefore(closesAt)
    }

    /**
     * The moment a human reply is due for an enquiry that arrived out of hours.
     *
     * An enquiry before opening on a working day is due that same morning, not
     * the next one — waiting a whole extra day because someone wrote at 07:00
     * would be the letter of the rule defeating its point. The reply time is
     * never earlier than opening, so setting a 10:00 reply against an 11:00
     * opening cannot produce a deadline nobody is at work for.
     */
    fun nextReplyDeadline(from: Instant): Instant {
        val local = from.atZone(zone)
        val replyTime = maxOf(outOfHoursReplyBy, opensAt)

        val sameDayDeadline = local.toLocalDate().atTime(replyTime).atZone(zone)
        if (local.dayOfWeek in workingDays && local.toLocalTime() < opensAt) {
            return sameDayDeadline.toInstant()
        }

        var day = local.toLocalDate().plusDays(1)
        while (day.dayOfWeek !in workingDays) {
            day = day.plusDays(1)
        }
        return day.atTime(replyTime).atZone(zone).toInstant()
    }

    /**
     * Adds working time to an instant, skipping evenings and weekends.
     *
     * A 15-minute clock started at 17:55 must not expire at 18:10 when the
     * office shut at 18:00; the remaining ten minutes belong to the next
     * working morning.
     */
    fun addWorkingTime(from: Instant, duration: Duration): Instant {
        require(!duration.isNegative) { "Cannot add negative working time" }
        var cursor = advanceToOpen(from.atZone(zone))
        var remaining = duration

        while (true) {
            val closing = cursor.toLocalDate().atTime(closesAt).atZone(zone)
            val availableToday = Duration.between(cursor, closing)
            if (remaining <= availableToday) {
                return cursor.plus(remaining).toInstant()
            }
            remaining -= availableToday
            cursor = advanceToOpen(closing.plusSeconds(1))
        }
    }

    /** Moves to the next moment the office is open, or stays put if it already is. */
    private fun advanceToOpen(from: ZonedDateTime): ZonedDateTime {
        var cursor = from
        while (true) {
            if (cursor.dayOfWeek !in workingDays) {
                cursor = cursor.toLocalDate().plusDays(1).atTime(opensAt).atZone(zone)
                continue
            }
            val time = cursor.toLocalTime()
            if (time < opensAt) return cursor.toLocalDate().atTime(opensAt).atZone(zone)
            if (time >= closesAt) {
                cursor = cursor.toLocalDate().plusDays(1).atTime(opensAt).atZone(zone)
                continue
            }
            return cursor
        }
    }
}
