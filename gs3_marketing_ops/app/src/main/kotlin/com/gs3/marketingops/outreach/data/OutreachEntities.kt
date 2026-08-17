package com.gs3.marketingops.outreach.data

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.gs3.marketingops.domain.outreach.MessageTemplate

/**
 * A WhatsApp message template.
 *
 * The body is stored per language rather than being one string with the other
 * derived: Arabic is authored, not translated (B5 — Modern Standard Arabic for
 * expatriate and non-Jordanian buyers, light Jordanian dialect for local ones),
 * and a template that reads naturally in one language rarely does so when
 * mapped word-for-word into the other.
 *
 * Placeholder syntax and rendering are `MessageTemplate`'s job in `:domain`,
 * which already refuses to render a template with an unfilled placeholder. This
 * table stores the text and nothing else.
 */
@Entity(tableName = "message_templates")
data class MessageTemplateEntity(
    @PrimaryKey val templateKey: String,
    val bodyAr: String,
    val bodyEn: String,
    val trackKey: String?,
    val isEditable: Boolean = true,
) {
    /** The domain template for the language being written in. */
    fun toDomain(arabic: Boolean): MessageTemplate =
        MessageTemplate(id = templateKey, body = if (arabic) bodyAr else bodyEn)
}

/**
 * A buyer objection and the answer the company stands behind.
 *
 * This exists because the alternative is each salesperson inventing an answer
 * under pressure, and the answers that get invented under pressure are the ones
 * that over-promise. A written library is how a small team says the same true
 * thing twice.
 *
 * **Nothing here may cite the four B-2 contract terms** — the finishing annex,
 * the delay penalty, the warranty, the quarterly progress report — until each
 * has been confirmed against the signed contract. That is enforced by a test,
 * not by whoever writes the next objection remembering.
 */
@Entity(tableName = "objections")
data class ObjectionEntity(
    @PrimaryKey val objectionKey: String,
    val objectionAr: String,
    val objectionEn: String,
    val responseAr: String,
    val responseEn: String,
    val displayOrder: Int,
)
