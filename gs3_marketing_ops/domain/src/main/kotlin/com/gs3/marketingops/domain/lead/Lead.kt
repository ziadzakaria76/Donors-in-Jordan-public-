package com.gs3.marketingops.domain.lead

import com.gs3.marketingops.domain.funnel.Track
import com.gs3.marketingops.domain.money.AppLanguage
import java.time.Instant
import java.time.ZoneId

/** Where an enquiry came from. Wrong sources make the cost-per-lead report untrustworthy. */
enum class LeadSource {
    META, GOOGLE_SEARCH, YOUTUBE, SNAPCHAT, TIKTOK, LINKEDIN,
    OPENSOOQ, BAYUT, KHARETA, REALSOOQ,
    WEBSITE, WHATSAPP_DIRECT, WALK_IN, SIGNAGE_QR,
    BROKER, REFERRAL, OPEN_HOUSE, EXHIBITION, OTHER,
}

/**
 * Which of the two special tracks a buyer falls into, if either.
 *
 * This is not the same question as nationality in the passport sense, and the
 * app does not need that. It needs to know which process applies: a Jordanian
 * abroad buys remotely, and a non-Jordanian needs government approvals the
 * company cannot promise.
 */
enum class NationalityCategory(val track: Track) {
    JORDANIAN_RESIDENT(Track.LOCAL),
    JORDANIAN_EXPATRIATE(Track.EXPAT),
    ARAB_NON_JORDANIAN(Track.NONJO),
    NON_ARAB(Track.NONJO),
}

enum class Purpose { RESIDENCE, INVESTMENT }

enum class BudgetBand { UNDER_100K, FROM_100K_TO_130K, FROM_130K_TO_160K, ABOVE_160K, UNSTATED }

/** The five standard qualifying questions, as quick-tap chips. */
data class Qualification(
    val purpose: Purpose? = null,
    val householdSize: Int? = null,
    val financing: Financing? = null,
    val timeFrame: TimeFrame? = null,
    val visitedOtherProjects: Boolean? = null,
) {
    enum class Financing { CASH, BANK }
    enum class TimeFrame { WITHIN_A_MONTH, WITHIN_THREE_MONTHS, LATER }

    /** Answered enough to be worth a viewing — purpose, financing and time frame. */
    val isComplete: Boolean get() = purpose != null && financing != null && timeFrame != null

    val answeredCount: Int
        get() = listOfNotNull(purpose, householdSize, financing, timeFrame, visitedOtherProjects).size
}

/**
 * A prospective buyer.
 *
 * Note what is absent, deliberately: no passport number, no national ID, no
 * bank details, no scanned documents. This is a sales operations app on a phone
 * that could be lost or stolen, and holding identity documents on it would
 * create a liability out of all proportion to the convenience. Where a document
 * checklist item is ticked, only the fact of receipt is stored — never the
 * document. A test asserts this type keeps no such field, so the rule survives
 * the next person who adds a "useful" column.
 */
data class Lead(
    val id: String,
    val name: String,
    val phone: String,
    val language: AppLanguage,
    val countryOfResidence: String,
    val timeZone: ZoneId,
    val nationalityCategory: NationalityCategory,
    val source: LeadSource,
    val stage: LeadStage = LeadStage.NEW_ENQUIRY,
    val qualification: Qualification = Qualification(),
    val budgetBand: BudgetBand = BudgetBand.UNSTATED,
    val unitsOfInterest: List<Int> = emptyList(),
    val assignedTo: String? = null,
    val note: String = "",
    val email: String? = null,
    val enquiredAt: Instant,
    val lastContactedAt: Instant? = null,
    val lossReason: LossReason? = null,
) {
    init {
        require(name.isNotBlank()) { "A lead needs a name" }
        require(phone.isNotBlank()) { "A lead needs a phone number" }
        require(stage != LeadStage.LOST || lossReason != null) {
            "A lost lead must carry a loss reason — this is the report the company learns from"
        }
    }

    val track: Track get() = nationalityCategory.track

    /**
     * The 10-day update promise applies to external-track leads whether or not
     * anything has changed. Silence is what loses a buyer four time zones away.
     */
    val needsPeriodicUpdate: Boolean get() = track.isExternal && stage.isOpen
}
