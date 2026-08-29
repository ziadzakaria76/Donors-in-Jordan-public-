package com.gs3.marketingops.inventory.data

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.gs3.marketingops.domain.inventory.Apartment
import com.gs3.marketingops.domain.inventory.PriorityClass
import com.gs3.marketingops.domain.inventory.UnitStatus
import com.gs3.marketingops.domain.money.Jod

/**
 * One of the fourteen apartments, as stored.
 *
 * The list price, areas and position come straight from [Apartment] and are
 * seeded from `Gs3Schedule`, which is itself cross-checked against the live
 * website's data file. They are *not* editable in the app: a price schedule
 * that can drift away from the brochure while the website still shows the old
 * one is how a client gets quoted two different numbers in the same week.
 *
 * What the app *does* own is the right-hand half of this table — status, the
 * agreed price and discount, and the justification. Those are per-negotiation
 * and belong to the team.
 *
 * Money is `Long` fils throughout (see `Converters`). Enums are stored by
 * **name**, never ordinal: an ordinal silently changes meaning the day someone
 * inserts a value into the middle of an enum, and here that would silently
 * reclassify a unit's priority class or its sale status.
 */
@Entity(tableName = "units")
data class UnitEntity(
    @PrimaryKey val number: Int,
    val positionEn: String,
    val positionAr: String,
    val internalArea: Int,
    val externalArea: Int,
    val listPriceFils: Long,
    val priorityClass: String,
    val status: String,

    /**
     * The price actually agreed, when one has been.
     *
     * Null until a negotiation closes — deliberately distinct from "equal to
     * the list price", because the two mean different things in a report about
     * how much discounting the team is really doing.
     *
     * A4: these are stored, and the app lock defaults to on because of it.
     */
    val agreedPriceFils: Long? = null,
    val discountJustification: String? = null,
) {
    fun toDomain(): Apartment = Apartment(
        number = number,
        positionEn = positionEn,
        positionAr = positionAr,
        internalArea = internalArea,
        externalArea = externalArea,
        listPrice = Jod.ofFils(listPriceFils),
        priorityClass = PriorityClass.valueOf(priorityClass),
        status = UnitStatus.valueOf(status),
    )

    internal companion object {
        fun fromDomain(apartment: Apartment): UnitEntity = UnitEntity(
            number = apartment.number,
            positionEn = apartment.positionEn,
            positionAr = apartment.positionAr,
            internalArea = apartment.internalArea,
            externalArea = apartment.externalArea,
            listPriceFils = apartment.listPrice.fils,
            priorityClass = apartment.priorityClass.name,
            status = apartment.status.name,
        )
    }
}
