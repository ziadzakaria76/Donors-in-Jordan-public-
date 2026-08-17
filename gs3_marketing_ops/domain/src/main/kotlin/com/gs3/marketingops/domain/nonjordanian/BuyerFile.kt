package com.gs3.marketingops.domain.nonjordanian

import java.time.Duration
import java.time.Instant
import java.time.LocalDate

/**
 * The eight steps of a non-Jordanian purchase.
 *
 * Numbered and ordered because the process genuinely is sequential — a file
 * cannot be opened before an offer is reviewed, and nothing is registered
 * before it is approved.
 */
enum class JourneyStep(val order: Int) {
    CONSULTATION_AND_ELIGIBILITY(1),
    UNIT_SELECTION_AND_LIVE_TOUR(2),
    WRITTEN_OFFER_AND_LEGAL_REVIEW(3),
    AUTHORISATION_AND_FILE_OPENING(4),
    OFFICIAL_APPROVALS(5),
    SIGNING_AND_FIRST_PAYMENT(6),
    REGISTRATION_AND_TITLE_TRANSFER(7),
    HANDOVER_AND_AFTER_SALES(8),
}

enum class StepStatus { NOT_STARTED, IN_PROGRESS, DONE, BLOCKED }

data class JourneyStepState(
    val step: JourneyStep,
    val status: StepStatus = StepStatus.NOT_STARTED,
    val date: LocalDate? = null,
    val responsible: String? = null,
    val documentsProduced: List<String> = emptyList(),
)

/** Who is expected to produce a document. */
enum class DocumentProvider { BUYER, COMPANY, CASE_BY_CASE }

/**
 * A checklist item records only *that* a document was received — never the
 * document, and never its contents. Storing a passport scan on a sales phone
 * would be a liability out of all proportion to the convenience, and the app
 * has no need for it: the process needs to know the file is complete, not what
 * is in it.
 */
data class DocumentItem(
    val key: String,
    val provider: DocumentProvider,
    val received: Boolean = false,
)

/**
 * Indicative processing times for the approval authorities, published so the
 * team can set expectations — and labelled indicative because they are not
 * commitments anybody can make. The app states these as reference only, beside
 * a standing disclaimer that approval rests solely with the competent
 * authorities.
 */
enum class ApprovalAuthority(val indicativeDuration: Duration) {
    DIRECTOR_GENERAL(Duration.ofDays(1)),
    MINISTER_OF_FINANCE(Duration.ofDays(4)),
    COUNCIL_OF_MINISTERS(Duration.ofDays(20)),
    SECURITY_CLEARANCE(Duration.ofDays(30)),
}

data class NonJordanianFile(
    val id: String,
    val leadId: String,
    val steps: List<JourneyStepState> = JourneyStep.entries.map { JourneyStepState(it) },
    val documents: List<DocumentItem> = emptyList(),
    val lastClientUpdateAt: Instant? = null,
    val openedAt: Instant,
) {
    val currentStep: JourneyStep?
        get() = steps.sortedBy { it.step.order }.firstOrNull { it.status != StepStatus.DONE }?.step

    val isComplete: Boolean get() = steps.all { it.status == StepStatus.DONE }

    fun outstandingDocuments(provider: DocumentProvider): List<DocumentItem> =
        documents.filter { it.provider == provider && !it.received }

    /** The 10-day update promise, which applies to every open file. */
    fun updateDueAt(): Instant = (lastClientUpdateAt ?: openedAt).plus(UPDATE_INTERVAL)

    fun isUpdateOverdue(now: Instant): Boolean = !isComplete && now >= updateDueAt()

    companion object {
        val UPDATE_INTERVAL: Duration = Duration.ofDays(10)
    }
}

/**
 * The blocking gate.
 *
 * This exists because a government minister stated before parliament that the
 * law in force does not permit non-Jordanians to own residential units in
 * complexes, while an amendment is still in progress. Until that is resolved in
 * writing, the company must not spend money marketing to those buyers or make
 * promises to them — so the app refuses, rather than relying on anyone to
 * remember.
 *
 * Clearing it takes two written documents and a reference. Both, not either:
 * the Department's classification answers what the units are, and the lawyer's
 * opinion answers what that means for this sale, and neither answers the other.
 */
data class EligibilityGate(
    val landsAndSurveyStatementObtained: Boolean = false,
    val lawyerOpinionObtained: Boolean = false,
    val reference: String = "",
    val clearedAt: Instant? = null,
) {
    val isCleared: Boolean
        get() = landsAndSurveyStatementObtained &&
            lawyerOpinionObtained &&
            reference.isNotBlank()

    /** What is still missing, for the blocking screen to state plainly. */
    fun missingRequirements(): List<String> = buildList {
        if (!landsAndSurveyStatementObtained) add("lands_and_survey_statement")
        if (!lawyerOpinionObtained) add("lawyer_opinion")
        if (reference.isBlank()) add("reference")
    }

    /** The module is unreachable, and NONJO campaigns unstartable, until this is true. */
    fun allowsModuleAccess(): Boolean = isCleared

    fun allowsNonJordanianCampaignActivation(): Boolean = isCleared
}
