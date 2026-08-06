package jo.tendermonitor.data.report

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * The report as the pipeline writes it. See jordan_tender_monitor's
 * agents/reporter.py: write_json.
 *
 * TWO FIELDS ARE NULLABLE ON PURPOSE AND MUST STAY THAT WAY.
 *
 * `PortalStatus.scanned` is null when a portal never filters. Rendering it as
 * 0 would collapse "read nothing" and "read 500 notices, none of them Jordan"
 * into the same line, and those need entirely different fixes -- the backend
 * added that number precisely because five identical zeroes could not be told
 * apart.
 *
 * `Opportunity.closingDate` is null when a notice published no deadline. A
 * missing field is not evidence: absent means unknown, never "no deadline".
 */
@Serializable
data class Report(
    val schema: Int = 0,
    @SerialName("generated_at") val generatedAt: String = "",
    val run: RunSummary = RunSummary(),
    @SerialName("tender_count") val tenderCount: Int = 0,
    val tenders: List<Opportunity> = emptyList(),
    val portals: List<PortalStatus> = emptyList(),
) {
    companion object {
        /**
         * The schema this app was written against. A newer document is refused
         * rather than half-rendered: a screen of fields that silently mean
         * something else is worse than a sentence saying the app is out of date.
         */
        const val SUPPORTED_SCHEMA = 1
    }
}

@Serializable
data class RunSummary(
    /** ok | quiet | partial | action_needed */
    val status: String = "",
    @SerialName("status_line") val statusLine: String = "",
    val slug: String = "",
    @SerialName("opportunity_count") val opportunityCount: Int = 0,
    /** Notices read before filtering, across every portal. */
    val scanned: Int = 0,
    @SerialName("merged_duplicates") val mergedDuplicates: Int = 0,
    val dropped: Map<String, Int> = emptyMap(),
    @SerialName("portals_total") val portalsTotal: Int = 0,
    @SerialName("portals_ok") val portalsOk: Int = 0,
    @SerialName("portals_broken") val portalsBroken: Int = 0,
    @SerialName("new_only") val newOnly: Boolean = false,
) {
    val isActionNeeded: Boolean get() = status == "action_needed"
    val isPartial: Boolean get() = status == "partial"
}

@Serializable
data class Opportunity(
    val id: String = "",
    val title: String = "",
    val portal: String = "",
    @SerialName("portal_name") val portalName: String = "",
    val url: String? = null,
    val score: Double = 0.0,
    val sector: String? = null,
    @SerialName("notice_type") val noticeType: String? = null,
    val language: String? = null,
    val flags: List<String> = emptyList(),
    @SerialName("posted_date") val postedDate: String? = null,
    @SerialName("closing_date") val closingDate: String? = null,
    /** Null when there is no deadline to count down to. Never 0 for unknown. */
    @SerialName("days_left") val daysLeft: Int? = null,
    @SerialName("estimated_value_usd") val estimatedValueUsd: Double? = null,
    @SerialName("value_display") val valueDisplay: String = "",
    val eligibility: String? = null,
    val contact: String? = null,
    val description: String? = null,
)

@Serializable
data class PortalStatus(
    val key: String = "",
    val name: String = "",
    val tier: Int = 2,
    @SerialName("tier_label") val tierLabel: String = "",
    /** ok | unavailable | unconfigured | no listing */
    val status: String = "",
    val count: Int = 0,
    /** Null means "this portal never filters" -- NOT zero. See the file header. */
    val scanned: Int? = null,
    val reason: String = "",
    val urls: List<String> = emptyList(),
    val layer: String = "",
    val quality: Double = 0.0,
) {
    val isBroken: Boolean get() = status == "unavailable"
    val isOk: Boolean get() = status == "ok"

    /**
     * How many notices were read but were not Jordan. Null when the portal
     * never filtered, which is a different thing from none.
     */
    val filteredOut: Int? get() = scanned?.let { (it - count).coerceAtLeast(0) }
}
