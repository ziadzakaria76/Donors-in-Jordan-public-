package com.gs3.marketingops.domain.sla

import com.gs3.marketingops.domain.funnel.Track
import java.time.Duration
import java.time.Instant
import java.time.LocalTime
import java.time.ZoneId

/** The five promises the team makes, and the app holds them to. */
enum class SlaRule(val appliesToExternalTrackOnly: Boolean = false) {
    /** 15 minutes, during business hours. */
    FIRST_RESPONSE,

    /** 48 hours after a viewing. */
    VIEWING_FOLLOW_UP,

    /** 24 hours from the request. */
    WRITTEN_OFFER,

    /**
     * A status update to an external-track client at least every 10 days,
     * whether or not anything has changed. Silence is what loses a buyer who is
     * four time zones away and cannot simply drop in.
     */
    EXTERNAL_STATUS_UPDATE(appliesToExternalTrackOnly = true),
    ;
}

enum class SlaState { MET, DUE, APPROACHING, BREACHED }

data class SlaDeadline(
    val rule: SlaRule,
    val dueAt: Instant,
    val state: SlaState,
) {
    fun stateAt(now: Instant, approachingWindow: Duration = Duration.ofMinutes(5)): SlaState = when {
        now >= dueAt -> SlaState.BREACHED
        Duration.between(now, dueAt) <= approachingWindow -> SlaState.APPROACHING
        else -> SlaState.DUE
    }
}

object SlaEngine {

    val FIRST_RESPONSE_WINDOW: Duration = Duration.ofMinutes(15)
    val VIEWING_FOLLOW_UP_WINDOW: Duration = Duration.ofHours(48)
    val WRITTEN_OFFER_WINDOW: Duration = Duration.ofHours(24)
    val EXTERNAL_UPDATE_INTERVAL: Duration = Duration.ofDays(10)

    /**
     * When the first response is due.
     *
     * Inside business hours it is fifteen minutes of working time. Outside them
     * the fifteen-minute clock does not apply at all — the promise becomes a
     * human reply by the next business morning, which is a different and softer
     * commitment, and conflating the two would either flag every overnight
     * enquiry as breached or let a 09:05 enquiry sit until ten.
     */
    fun firstResponseDeadline(enquiredAt: Instant, hours: BusinessHours): SlaDeadline {
        val dueAt = if (hours.isWithinBusinessHours(enquiredAt)) {
            hours.addWorkingTime(enquiredAt, FIRST_RESPONSE_WINDOW)
        } else {
            hours.nextReplyDeadline(enquiredAt)
        }
        return SlaDeadline(SlaRule.FIRST_RESPONSE, dueAt, SlaState.DUE)
    }

    /** Elapsed time, not working time: two days is two days to the person waiting. */
    fun viewingFollowUpDeadline(viewedAt: Instant): SlaDeadline =
        SlaDeadline(SlaRule.VIEWING_FOLLOW_UP, viewedAt.plus(VIEWING_FOLLOW_UP_WINDOW), SlaState.DUE)

    fun writtenOfferDeadline(requestedAt: Instant): SlaDeadline =
        SlaDeadline(SlaRule.WRITTEN_OFFER, requestedAt.plus(WRITTEN_OFFER_WINDOW), SlaState.DUE)

    /** Only the external track gets this one; a local buyer can just be phoned. */
    fun externalStatusUpdateDeadline(lastContactedAt: Instant, track: Track): SlaDeadline? {
        if (!track.isExternal) return null
        return SlaDeadline(
            SlaRule.EXTERNAL_STATUS_UPDATE,
            lastContactedAt.plus(EXTERNAL_UPDATE_INTERVAL),
            SlaState.DUE,
        )
    }

    /**
     * How long a lead may go quiet before it is stale — which is not the same
     * number for both tracks. An external buyer decides over 90 to 150 days
     * against 60 to 75 for a local one, so judging both on the local clock
     * would bury a live expatriate lead at thirty days.
     */
    fun staleAfter(track: Track): Duration =
        if (track.isExternal) Duration.ofDays(45) else Duration.ofDays(30)
}

/**
 * Schedules outreach at a civil hour in the *client's* zone.
 *
 * This is the one the brief warns about, and the reason it is a separate object
 * from the SLA clock. The nurture sequence says "+1 day", "+3 days", "+7 days";
 * what the client experiences is a message arriving at nine in the morning
 * where they are. Amman has not observed daylight saving since 2022, but
 * Toronto and London still do, so an expatriate lead's 09:00 drifts against
 * Amman twice a year. Storing an offset instead of a zone is what breaks every
 * North America reminder each March and November.
 */
object NurtureScheduler {

    val DEFAULT_LOCAL_HOUR: LocalTime = LocalTime.of(9, 0)

    /** The day offsets of the external-track nurture sequence. */
    val SEQUENCE_DAY_OFFSETS: List<Int> = listOf(0, 1, 3, 7, 14, 30)

    /**
     * [daysFromNow] days after [from], at [localTime] in the client's own zone.
     * Where a local time does not exist on that date — the spring-forward gap —
     * `java.time` moves forward to the first valid instant rather than throwing.
     */
    fun scheduleAt(
        from: Instant,
        daysFromNow: Int,
        clientZone: ZoneId,
        localTime: LocalTime = DEFAULT_LOCAL_HOUR,
    ): Instant {
        require(daysFromNow >= 0) { "Cannot schedule outreach $daysFromNow days ahead" }
        return from.atZone(clientZone)
            .toLocalDate()
            .plusDays(daysFromNow.toLong())
            .atTime(localTime)
            .atZone(clientZone)
            .toInstant()
    }

    /** The whole sequence for one lead, in the client's zone. */
    fun sequenceFor(
        enquiredAt: Instant,
        clientZone: ZoneId,
        localTime: LocalTime = DEFAULT_LOCAL_HOUR,
    ): List<Instant> = SEQUENCE_DAY_OFFSETS.map { scheduleAt(enquiredAt, it, clientZone, localTime) }
}
