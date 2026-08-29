package com.gs3.marketingops.compliance.data

import androidx.room.Entity
import androidx.room.PrimaryKey
import java.time.Instant

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
 *
 * **These rows are not about non-Jordanian buyers**, which is why they survived
 * the removal of that track (DECISIONS.md → D-23) while the eligibility gate
 * that used to share this file did not. A finishing annex and a delay penalty
 * are terms of the same signed contract every buyer signs. This file was called
 * `nonjordanian/data/ComplianceEntities.kt`; the package was wrong about it
 * even before the track went.
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

        /**
         * A claim someone has read the signed contract and confirmed.
         *
         * [reference] is nullable because the owner can confirm a term is
         * present without having the clause number to hand, and refusing the
         * confirmation until they do would keep a true statement out of client
         * text for the sake of a citation. It is still worth filling in later:
         * without it the next reader has to ask a person rather than open the
         * contract.
         */
        fun confirmed(
            claim: ContractClaim,
            at: Instant,
            reference: String? = null,
        ) = ContractClaimEntity(
            claim = claim.name,
            confirmedPresent = true,
            contractReference = reference,
            confirmedAt = at,
        )
    }
}
