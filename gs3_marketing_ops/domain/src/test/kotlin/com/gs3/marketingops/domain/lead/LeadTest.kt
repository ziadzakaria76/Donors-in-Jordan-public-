package com.gs3.marketingops.domain.lead

import com.gs3.marketingops.domain.funnel.Track
import com.gs3.marketingops.domain.money.AppLanguage
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.time.Instant
import java.time.ZoneId

internal fun lead(
    id: String = "L1",
    stage: LeadStage = LeadStage.NEW_ENQUIRY,
    category: NationalityCategory = NationalityCategory.JORDANIAN_RESIDENT,
    source: LeadSource = LeadSource.META,
    lossReason: LossReason? = null,
    lastContactedAt: Instant? = null,
) = Lead(
    id = id,
    name = "أحمد",
    phone = "0790730903",
    language = AppLanguage.ARABIC,
    countryOfResidence = "JO",
    timeZone = ZoneId.of("Asia/Amman"),
    nationalityCategory = category,
    source = source,
    stage = stage,
    lossReason = lossReason,
    lastContactedAt = lastContactedAt,
    enquiredAt = Instant.parse("2026-08-01T09:00:00Z"),
)

class LeadTest {

    @Test
    fun `nationality category decides the track, and so the whole process`() {
        assertEquals(Track.LOCAL, NationalityCategory.JORDANIAN_RESIDENT.track)
        assertEquals(Track.EXPAT, NationalityCategory.JORDANIAN_EXPATRIATE.track)
    }

    @Test
    fun `the two non-Jordanian categories are gone, not remapped onto expatriate`() {
        // D-23. The failure this guards against is not the enum coming back —
        // it is the enum coming back pointed at EXPAT, which would file a
        // non-Jordanian buyer as a Jordanian expatriate and look perfectly
        // healthy on every screen. Every category must map to the track its own
        // name describes, and only two names are left that can.
        assertEquals(
            listOf("JORDANIAN_RESIDENT", "JORDANIAN_EXPATRIATE"),
            NationalityCategory.entries.map { it.name },
        )
    }

    @Test
    fun `a lost lead cannot exist without a reason`() {
        val thrown = runCatching { lead(stage = LeadStage.LOST) }.exceptionOrNull()
        assertTrue(thrown is IllegalArgumentException)
        // With a reason it constructs fine.
        assertEquals(LossReason.PRICE, lead(stage = LeadStage.LOST, lossReason = LossReason.PRICE).lossReason)
    }

    @Test
    fun `only open external-track leads carry the periodic update promise`() {
        assertTrue(lead(category = NationalityCategory.JORDANIAN_EXPATRIATE).needsPeriodicUpdate)
        assertFalse(lead(category = NationalityCategory.JORDANIAN_RESIDENT).needsPeriodicUpdate)
        // Contracted or lost: the promise ends with the process.
        assertFalse(
            lead(
                category = NationalityCategory.JORDANIAN_EXPATRIATE,
                stage = LeadStage.CONTRACTED,
            ).needsPeriodicUpdate
        )
    }

    @Test
    fun `qualification is complete on purpose, financing and time frame`() {
        val partial = Qualification(purpose = Purpose.RESIDENCE)
        assertFalse(partial.isComplete)
        assertEquals(1, partial.answeredCount)

        val full = Qualification(
            purpose = Purpose.INVESTMENT,
            householdSize = 4,
            financing = Qualification.Financing.BANK,
            timeFrame = Qualification.TimeFrame.WITHIN_THREE_MONTHS,
            visitedOtherProjects = true,
        )
        assertTrue(full.isComplete)
        assertEquals(5, full.answeredCount)
    }

    /**
     * The privacy rule, enforced rather than documented.
     *
     * The brief forbids storing passport numbers, national IDs, bank details or
     * identity documents on a sales phone. A comment saying so survives exactly
     * until the next person who needs "just one more field", so this asserts it
     * against the type itself.
     */
    @Test
    fun `the lead type holds no identity or banking field`() {
        val forbidden = listOf(
            "passport", "nationalid", "national_id", "idnumber", "id_number",
            "iban", "bank", "account", "card", "document", "scan", "attachment",
        )
        val properties = Lead::class.java.declaredFields.map { it.name.lowercase() }
        val offenders = properties.filter { property -> forbidden.any { property.contains(it) } }
        assertTrue(offenders.isEmpty(), "Lead must not hold identity or banking data, found: $offenders")
    }
}

