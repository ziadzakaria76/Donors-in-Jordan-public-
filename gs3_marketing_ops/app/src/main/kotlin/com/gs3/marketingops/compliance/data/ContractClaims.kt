package com.gs3.marketingops.compliance.data

import androidx.room.Entity
import androidx.room.PrimaryKey
import java.time.Instant

/**
 * The contract terms the marketing material may point at.
 *
 * B-2 asked whether the signed contract actually contains each of these. Both
 * survivors are **confirmed present** by the owner (2026-08-29), so both may
 * appear in a WhatsApp template, a share card or ad copy.
 *
 * They are **separate rows on purpose**, not one flag. A single "contract
 * verified" switch would force the team to choose between over-claiming and
 * under-claiming the moment the answers differed — which is exactly what
 * happened when B-2 came back answered in part.
 *
 * **There were four.** The delay penalty and the two-year/ten-year warranty
 * were the two nobody had verified, and on 2026-08-30 the owner removed them
 * along with the guard that kept them out of client-facing text. Nothing now
 * stops a template or an objection promising either, so the signed contract is
 * the only thing behind such a sentence. Anything added here in future starts
 * unconfirmed and should stay out of client text until someone has read the
 * contract.
 *
 * **These rows are not about non-Jordanian buyers**, which is why they survived
 * the removal of that track (DECISIONS.md → D-23) while the eligibility gate
 * that used to share this file did not. A finishing annex is a term of the same
 * signed contract every buyer signs. This file was called
 * `nonjordanian/data/ComplianceEntities.kt`; the package was wrong about it
 * even before the track went.
 */
enum class ContractClaim {
    /** A finishing-specifications annex, named and attached. Confirmed 2026-08-29. */
    FINISHING_SPECIFICATIONS_ANNEX,

    /** A quarterly photographic progress report. Confirmed 2026-08-29. */
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
