package com.gs3.marketingops.domain.nonjordanian

import com.gs3.marketingops.domain.campaign.CampaignSpec
import com.gs3.marketingops.domain.campaign.Objective
import com.gs3.marketingops.domain.campaign.Platform
import com.gs3.marketingops.domain.funnel.Track
import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test
import java.time.Duration
import java.time.Instant

class EligibilityGateTest {

    @Test
    fun `the gate is closed by default`() {
        val gate = EligibilityGate()
        assertFalse(gate.isCleared)
        assertFalse(gate.allowsModuleAccess())
        assertFalse(gate.allowsNonJordanianCampaignActivation())
    }

    @Test
    fun `both documents and a reference are needed — no two of the three will do`() {
        // The Department's classification answers what the units are; the
        // lawyer's opinion answers what that means for this sale. Neither
        // answers the other, so neither alone opens the gate.
        assertFalse(EligibilityGate(landsAndSurveyStatementObtained = true, reference = "ref").isCleared)
        assertFalse(EligibilityGate(lawyerOpinionObtained = true, reference = "ref").isCleared)
        assertFalse(
            EligibilityGate(
                landsAndSurveyStatementObtained = true,
                lawyerOpinionObtained = true,
            ).isCleared
        )
    }

    @Test
    fun `a blank reference does not count as a reference`() {
        val gate = EligibilityGate(
            landsAndSurveyStatementObtained = true,
            lawyerOpinionObtained = true,
            reference = "   ",
        )
        assertFalse(gate.isCleared)
        assertTrue(gate.missingRequirements().contains("reference"))
    }

    @Test
    fun `all three together open it`() {
        val gate = EligibilityGate(
            landsAndSurveyStatementObtained = true,
            lawyerOpinionObtained = true,
            reference = "DLS-2026-4471",
            clearedAt = Instant.parse("2026-09-01T08:00:00Z"),
        )
        assertTrue(gate.isCleared)
        assertTrue(gate.allowsModuleAccess())
        assertTrue(gate.missingRequirements().isEmpty())
    }

    @Test
    fun `the blocking screen can say exactly what is missing`() {
        assertEquals(
            listOf("lands_and_survey_statement", "lawyer_opinion", "reference"),
            EligibilityGate().missingRequirements(),
        )
    }

    @Test
    fun `a closed gate stops a NONJO campaign but nothing else`() {
        // The same gate, checked from the campaign side. This is the rule that
        // stops money being spent on a track whose legality is unresolved.
        val gate = EligibilityGate()
        val nonJordanian = CampaignSpec(
            Track.NONJO, "IRQ", Objective.CONV, "LAL1", "Reel30s", 1, Platform.META,
        )
        val expatriate = nonJordanian.copy(track = Track.EXPAT, market = "UAE")

        assertFalse(nonJordanian.canActivate(gate.allowsNonJordanianCampaignActivation()))
        assertTrue(expatriate.canActivate(gate.allowsNonJordanianCampaignActivation()))
    }
}

class NonJordanianFileTest {

    private val opened = Instant.parse("2026-08-01T09:00:00Z")

    private fun file(
        steps: List<JourneyStepState> = JourneyStep.entries.map { JourneyStepState(it) },
        lastUpdate: Instant? = null,
    ) = NonJordanianFile(id = "F1", leadId = "L1", steps = steps, openedAt = opened, lastClientUpdateAt = lastUpdate)

    @Test
    fun `the journey has eight steps in order`() {
        assertEquals(8, JourneyStep.entries.size)
        assertEquals((1..8).toList(), JourneyStep.entries.map { it.order })
        assertEquals(JourneyStep.CONSULTATION_AND_ELIGIBILITY, JourneyStep.entries.first())
        assertEquals(JourneyStep.HANDOVER_AND_AFTER_SALES, JourneyStep.entries.last())
    }

    @Test
    fun `the current step is the first one not finished`() {
        assertEquals(JourneyStep.CONSULTATION_AND_ELIGIBILITY, file().currentStep)

        val started = file(
            JourneyStep.entries.map { step ->
                JourneyStepState(step, if (step.order <= 2) StepStatus.DONE else StepStatus.NOT_STARTED)
            }
        )
        assertEquals(JourneyStep.WRITTEN_OFFER_AND_LEGAL_REVIEW, started.currentStep)
    }

    @Test
    fun `a finished file has no current step`() {
        val done = file(JourneyStep.entries.map { JourneyStepState(it, StepStatus.DONE) })
        assertTrue(done.isComplete)
        assertEquals(null, done.currentStep)
    }

    @Test
    fun `the ten-day update is due from the last contact, or from opening`() {
        assertEquals(opened.plus(Duration.ofDays(10)), file().updateDueAt())

        val contacted = Instant.parse("2026-08-05T09:00:00Z")
        assertEquals(contacted.plus(Duration.ofDays(10)), file(lastUpdate = contacted).updateDueAt())
    }

    @Test
    fun `an open file goes overdue after ten days of silence`() {
        val eleventhDay = opened.plus(Duration.ofDays(11))
        assertTrue(file().isUpdateOverdue(eleventhDay))
        assertFalse(file().isUpdateOverdue(opened.plus(Duration.ofDays(9))))
    }

    @Test
    fun `a completed file stops demanding updates`() {
        val done = file(JourneyStep.entries.map { JourneyStepState(it, StepStatus.DONE) })
        assertFalse(done.isUpdateOverdue(opened.plus(Duration.ofDays(365))))
    }

    @Test
    fun `outstanding documents are listed by who owes them`() {
        val withDocs = file().copy(
            documents = listOf(
                DocumentItem("authorisation", DocumentProvider.BUYER, received = false),
                DocumentItem("passport_copy", DocumentProvider.BUYER, received = true),
                DocumentItem("unit_specification", DocumentProvider.COMPANY, received = false),
            )
        )
        assertEquals(listOf("authorisation"), withDocs.outstandingDocuments(DocumentProvider.BUYER).map { it.key })
        assertEquals(listOf("unit_specification"), withDocs.outstandingDocuments(DocumentProvider.COMPANY).map { it.key })
    }

    @Test
    fun `a checklist item records receipt and nothing else`() {
        // Only the fact that a document arrived is stored — never the document.
        // A sales phone is the wrong place for a passport scan.
        val properties = DocumentItem::class.java.declaredFields.map { it.name.lowercase() }
        val forbidden = listOf("content", "bytes", "file", "path", "uri", "image", "scan", "number")
        val offenders = properties.filter { property -> forbidden.any { property.contains(it) } }
        assertTrue(offenders.isEmpty(), "DocumentItem must record receipt only, found: $offenders")
    }

    @Test
    fun `approval durations are indicative reference only, longest last`() {
        val durations = ApprovalAuthority.entries.map { it.indicativeDuration }
        assertEquals(durations.sorted(), durations)
        assertEquals(Duration.ofDays(1), ApprovalAuthority.DIRECTOR_GENERAL.indicativeDuration)
        assertEquals(Duration.ofDays(30), ApprovalAuthority.SECURITY_CLEARANCE.indicativeDuration)
    }
}
