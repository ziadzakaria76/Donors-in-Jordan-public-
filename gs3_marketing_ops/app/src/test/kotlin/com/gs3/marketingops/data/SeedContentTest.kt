package com.gs3.marketingops.data

import com.gs3.marketingops.core.data.seed.Gs3Seed
import com.gs3.marketingops.domain.budget.Gs3Budget
import com.gs3.marketingops.domain.inventory.Gs3Schedule
import com.gs3.marketingops.domain.inventory.totals
import com.gs3.marketingops.domain.money.Jod
import com.gs3.marketingops.domain.outreach.MessageTemplate
import com.gs3.marketingops.nonjordanian.data.ContractClaim
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * What the app ships with, asserted rather than assumed.
 *
 * Plain JUnit with no Robolectric: the seed is pure Kotlin, and these run in
 * milliseconds. The Room round-trip is exercised separately in
 * `DatabaseSeedTest`.
 */
class SeedContentTest {

    @Test
    fun `the seeded units are the schedule, not a second copy of it`() {
        val seeded = Gs3Seed.units().map { it.toDomain() }

        // Whole-object equality, not a spot check on a few fields. A price that
        // is right and a priority class that is wrong is still a defect, and
        // this is the assertion that would catch it.
        assertEquals(Gs3Schedule.apartments, seeded)
    }

    @Test
    fun `the brief's own inventory totals survive the round trip`() {
        val totals = Gs3Seed.units().map { it.toDomain() }.totals()

        assertEquals(14, totals.unitCount)
        assertEquals(2_320, totals.internalArea)
        assertEquals(620, totals.externalArea)
        assertEquals(Jod.ofDinars(1_496_000), totals.grossDevelopmentValue)

        // 644.828 JOD/m², which is the figure the brief quotes as 645.
        assertEquals(
            645L,
            totals.weightedPricePerSquareMetre.dinars
                .setScale(0, java.math.RoundingMode.HALF_UP)
                .toLong(),
        )
    }

    @Test
    fun `the seeded budget rows sum to the track totals exactly`() {
        val seeded = Gs3Seed.marketBudgets().map { it.toDomain() }

        assertEquals(Gs3Budget.externalTrackMarkets, seeded)
        assertEquals(
            Gs3Budget.externalTrackTotal,
            seeded.fold(Jod.ZERO) { running, row -> running + row.annual },
        )
        assertEquals(Jod.ofDinars(7_200), Gs3Budget.externalTrackTotal)
    }

    @Test
    fun `the eligibility gate ships closed, and a closed gate blocks both things it must`() {
        val gate = Gs3Seed.eligibilityGate().toDomain()

        // B-1 is unanswered. This is the correct shipping state, not a stub.
        assertTrue(!gate.isCleared)
        assertTrue(!gate.allowsModuleAccess())
        assertTrue(!gate.allowsNonJordanianCampaignActivation())
        assertEquals(
            listOf("lands_and_survey_statement", "lawyer_opinion", "reference"),
            gate.missingRequirements(),
        )
    }

    @Test
    fun `the two confirmed contract claims ship confirmed and the other two do not`() {
        val claims = Gs3Seed.contractClaims()

        assertEquals(ContractClaim.entries.size, claims.size)
        assertEquals(4, claims.size)
        // Four rows rather than one switch. This is the case that design was
        // for: B-2 came back answered in part, and a single switch would have
        // forced all four to share the most cautious answer.
        assertEquals(ContractClaim.entries.map { it.name }.toSet(), claims.map { it.claim }.toSet())

        val confirmed = claims.filter { it.confirmedPresent }.map { it.claimType }.toSet()
        assertEquals(
            setOf(
                ContractClaim.FINISHING_SPECIFICATIONS_ANNEX,
                ContractClaim.QUARTERLY_PHOTOGRAPHIC_PROGRESS_REPORT,
            ),
            confirmed,
        )

        // Not confirmed means "nobody has verified it", never "verified
        // absent". Either way it stays out of client text.
        val unconfirmed = claims.filterNot { it.confirmedPresent }.map { it.claimType }.toSet()
        assertEquals(
            setOf(
                ContractClaim.DELAY_PENALTY_IN_BUYERS_FAVOUR,
                ContractClaim.TWO_YEAR_AND_TEN_YEAR_WARRANTY,
            ),
            unconfirmed,
        )

        // A confirmation is dated, so its age is visible. No clause references
        // were supplied, so they stay null until someone has the contract open.
        assertTrue(claims.filter { it.confirmedPresent }.all { it.confirmedAt != null })
        assertTrue(claims.filterNot { it.confirmedPresent }.all { it.confirmedAt == null })
        assertTrue(claims.all { it.contractReference == null })
    }

    @Test
    fun `every template renders with the unit variables and nothing else`() {
        val values = MessageTemplate.UNIT_VARIABLES.associateWith { "x" }

        Gs3Seed.messageTemplates().forEach { seeded ->
            listOf(seeded.bodyAr to "ar", seeded.bodyEn to "en").forEach { (body, language) ->
                val template = MessageTemplate(seeded.templateKey, body)
                val unknown = template.placeholders() - MessageTemplate.UNIT_VARIABLES

                assertTrue(
                    "${seeded.templateKey} ($language) uses unknown placeholders: $unknown",
                    unknown.isEmpty(),
                )
                assertNotNull(
                    "${seeded.templateKey} ($language) failed to render",
                    template.render(values),
                )
            }
        }
    }

