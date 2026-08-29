package com.gs3.marketingops.domain.outreach

import java.net.URLEncoder
import java.nio.charset.StandardCharsets

/** What to do when a `wa.me` link cannot be opened. */
sealed interface ShareTarget {
    /** WhatsApp is installed: open it with the message pre-filled. */
    data class WhatsApp(val url: String) : ShareTarget

    /**
     * WhatsApp is not installed. The message still exists and is still worth
     * sending, so it goes to the system share sheet rather than crashing or
     * showing a blank screen — which is what the brief warns about.
     */
    data class SystemShareSheet(val text: String) : ShareTarget
}

object WhatsAppLink {

    private const val BASE = "https://wa.me/"

    /**
     * Normalises a phone number to E.164 digits with no leading `+`, no spaces
     * and no dashes — the only form `wa.me` accepts.
     *
     * A number copied from a business card as `+962 79073 0903` or
     * `0790730903` is the common case, and both silently produce a dead link
     * if passed through unchanged. A local number beginning `0` is expanded
     * using the supplied country dialling code, because a Jordanian
     * salesperson typing a local mobile is not going to remember to write it
     * in international form.
     */
    fun normalisePhone(raw: String, defaultCountryCode: String = "962"): String? {
        val trimmed = raw.trim()
        if (trimmed.isEmpty()) return null

        val hadPlus = trimmed.startsWith("+")
        val digits = trimmed.filter { it.isDigit() }
        if (digits.isEmpty()) return null

        val international = when {
            hadPlus -> digits
            digits.startsWith("00") -> digits.removePrefix("00")
            // A national number: 0790730903 -> 962790730903.
            digits.startsWith("0") -> defaultCountryCode + digits.drop(1)
            digits.startsWith(defaultCountryCode) -> digits
            else -> defaultCountryCode + digits
        }

        // E.164 allows at most 15 digits, and a country code is at least one.
        return if (international.length in 8..15) international else null
    }

    /**
     * Builds the deep link. The body is URL-encoded, and `URLEncoder` is not
     * quite enough on its own: it emits `+` for a space, which `wa.me` renders
     * literally as a plus sign, so spaces become `%20`. Arabic text encodes to
     * UTF-8 percent escapes and arrives intact.
     */
    fun deepLink(phone: String, message: String, defaultCountryCode: String = "962"): String? {
        val normalised = normalisePhone(phone, defaultCountryCode) ?: return null
        val encoded = URLEncoder.encode(message, StandardCharsets.UTF_8)
            .replace("+", "%20")
        return "$BASE$normalised?text=$encoded"
    }

    /**
     * The link if the number is usable and WhatsApp is present; otherwise the
     * share sheet with the same text. Never nothing.
     */
    fun shareTarget(
        phone: String,
        message: String,
        whatsAppInstalled: Boolean,
        defaultCountryCode: String = "962",
    ): ShareTarget {
        if (!whatsAppInstalled) return ShareTarget.SystemShareSheet(message)
        val url = deepLink(phone, message, defaultCountryCode)
        return if (url == null) ShareTarget.SystemShareSheet(message) else ShareTarget.WhatsApp(url)
    }
}

/**
 * A message template with `{placeholder}` substitution.
 *
 * Substitution is strict on purpose. A template that renders
 * "the price is {price}" to a client is worse than one that fails loudly in
 * testing, so an unresolved placeholder is reported rather than passed through.
 */
data class MessageTemplate(val id: String, val body: String) {

    fun placeholders(): Set<String> =
        PLACEHOLDER.findAll(body).map { it.groupValues[1] }.toSet()

    fun missingFrom(values: Map<String, String>): Set<String> = placeholders() - values.keys

    /** Renders, or returns null if any placeholder has no value. */
    fun render(values: Map<String, String>): String? {
        if (missingFrom(values).isNotEmpty()) return null
        return PLACEHOLDER.replace(body) { match -> values.getValue(match.groupValues[1]) }
    }

    companion object {
        private val PLACEHOLDER = Regex("""\{([a-z_]+)}""")

        /** The variables every unit-facing template may use. */
        val UNIT_VARIABLES: Set<String> = setOf(
            "unit_number", "area", "price", "external_area", "link", "contact",
        )
    }
}

/**
 * The external-track nurture sequence: what gets sent, and how many days after
 * the enquiry.
 *
 * The app schedules the reminder and pre-fills the text. It never sends
 * anything by itself — every outbound message is a human tapping send. That is
 * a deliberate constraint, not a missing feature: an automated message to a
 * buyer considering a six-figure purchase reads as exactly what it is.
 */
enum class NurtureStep(val dayOffset: Int, val isAutomaticAcknowledgement: Boolean = false) {
    AUTO_ACKNOWLEDGEMENT(0, isAutomaticAcknowledgement = true),
    HUMAN_REPLY(0),
    UNIT_FILE(0),
    PERSONALISED_UNIT_VIDEO(1),
    VALUE_ASSET(3),
    BUYER_TESTIMONIAL(7),
    INVENTORY_STATUS_UPDATE(14),
    WHAT_IS_HOLDING_YOU_BACK(30),
    ;

    companion object {
        val sequence: List<NurtureStep> = entries.sortedBy { it.dayOffset }

        /** Everything a human must send by hand — which is everything but the receipt. */
        val humanSent: List<NurtureStep> = entries.filterNot { it.isAutomaticAcknowledgement }
    }
}
