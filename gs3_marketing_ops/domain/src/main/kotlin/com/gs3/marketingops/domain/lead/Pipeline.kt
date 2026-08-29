package com.gs3.marketingops.domain.lead

/**
 * Why a sale did not happen.
 *
 * A required single-select, never free text alone, and this is the one field in
 * the app worth being strict about. Ranked over a year it is the only honest
 * evidence of whether the problem is the price, the product, or the process —
 * and "other, see note" across forty leads answers nothing. The note is
 * available in addition, not instead.
 */
enum class LossReason {
    PRICE,
    PAYMENT_TERMS,
    LOCATION,
    UNIT_SIZE,
    CHOSE_COMPETITOR,
    FINANCING_REFUSED,
    ELIGIBILITY_OR_APPROVAL,
    TIMING_POSTPONED,
    UNREACHABLE,
    OTHER,
    ;

    /** OTHER is the only one that needs the note filled in to mean anything. */
    val requiresNote: Boolean get() = this == OTHER
}

enum class LeadStage(val order: Int) {
    NEW_ENQUIRY(0),
    QUALIFIED(1),
    VIEWING_SCHEDULED(2),
    VIEWING_DONE(3),
    OFFER_SENT(4),
    NEGOTIATION(5),
    CONTRACTED(6),
    LOST(7),
    ;

    val isTerminal: Boolean get() = this == CONTRACTED || this == LOST
    val isOpen: Boolean get() = !isTerminal
}

/** Why a stage change was refused. */
sealed interface TransitionRefusal {
    /** Moving to LOST without saying why. */
    data object LossReasonRequired : TransitionRefusal

    /** LossReason.OTHER selected but nothing written. */
    data object LossNoteRequired : TransitionRefusal

    /** CONTRACTED and LOST are the end; a lead reopens as a new enquiry, not by rewind. */
    data class AlreadyTerminal(val stage: LeadStage) : TransitionRefusal

    /** Stages are not skipped forward — an offer without a viewing is a data-entry slip. */
    data class CannotSkip(val from: LeadStage, val to: LeadStage) : TransitionRefusal
}

sealed interface TransitionResult {
    data class Moved(val lead: Lead) : TransitionResult
    data class Refused(val reason: TransitionRefusal) : TransitionResult
}

object Pipeline {

    val sellingStages: List<LeadStage> =
        LeadStage.entries.filter { it != LeadStage.LOST }.sortedBy { it.order }

    /**
     * Moves a lead between stages, refusing the changes that would corrupt the
     * reports rather than silently accepting them.
     *
     * Going *backwards* is allowed — a viewing gets cancelled, a negotiation
     * stalls back to an offer, and real pipelines do that. Skipping *forwards*
     * is not: an offer recorded against a lead that never viewed is almost
     * always a mis-tap, and it would inflate the very conversion rate the team
     * uses to diagnose a weak month.
     */
    fun moveTo(
        lead: Lead,
        target: LeadStage,
        lossReason: LossReason? = null,
        note: String = lead.note,
    ): TransitionResult {
        if (lead.stage.isTerminal && target != lead.stage) {
            return TransitionResult.Refused(TransitionRefusal.AlreadyTerminal(lead.stage))
        }

        if (target == LeadStage.LOST) {
            if (lossReason == null) {
                return TransitionResult.Refused(TransitionRefusal.LossReasonRequired)
            }
            if (lossReason.requiresNote && note.isBlank()) {
                return TransitionResult.Refused(TransitionRefusal.LossNoteRequired)
            }
            return TransitionResult.Moved(lead.copy(stage = target, lossReason = lossReason, note = note))
        }

        val isForward = target.order > lead.stage.order
        if (isForward && target.order - lead.stage.order > 1) {
            return TransitionResult.Refused(TransitionRefusal.CannotSkip(lead.stage, target))
        }

        return TransitionResult.Moved(lead.copy(stage = target, note = note))
    }

    /** Counts at each stage, for the funnel card. Every stage appears, including the empty ones. */
    fun stageCounts(leads: List<Lead>): Map<LeadStage, Int> =
        LeadStage.entries.associateWith { stage -> leads.count { it.stage == stage } }

    /**
     * Loss reasons ranked. The most valuable report in the app, so it is
     * computed from the enum rather than from free text, and ties break by the
     * enum's own order to keep the chart stable between refreshes.
     */
    fun lossReasonsRanked(leads: List<Lead>): List<Pair<LossReason, Int>> =
        leads.mapNotNull { it.lossReason }
            .groupingBy { it }
            .eachCount()
            .toList()
            .sortedWith(compareByDescending<Pair<LossReason, Int>> { it.second }.thenBy { it.first.ordinal })
}
