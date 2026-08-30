package com.gs3.marketingops.screenshot

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onFirst
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import com.gs3.marketingops.core.locale.Gs3Localized
import com.gs3.marketingops.domain.inventory.Apartment
import com.gs3.marketingops.domain.inventory.Gs3Schedule
import com.gs3.marketingops.domain.inventory.UnitStatus
import com.gs3.marketingops.domain.inventory.totals
import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.NumeralStyle
import com.gs3.marketingops.inventory.ui.InventoryList
import com.gs3.marketingops.settings.data.AppSettings
import com.gs3.marketingops.settings.data.ThemeMode
import com.gs3.marketingops.ui.theme.Gs3Theme
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/**
 * The inventory screen in both languages, and the assertions that a screenshot
 * cannot make for itself.
 *
 * Rendering `InventoryList` rather than `InventoryScreen` is deliberate: the
 * screen resolves its own `hiltViewModel`, which would drag an injection graph
 * and a real database into a test whose subject is layout and wording. The
 * list takes the units it draws, so the fixture is the schedule itself —
 * exactly the data the app seeds.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [ROBOLECTRIC_SDK], qualifiers = "w411dp-h891dp-xhdpi")
class InventoryScreenshotTest {

    @get:Rule
    val composeRule = createComposeRule()

    private val schedule = Gs3Schedule.apartments

    private fun settings(
        language: AppLanguage,
        numerals: NumeralStyle = NumeralStyle.WESTERN,
    ) = AppSettings(
        language = language,
        numerals = numerals,
        showHijri = false,
        theme = ThemeMode.LIGHT,
    )

    private fun capture(name: String) {
        val file = File("$SCREENSHOT_DIR/$name.png")
        composeRule.onRoot().captureRoboImage(file.path)

        // The assertion that does not depend on build configuration staying
        // put: `captureRoboImage` is a silent no-op outside record mode, and
        // that shipped once already — four green tests and no PNG anywhere.
        assertTrue("no screenshot written to ${file.path}", file.exists())
        assertTrue("screenshot ${file.path} is suspiciously small", file.length() > 10_000)
    }

    @Test
    fun `inventory in Arabic`() {
        composeRule.setContent { Fixture(settings(AppLanguage.ARABIC), schedule) }
        capture("inventory_arabic")
    }

    @Test
    fun `inventory in English`() {
        composeRule.setContent { Fixture(settings(AppLanguage.ENGLISH), schedule) }
        capture("inventory_english")
    }

    @Test
    fun `inventory in Arabic with Arabic-Indic numerals`() {
        composeRule.setContent {
            Fixture(settings(AppLanguage.ARABIC, NumeralStyle.ARABIC_INDIC), schedule)
        }
        capture("inventory_arabic_indic")
    }

    /**
     * The behavioural assertions run against a **two-unit fixture**, not the
     * whole schedule, and that is not a shortcut.
     *
     * `LazyColumn` composes only what is on screen, so an assertion about unit
     * 11 on a 411dp phone fails for the honest reason that unit 11 has not been
     * composed — a green-or-red that depends on scroll position rather than on
     * the code. Two units, both visible, test the row itself; the screenshots
     * above cover the full fourteen.
     */
    private fun twoUnits() = listOf(
        schedule.first { it.hasExternalArea },
        schedule.first { !it.hasExternalArea },
    )

    @Composable
    private fun Fixture(settings: AppSettings, units: List<Apartment>) {
        Gs3Localized(language = settings.language) {
            Gs3Theme(darkTheme = false) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .background(MaterialTheme.colorScheme.background),
                ) {
                    InventoryList(units = units, settings = settings)
                }
            }
        }
    }

    /**
     * The position is data, not a string resource, so the language switch has
     * to pick the right half of the row. Getting it wrong shows «الطابق
     * الأرضي» to an English-speaking client and would fail nothing else here:
     * both strings are non-blank and both render.
     */
    @Test
    fun `an English reader gets the schedule's English wording`() {
        val units = twoUnits()
        composeRule.setContent { Fixture(settings(AppLanguage.ENGLISH), units) }

        composeRule.onAllNodesWithText(units.first().positionEn, substring = true)
            .onFirst().assertExists()
        composeRule.onAllNodesWithText(units.first().positionAr, substring = true)
            .assertCountEquals(0)
    }

    @Test
    fun `an Arabic reader gets the schedule's Arabic wording`() {
        val units = twoUnits()
        composeRule.setContent { Fixture(settings(AppLanguage.ARABIC), units) }

        composeRule.onAllNodesWithText(units.first().positionAr, substring = true)
            .onFirst().assertExists()
        composeRule.onAllNodesWithText(units.first().positionEn, substring = true)
            .assertCountEquals(0)
    }

    /**
     * Eight of the fourteen have no terrace or roof. "0 m²" reads as a
     * measurement that happens to be zero; the screen says there is none.
     */
    @Test
    fun `a unit with no external area says so rather than showing a zero`() {
        val units = twoUnits()
        assertTrue("fixture needs a flat with no terrace", units.any { !it.hasExternalArea })

        composeRule.setContent { Fixture(settings(AppLanguage.ENGLISH), units) }

        composeRule.onAllNodesWithText("No terrace or roof", substring = true)
            .assertCountEquals(units.count { !it.hasExternalArea })

        // Matched with its label rather than as a bare "0 m²": unit 1's
        // external area is 170 m², which contains "0 m²" as a substring. The
        // loose version of this assertion failed against correct code, which is
        // its own small lesson about substring matching on rendered numbers.
        composeRule.onAllNodesWithText("External area, 0 m²", substring = true)
            .assertCountEquals(0)
    }

    /**
     * Price per square metre is the number the objection library leans on, so
     * it has to be on the row rather than worked out at the door. 90,000 over
     * 151 m² is 596 to the dinar — and a rate that silently became the list
     * price would still render, and still look plausible.
     */
    @Test
    fun `every row carries its own price per square metre`() {
        val unit = schedule.first { it.internalArea == 151 && it.listPrice.dinars.toInt() == 90_000 }
        assertEquals(596, unit.pricePerSquareMetre.dinars.toInt())

        composeRule.setContent { Fixture(settings(AppLanguage.ENGLISH), listOf(unit)) }

        composeRule.onAllNodesWithText("596 JOD", substring = true).onFirst().assertExists()
        // The list price is on the row too, so the rate must not merely be it.
        assertTrue(unit.listPrice.dinars.toInt() != unit.pricePerSquareMetre.dinars.toInt())
    }

    /**
     * Every unit ships Available, so a status that failed to render would be
     * invisible in a screenshot of the seeded state. Asserted by word, because
     * the colour beside it is deliberately never the only carrier.
     */
    @Test
    fun `status is carried by a word, not only by a colour`() {
        assertTrue(schedule.all { it.status == UnitStatus.AVAILABLE })
        val units = twoUnits()

        composeRule.setContent { Fixture(settings(AppLanguage.ENGLISH), units) }

        composeRule.onAllNodesWithText("Available", substring = true)
            .assertCountEquals(units.size)
    }

    /**
     * The summary is `List<Apartment>.totals()`, so it cannot drift from the
     * rows above it. Asserted on the real schedule rather than the fixture,
     * because these are the figures the brief publishes and the team gets
     * asked about: fourteen units, 2,320 m², 1,496,000 JOD.
     */
    @Test
    fun `the summary is the schedule's own totals`() {
        val totals = schedule.totals()
        assertEquals(14, totals.unitCount)
        assertEquals(2_320, totals.internalArea)
        assertEquals(1_496_000, totals.grossDevelopmentValue.dinars.toInt())

        composeRule.setContent { Fixture(settings(AppLanguage.ENGLISH), schedule) }

        composeRule.onAllNodesWithText("1,496,000 JOD", substring = true).onFirst().assertExists()
        composeRule.onAllNodesWithText("2,320 m²", substring = true).onFirst().assertExists()
    }
}
