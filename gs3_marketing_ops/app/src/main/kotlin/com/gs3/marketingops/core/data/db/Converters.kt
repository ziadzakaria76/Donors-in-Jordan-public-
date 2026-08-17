package com.gs3.marketingops.core.data.db

import androidx.room.TypeConverter
import java.time.Instant

/**
 * The only place a stored value changes shape.
 *
 * Two rules are enforced here rather than remembered at each call site:
 *
 * **Money is stored as whole fils, never as a decimal.** `Jod` already holds
 * fils internally for exactly this reason — a dinar is a thousand fils, so an
 * integer count of them is exact, and a twelve-month split adds back to the
 * annual figure to the fils instead of drifting. Storing a `REAL` would undo
 * that at the database boundary, which is the one place nobody would look.
 *
 * **Time is stored as epoch milliseconds, which are UTC by construction.** A
 * lead in Toronto and a lead in Amman are the same code path; the zone enters
 * only when something is rendered, through `DateFormat`. Storing a local time —
 * or worse, a fixed offset — breaks every North America reminder twice a year,
 * and breaks it silently, because a reminder that arrives an hour late looks
 * exactly like a reminder that arrived.
 */
object Converters {

    @TypeConverter
    fun instantToEpochMilli(instant: Instant?): Long? = instant?.toEpochMilli()

    @TypeConverter
    fun epochMilliToInstant(epochMilli: Long?): Instant? =
        epochMilli?.let(Instant::ofEpochMilli)
}
