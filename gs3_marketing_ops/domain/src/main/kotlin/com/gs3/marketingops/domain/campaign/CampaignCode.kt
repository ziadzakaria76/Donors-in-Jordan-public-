package com.gs3.marketingops.domain.campaign

import com.gs3.marketingops.domain.funnel.Track
import java.net.URLEncoder
import java.nio.charset.StandardCharsets

enum class Objective { AWR, ENG, CONV }

/** Where the money is spent, and the UTM medium each implies. */
enum class Platform(val utmSource: String, val utmMedium: String) {
    META("meta", "paid_social"),
    GOOGLE("google", "cpc"),
    YOUTUBE("youtube", "video"),
    SNAPCHAT("snapchat", "paid_social"),
    TIKTOK("tiktok", "paid_social"),
    OPENSOOQ("opensooq", "listing"),
    BAYUT("bayut", "listing"),
}

/**
 * One campaign, described once.
 *
 * The code and the UTM parameters are both derived from this single object, and
 * that is the entire point of the type. When a code is typed into the ad
 * platform and the UTMs are typed into the landing-page URL separately, they
 * drift within a fortnight — and then the spend sits under one name while the
 * leads arrive under another, and cost per lead becomes unknowable for the rest
 * of the campaign. Deriving both from one source makes that impossible.
 */
data class CampaignSpec(
    val track: Track,
    val market: String,
    val objective: Objective,
    val audience: String,
    val format: String,
    val version: Int,
    val platform: Platform,
) {
    init {
        require(version >= 1) { "Campaign version starts at 1, was $version" }
        listOf("market" to market, "audience" to audience, "format" to format).forEach { (field, value) ->
            require(value.isNotBlank()) { "Campaign $field cannot be blank" }
            require(!value.contains(SEPARATOR)) { "Campaign $field cannot contain '$SEPARATOR': $value" }
            require(value.none { it.isWhitespace() }) { "Campaign $field cannot contain spaces: $value" }
        }
    }

    /** `GS3-EXPAT-UAE-CONV-LAL2-Reel30s-v3` */
    val code: String
        get() = listOf(PREFIX, track.name, market.uppercase(), objective.name, audience, format, "v$version")
            .joinToString(SEPARATOR)

    fun utmParameters(): Map<String, String> = linkedMapOf(
        "utm_source" to platform.utmSource,
        "utm_medium" to platform.utmMedium,
        "utm_campaign" to code.lowercase(),
        "utm_content" to listOf(audience, format, "v$version").joinToString("-").lowercase(),
    )

    /** The tagged landing-page URL, ready to paste into the ad platform. */
    fun taggedUrl(baseUrl: String = DEFAULT_LANDING_PAGE): String {
        val query = utmParameters().entries.joinToString("&") { (key, value) ->
            "$key=${URLEncoder.encode(value, StandardCharsets.UTF_8)}"
        }
        val joiner = if (baseUrl.contains('?')) "&" else "?"
        return "$baseUrl$joiner$query"
    }

    companion object {
        const val PREFIX = "GS3"
        const val SEPARATOR = "-"
        const val DEFAULT_LANDING_PAGE = "https://general-sherman-housing.com/"

        /** Reads a code back, so an existing campaign can be edited rather than retyped. */
        fun parse(code: String): CampaignSpec? {
            val parts = code.split(SEPARATOR)
            if (parts.size != 7 || parts[0] != PREFIX) return null
            val track = Track.entries.firstOrNull { it.name == parts[1] } ?: return null
            val objective = Objective.entries.firstOrNull { it.name == parts[3] } ?: return null
            val version = parts[6].removePrefix("v").toIntOrNull() ?: return null
            return CampaignSpec(
                track = track,
                market = parts[2],
                objective = objective,
                audience = parts[4],
                format = parts[5],
                version = version,
                // The code carries no platform — it never has. A parsed spec
                // defaults to Meta and the caller sets the real one; the code
                // round-trips regardless, because platform does not appear in it.
                platform = Platform.META,
            )
        }
    }
}