class PipelineTest {

    @Test
    fun `a lead moves forward one stage at a time`() {
        val result = Pipeline.moveTo(lead(), LeadStage.QUALIFIED)
        assertTrue(result is TransitionResult.Moved)
        assertEquals(LeadStage.QUALIFIED, (result as TransitionResult.Moved).lead.stage)
    }

    @Test
    fun `skipping forward is refused, because it would inflate the conversion rate`() {
        // An offer recorded against a lead that never viewed is almost always a
        // mis-tap, and it corrupts the very number used to diagnose a weak month.
        val result = Pipeline.moveTo(lead(), LeadStage.OFFER_SENT)
        assertTrue(result is TransitionResult.Refused)
        assertEquals(
            TransitionRefusal.CannotSkip(LeadStage.NEW_ENQUIRY, LeadStage.OFFER_SENT),
            (result as TransitionResult.Refused).reason,
        )
    }

    @Test
    fun `going backwards is allowed, because real pipelines do that`() {
        val negotiating = lead(stage = LeadStage.NEGOTIATION)
        val result = Pipeline.moveTo(negotiating, LeadStage.OFFER_SENT)
        assertTrue(result is TransitionResult.Moved)
    }

    @Test
    fun `moving to lost without a reason is refused`() {
        val result = Pipeline.moveTo(lead(stage = LeadStage.QUALIFIED), LeadStage.LOST)
        assertEquals(
            TransitionRefusal.LossReasonRequired,
            (result as TransitionResult.Refused).reason,
        )
    }

    @Test
    fun `loss reason OTHER needs the note filled in`() {
        val qualified = lead(stage = LeadStage.QUALIFIED)
        val withoutNote = Pipeline.moveTo(qualified, LeadStage.LOST, LossReason.OTHER, note = "  ")
        assertEquals(TransitionRefusal.LossNoteRequired, (withoutNote as TransitionResult.Refused).reason)

        val withNote = Pipeline.moveTo(qualified, LeadStage.LOST, LossReason.OTHER, note = "Moved abroad")
        assertTrue(withNote is TransitionResult.Moved)
    }

    @Test
    fun `a named loss reason needs no note`() {
        val result = Pipeline.moveTo(lead(stage = LeadStage.QUALIFIED), LeadStage.LOST, LossReason.PRICE)
        assertTrue(result is TransitionResult.Moved)
        assertEquals(LossReason.PRICE, (result as TransitionResult.Moved).lead.lossReason)
    }

    @Test
    fun `a terminal lead does not rewind`() {
        val contracted = lead(stage = LeadStage.CONTRACTED)
        val result = Pipeline.moveTo(contracted, LeadStage.NEGOTIATION)
        assertEquals(
            TransitionRefusal.AlreadyTerminal(LeadStage.CONTRACTED),
            (result as TransitionResult.Refused).reason,
        )
    }

    @Test
    fun `loss reasons rank by frequency, with a stable tie-break`() {
        val leads = listOf(
            lead("1", LeadStage.LOST, lossReason = LossReason.PRICE),
            lead("2", LeadStage.LOST, lossReason = LossReason.PRICE),
            lead("3", LeadStage.LOST, lossReason = LossReason.LOCATION),
            lead("4", LeadStage.LOST, lossReason = LossReason.PAYMENT_TERMS),
            lead("5", LeadStage.QUALIFIED),
        )
        val ranked = Pipeline.lossReasonsRanked(leads)
        assertEquals(LossReason.PRICE to 2, ranked.first())
        // PAYMENT_TERMS and LOCATION both have one; the enum order breaks the tie
        // so the chart does not reshuffle itself between refreshes.
        assertEquals(listOf(LossReason.PAYMENT_TERMS, LossReason.LOCATION), ranked.drop(1).map { it.first })
    }

    @Test
    fun `stage counts include the empty stages`() {
        val counts = Pipeline.stageCounts(listOf(lead()))
        assertEquals(LeadStage.entries.size, counts.size)
        assertEquals(1, counts[LeadStage.NEW_ENQUIRY])
        assertEquals(0, counts[LeadStage.CONTRACTED])
    }
}