    @Test
    fun `a template with a missing value refuses to render rather than sending a brace to a client`() {
        val withPlaceholders = Gs3Seed.messageTemplates()
            .map { MessageTemplate(it.templateKey, it.bodyAr) }
            .filter { it.placeholders().isNotEmpty() }

        assertTrue("no template uses placeholders at all", withPlaceholders.isNotEmpty())
        withPlaceholders.forEach { assertNull(it.render(emptyMap())) }
    }

    @Test
    fun `both languages exist for every template and objection`() {
        Gs3Seed.messageTemplates().forEach {
            assertTrue("${it.templateKey} has no Arabic", it.bodyAr.isNotBlank())
            assertTrue("${it.templateKey} has no English", it.bodyEn.isNotBlank())
        }
        Gs3Seed.objections().forEach {
            assertTrue("${it.objectionKey} has no Arabic", it.objectionAr.isNotBlank())
            assertTrue("${it.objectionKey} has no English", it.objectionEn.isNotBlank())
            assertTrue("${it.objectionKey} has no Arabic answer", it.responseAr.isNotBlank())
            assertTrue("${it.objectionKey} has no English answer", it.responseEn.isNotBlank())
        }
    }

    @Test
    fun `objections are uniquely keyed and uniquely ordered`() {
        val objections = Gs3Seed.objections()

        assertEquals(objections.size, objections.map { it.objectionKey }.toSet().size)
        assertEquals(objections.size, objections.map { it.displayOrder }.toSet().size)
    }

    /**
     * The one that matters most, and the reason this file exists.
     *
     * `verifyStrings` polices `strings.xml`, and it cannot see this: client-facing
     * text now also lives in Kotlin seed data, which is a real gap the moment
     * templates and objections were written. This closes it.
     *
     * Two families of phrase are banned. The first is the **B-2 contract claims
     * that are still unconfirmed**. B-2 came back answered in part on
     * 2026-08-29: the finishing-specifications annex and the quarterly
     * photographic progress report are in the signed contract, so they are no
     * longer promises the company cannot make and are no longer banned here.
     * The delay penalty and the warranty are not confirmed, so they stay banned
     * — and they stay banned on the same reasoning as before, not a weaker one:
     * unconfirmed means nobody has checked, which is not the same as absent,
     * and both keep the phrase out of a client's hands.
     *
     * The second family is the standing **forbidden phrases**: a fee exemption
     * the company cannot grant, an approval that belongs to the authorities, a
     * return that belongs to the market. Note that «ضمان» stays on the list
     * twice over — as the unconfirmed warranty, and inside «ضمان الموافقة»,
     * which is forbidden regardless of what any contract says.
     */
    @Test
    fun `no seeded client-facing text promises anything unverified`() {
        val banned = mapOf(
            // --- B-2 claims still unconfirmed against the signed contract ---
            // The annex and the quarterly report were confirmed on 2026-08-29
            // and are deliberately no longer here.
            "غرامة تأخير" to "a delay penalty is an unconfirmed B-2 claim",
            "غرامة التأخير" to "a delay penalty is an unconfirmed B-2 claim",
            "delay penalty" to "a delay penalty is an unconfirmed B-2 claim",
            "ضمان" to "a warranty is an unconfirmed B-2 claim",
            "كفالة" to "a warranty is an unconfirmed B-2 claim",
            "warranty" to "a warranty is an unconfirmed B-2 claim",

            // --- Standing forbidden phrases, same list verifyStrings enforces ---
            "إعفاء من الرسوم" to "the company contributes toward fees; it cannot exempt anyone",
            "fee exemption" to "the company contributes toward fees; it cannot exempt anyone",
            "ضمان الموافقة" to "approval rests with the competent authorities",
            "guaranteed approval" to "approval rests with the competent authorities",
            "عائد مضمون" to "a yield estimate is not a guarantee",
            "guaranteed return" to "a yield estimate is not a guarantee",
        )

        val clientFacing: List<Pair<String, String>> =
            Gs3Seed.messageTemplates().flatMap {
                listOf("template ${it.templateKey} (ar)" to it.bodyAr, "template ${it.templateKey} (en)" to it.bodyEn)
            } + Gs3Seed.objections().flatMap {
                listOf(
                    "objection ${it.objectionKey} (ar)" to it.responseAr,
                    "objection ${it.objectionKey} (en)" to it.responseEn,
                    "objection ${it.objectionKey} prompt (ar)" to it.objectionAr,
                    "objection ${it.objectionKey} prompt (en)" to it.objectionEn,
                )
            }

        val violations = clientFacing.flatMap { (where, text) ->
            banned.filterKeys { text.contains(it, ignoreCase = true) }
                .map { (phrase, why) -> "$where contains \"$phrase\" — $why" }
        }

        assertTrue(
            "seeded text promises something unverified:\n" + violations.joinToString("\n"),
            violations.isEmpty(),
        )
    }

    @Test
    fun `the non-Jordanian objection answers honestly while B-1 is unanswered`() {
        val objection = Gs3Seed.objections().single { it.objectionKey == "non_jordanian_eligibility" }

        // It must defer to the authorities rather than give an opinion, and say
        // that the written answer is being sought — the same position the gate
        // enforces in code.
        assertTrue(objection.responseAr.contains("الجهات المختصّة"))
        assertTrue(objection.responseEn.contains("competent authorities", ignoreCase = true))
        assertTrue(objection.responseAr.contains("دائرة الأراضي والمساحة"))
        assertTrue(objection.responseEn.contains("Department of Lands and Survey", ignoreCase = true))
    }
}
