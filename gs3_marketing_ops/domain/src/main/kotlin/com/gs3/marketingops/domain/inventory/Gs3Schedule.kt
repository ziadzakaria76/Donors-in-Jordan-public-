package com.gs3.marketingops.domain.inventory

import com.gs3.marketingops.domain.money.Jod

/**
 * The schedule of fourteen apartments at General Sherman 3, as the sales
 * brochure publishes it.
 *
 * Cross-checked against `website/assets/js/data.js` in this repository, which
 * the live site is built from: every internal area, external area and price
 * agrees across both. Two independent sources for the same fourteen units is
 * the reason this can be seeded with confidence rather than typed once and
 * hoped over.
 *
 * The Arabic here is the brochure's own wording, carried across rather than
 * re-translated.
 */
object Gs3Schedule {

    val apartments: List<Apartment> = listOf(
        Apartment(1, "South-west, ground floor", "الجنوبية الغربية — الطابق الأرضي", 235, 170, Jod.ofDinars(151_000), PriorityClass.D),
        Apartment(2, "North-east, ground floor", "الشمالية الشرقية — الطابق الأرضي", 193, 120, Jod.ofDinars(129_000), PriorityClass.D),
        Apartment(3, "South, ground floor", "الجنوبية — الطابق الأرضي", 151, 30, Jod.ofDinars(107_000), PriorityClass.B),
        Apartment(4, "East, ground floor", "الشرقية — الطابق الأرضي", 152, 0, Jod.ofDinars(98_000), PriorityClass.B),
        Apartment(5, "North, ground floor", "الشمالية — الطابق الأرضي", 153, 70, Jod.ofDinars(115_000), PriorityClass.D),
        Apartment(6, "First floor (south)", "الطابق الأول (الجنوبية)", 151, 0, Jod.ofDinars(90_000), PriorityClass.A),
        Apartment(7, "First floor (east)", "الطابق الأول (الشرقية)", 152, 0, Jod.ofDinars(90_000), PriorityClass.A),
        Apartment(8, "First floor (north)", "الطابق الأول (الشمالية)", 153, 0, Jod.ofDinars(92_000), PriorityClass.B),
        Apartment(9, "Second floor (south)", "الطابق الثاني (الجنوبية)", 151, 0, Jod.ofDinars(90_000), PriorityClass.A),
        Apartment(10, "Second floor (east)", "الطابق الثاني (الشرقية)", 152, 0, Jod.ofDinars(90_000), PriorityClass.A),
        Apartment(11, "Second floor (north)", "الطابق الثاني (الشمالية)", 153, 0, Jod.ofDinars(92_000), PriorityClass.B),
        Apartment(12, "Third floor with roof (south)", "الطابق الثالث مع روف (الجنوبية)", 186, 120, Jod.ofDinars(131_000), PriorityClass.C),
        Apartment(13, "Third floor (east)", "الطابق الثالث (الشرقية)", 152, 0, Jod.ofDinars(90_000), PriorityClass.A),
        Apartment(14, "Third floor with roof (north)", "الطابق الثالث مع روف (الشمالية)", 186, 110, Jod.ofDinars(131_000), PriorityClass.C),
    )

    val totals: InventoryTotals get() = apartments.totals()

    /** 11 of 14 units over twelve months, of which 3 come from the external track (A6). */
    const val ANNUAL_UNIT_TARGET: Int = 11
    const val ANNUAL_EXTERNAL_TRACK_TARGET: Int = 3

    /** Share of sales the external track must carry, and the referral floor. */
    val externalTrackShareTarget: java.math.BigDecimal = java.math.BigDecimal("0.27")
    val referralShareTarget: java.math.BigDecimal = java.math.BigDecimal("0.20")
}
