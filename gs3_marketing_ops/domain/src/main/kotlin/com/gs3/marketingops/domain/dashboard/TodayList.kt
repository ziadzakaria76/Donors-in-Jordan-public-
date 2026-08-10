package com.gs3.marketingops.domain.dashboard

import com.gs3.marketingops.domain.lead.Lead
import com.gs3.marketingops.domain.lead.LeadStage
import com.gs3.marketingops.domain.sla.SlaEngine
import java.time.Duration
import java.time.Instant

/**
 * The kinds of thing that can be the most useful next action, most urgent
 * first. The ordinal is the priority — an overdue first response outranks
 * everything, because it is the only one where the damage compounds by the
 * minute.
 */
enum class ActionKind {
    OVERDUE_FIRST_RESPONSE,
    OFFER_EXPIRING,
    VIEWING_FOLLOW_UP_DUE,
    EXTERNAL_UPDATE_DUE,
    UNIT_WITHOUT_ENQUIRIES,
}

data class PriorityAction(
    val kind: ActionKind,
    val leadId: String? = null,
    val unitNumber: Int? = null,
    /** How overdue, or how soon due. Negative means already past. */
    val dueIn: Duration,
) {
    val isOverdue: Boolean get() = dueIn.isNegative
}

/** Everything the rules need, gathered once so the computation stays pure. */
data class DashboardInput(
    val now: Instant,
    val leads: List<Lead>,
    val firstResponseDueAt: Map<String, Instant> = emptyMap(),
    val viewingFollowUpDueAt: Map<String, Instant> = emptyMap(),
    val offerExpiresAt: Map<String, Instant> = emptyMap(),
    val unitsWithoutEnquiriesFor: Map<Int, Duration> = emptyMap(),
)

object TodayList {

    const val MAX_ACTIONS: Int = 5
    val OFFER_EXPIRY_WINDOW: Duration = Duration.ofDays(3)
    val UNIT_SILENCE_WINDOW: Duration = Duration.ofDays(30)

    /**
     * The five highest-priority actions.
     *
     * Ordering is by kind first and lateness second, not by lateness alone.
     * A first response four minutes overdue matters more than a unit that has
     * been quiet for thirty-one days, even though the unit is "later" by a
     * factor of ten thousand — sorting purely on elapsed time would bury the
     * one action with a fifteen-minute window under a pile of slow-burning
     * ones, every single day.
     */
    fun compute(input: DashboardInput): List<PriorityAction> {
        val actions = mutableListOf<PriorityAction>()
        val byId = input.leads.associateBy { it.id }

        input.firstResponseDueAt.forEach { (leadId, dueAt) ->
            val lead = byId[leadId] ?: return@forEach
            if (lead.stage != LeadStage.NEW_ENQUIRY) return@forEach
            if (input.now >= dueAt) {
                actions += PriorityAction(
                    ActionKind.OVERDUE_FIRST_RESPONSE, leadId, dueIn = Duration.between(input.now, dueAt),
                )
            }
        }

        input.offerExpiresAt.forEach { (leadId, expiresAt) ->
            val lead = byId[leadId] ?: return@forEach
            if (!lead.stage.isOpen) return@forEach
            val remaining = Duration.between(input.now, expiresAt)
            if (remaining <= OFFER_EXPIRY_WINDOW) {
                actions += PriorityAction(ActionKind.OFFER_EXPIRING, leadId, dueIn = remaining)
            }
        }

        input.viewingFollowUpDueAt.forEach { (leadId, dueAt) ->
            val lead = byId[leadId] ?: return@forEach
            if (lead.stage != LeadStage.VIEWING_DONE) return@forEach
            if (input.now >= dueAt) {
                actions += PriorityAction(
                    ActionKind.VIEWING_FOLLOW_UP_DUE, leadId, dueIn = Duration.between(input.now, dueAt),
                )
            }
        }

        input.leads.filter { it.needsPeriodicUpdate }.forEach { lead ->
            val since = lead.lastContactedAt ?: lead.enquiredAt
            val dueAt = since.plus(SlaEngine.EXTERNAL_UPDATE_INTERVAL)
            if (input.now >= dueAt) {
                actions += PriorityAction(
                    ActionKind.EXTERNAL_UPDATE_DUE, lead.id, dueIn = Duration.between(input.now, dueAt),
                )
            }
        }

        input.unitsWithoutEnquiriesFor.forEach { (unitNumber, silence) ->
            if (silence >= UNIT_SILENCE_WINDOW) {
                actions += PriorityAction(
                    ActionKind.UNIT_WITHOUT_ENQUIRIES,
                    unitNumber = unitNumber,
                    dueIn = UNIT_SILENCE_WINDOW - silence,
                )
            }
        }

        return actions
            .sortedWith(compareBy<PriorityAction> { it.kind.ordinal }.thenBy { it.dueIn })
            .take(MAX_ACTIONS)
    }
}
