package com.gs3.marketingops.domain.inventory

import com.gs3.marketingops.domain.money.Jod
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/**
 * The seed-data assertions the brief demands.
 *
 * These are not ceremony. The schedule is typed in by hand from a brochure, and
 * a single transposed digit in a price would flow into the dashboard's value
 * sold, the gross development value quoted to clients, and every price-per-m²
 * comparison — silently, and in the direction of a number that still looks
 * plausible. The totals are the checksum.
 */
class Gs3ScheduleTest {

    @Test
    fun `the schedule holds fourteen apartments`() {
        assertEquals(14, Gs3Schedule.apartments.size)
    }

    @Test
    fun `unit numbers are one to fourteen with no gaps or repeats`() {
        assertEquals((1..14).toList(), Gs3Schedule.apartments.map { it.number }.sorted())
    }

    @Test
    fun `totals match the brochure`() {
        val totals = Gs3Schedule.totals
        assertEquals(14, totals.unitCount)
        assertEquals(2_320, totals.internalArea)
        assertEquals(620, totals.externalArea)
        assertEquals(Jod.ofDinars(1_496_000), totals.grossDevelopmentValue)
    }

    @Test
    fun `weighted average price per square metre is 645 dinars`() {
        // 1,496,000 / 2,320 = 644.828 JOD, which the brief rounds to 645.
        val weighted = Gs3Schedule.totals.weightedPricePerSquareMetre
        assertEquals(644_828L, weighted.fils)
        assertEquals(645L, weighted.dinars.setScale(0, java.math.RoundingMode.HALF_UP).toLong())
    }

    @Test
    fun `price per square metre is computed per unit, not assumed uniform`() {
        // Units 3 and 6 are both 151 m2 but 17,000 JOD apart — the ground floor's
        // thirty metres of terrace. A schedule derived from a formula would miss this.
        val unit3 = Gs3Schedule.apartments.first { it.number == 3 }
        val unit6 = Gs3Schedule.apartments.first { it.number == 6 }
        assertEquals(unit3.internalArea, unit6.internalArea)
        assertTrue(unit3.pricePerSquareMetre > unit6.pricePerSquareMetre)
        assertEquals(708_609L, unit3.pricePerSquareMetre.fils)
    }

    @Test
    fun `class A units are the five priced at ninety thousand`() {
        val classA = Gs3Schedule.apartments.filter { it.priorityClass == PriorityClass.A }
        assertEquals(listOf(6, 7, 9, 10, 13), classA.map { it.number })
        assertTrue(classA.all { it.listPrice == Jod.ofDinars(90_000) })
        assertTrue(classA.none { it.priorityClass.allowsCashDiscount })
    }

    @Test
    fun `only six units have external area, totalling 620 square metres`() {
        val withOutdoor = Gs3Schedule.apartments.filter { it.hasExternalArea }
        assertEquals(listOf(1, 2, 3, 5, 12, 14), withOutdoor.map { it.number })
        assertEquals(620, withOutdoor.sumOf { it.externalArea })
    }

    @Test
    fun `every apartment starts available`() {
        assertTrue(Gs3Schedule.apartments.all { it.status == UnitStatus.AVAILABLE })
        assertEquals(Jod.ZERO, Gs3Schedule.apartments.valueOf(UnitStatus.CONTRACTED))
    }

    @Test
    fun `value sold counts only contracted units`() {
        val withSales = Gs3Schedule.apartments.map { apartment ->
            if (apartment.number in listOf(6, 7)) apartment.copy(status = UnitStatus.CONTRACTED) else apartment
        }
        assertEquals(Jod.ofDinars(180_000), withSales.valueOf(UnitStatus.CONTRACTED))
        assertEquals(Jod.ofDinars(1_316_000), withSales.valueOf(UnitStatus.AVAILABLE))
    }

    @Test
    fun `the annual target is eleven units of which three are external`() {
        assertEquals(11, Gs3Schedule.ANNUAL_UNIT_TARGET)
        assertEquals(3, Gs3Schedule.ANNUAL_EXTERNAL_TRACK_TARGET)
        // 3 of 11 is 27.3%, which clears the >= 27% the strategy commits to.
        val share = java.math.BigDecimal(3).divide(java.math.BigDecimal(11), 4, java.math.RoundingMode.HALF_UP)
        assertTrue(share >= Gs3Schedule.externalTrackShareTarget)
    }

    @Test
    fun `an apartment cannot be built with impossible dimensions`() {
        val thrown = runCatching {
            Apartment(1, "nowhere", "لا مكان", 0, 0, Jod.ofDinars(1), PriorityClass.A)
        }.exceptionOrNull()
        assertTrue(thrown is IllegalArgumentException)
    }
}
