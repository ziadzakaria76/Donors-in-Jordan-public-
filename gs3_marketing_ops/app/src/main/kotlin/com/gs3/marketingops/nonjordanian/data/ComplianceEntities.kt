package com.gs3.marketingops.nonjordanian.data

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.gs3.marketingops.domain.nonjordanian.EligibilityGate
import java.time.Instant

/**
 * The non-Jordanian eligibility gate, persisted.
 *
 * Exactly one row, and [SINGLETON_ID] is what keeps it that way — a second row
 * would mean two answers to a question that has one answer, and whichever the
 * query happened to return first would decide whether a module is locked.
 *
 * The *rule* is not here. `EligibilityGate` in `:domain` decides what clears the
 * gate and what a cleared gate permits, and it is tested there. This table only
 * remembers the answer.
 *
 * Seeded unconfirmed, because B-1 is unanswered. That is not a placeholder to
 * be tidied up later: it is the correct state, and it is what keeps the module
 * locked and `NONJO` campaigns unstartable until someone has the Department's
 * statement and a lawyer's opinion in hand.
 */
@Entity(tableName = "eligibility_gate")
data class EligibilityGateEntity(
    @PrimaryKey val id: Int = SINGLETON_ID,
    val landsAndSurveyStatementObtained: Boolean = false,
    val lawyerOpinionObtained: Boolean = false,
    val reference: String = "",
    val clearedAt: Instant? = null,
) {
    fun toDomain(): EligibilityGate = EligibilityGate(
        landsAndSurveyStatementObtained = landsAndSurveyStatementObtained,
        lawyerOpinionObtained = lawyerOpinionObtained,
        reference = reference,
        clearedAt = clearedAt,
    )

    internal companion object {
        const val SINGLETON_ID: Int = 1

        fun fromDomain(gate: EligibilityGate): EligibilityGateEntity = EligibilityGateEntity(
            landsAndSurveyStatementObtained = gate.landsAndSurveyStatementObtained,
            lawyerOpinionObtained = gate.lawyerOpinionObtained,
            reference = gate.reference,
            clearedAt = gate.clearedAt,
        )
    }
}

/**
 * The four contract terms the marketing material would like to promise.
 *
 * B-2 asks whether the signed contract actually contains each of these. Until
 * someone has read the contract and said so, none of them may appear in a
 * WhatsApp template, a share card or ad copy — the app must not put a promise
 * in front of a client that the contract does not carry.
 *
 * They are **four separate rows on purpose**, not one flag. If three turn out
 * to be in the contract and one does not, three can be used and only the
 * missing one stays out. A single "contract verified" switch would force the
 * team to choose between over-claiming and under-claiming.
 */
enum class ContractClaim {
    /** A finishing-specifications annex, named and attached. */
    FINISHING_SPECIFICATIONS_ANNEX,

    /** A delay penalty payable to the buyer. */
    DELAY_PENALTY_IN_BUYERS_FAVOUR,

    /** Two-year finishing and ten-year structural warranty. */
    TWO_YEAR_AND_TEN_YEAR_WARRANTY,

    /** A quarterly photographic progress report. */
    QUARTERLY_PHOTOGRAPHIC_PROGRESS_REPORT,
}

@Entity(tableName = "contract_claims")
data class ContractClaimEntity(
    @PrimaryKey val claim: String,

    /**
     * False until someone has read the signed contract and confirmed this
     * specific term is in it. False therefore means "not verified", never
     * "verified absent" — both keep the claim out of client-facing text, and
     * the distinction only matters to whoever is chasing the answer.
     */
    val confirmedPresent: Boolean = false,

    /** Clause or annex number, so a later reader can check without asking. */
    val contractReference: String? = null,
    val confirmedAt: Instant? = null,
) {
    val claimType: ContractClaim get() = ContractClaim.valueOf(claim)

    internal companion object {
        fun unverified(claim: ContractClaim) = ContractClaimEntity(claim = claim.name)
    }
}
