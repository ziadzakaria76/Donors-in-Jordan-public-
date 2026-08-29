package jo.tendermonitor.data.portals

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * What a `--probe` run found, as `jordan_tender_monitor/probe.py` writes it.
 *
 * The document exists so that adding a portal from a phone is not a guess. It
 * carries three things the app must not summarise away:
 *
 *  * **the verdict in words**, because "0.71" says nothing about what to do;
 *  * **every layer's row count and score**, so a portal that half-worked is
 *    visibly different from one that did not work at all;
 *  * **sample rows, even from a layer that was rejected.** A layer that found
 *    15 rows at 0.12 has found something, and whether those rows are notices
 *    missing their dates or navigation dressed as opportunities is not a
 *    question a score can answer.
 */
@Serializable
data class ProbeReport(
    val schema: Int = 0,
    @SerialName("generated_at") val generatedAt: String = "",
    @SerialName("quality_threshold") val qualityThreshold: Double = 0.36,
    /** Loader objections. Non-empty means nothing was fetched. */
    val rejected: List<String> = emptyList(),
    val sources: List<ProbeSource> = emptyList(),
    val verdict: ProbeVerdict = ProbeVerdict(),
) {
    companion object {
        const val SUPPORTED_SCHEMA = 1
    }

    val wouldBeRejected: Boolean get() = rejected.isNotEmpty()
}

@Serializable
data class ProbeVerdict(
    val usable: Boolean = false,
    val headline: String = "",
    val detail: String = "",
    val advice: String = "",
)

@Serializable
data class ProbeSource(
    val url: String = "",
    val fetched: Boolean = false,
    val bytes: Int = 0,
    val error: String = "",
    val layers: List<ProbeLayer> = emptyList(),
    val winner: String = "",
    @SerialName("winning_rows") val winningRows: Int = 0,
    @SerialName("winning_quality") val winningQuality: Double = 0.0,
    @SerialName("best_rows") val bestRows: Int = 0,
    @SerialName("best_quality") val bestQuality: Double = 0.0,
    /** Why the page carried no listing, in the run's own words. */
    val diagnosis: String = "",
    @SerialName("sample_rows") val sampleRows: List<ProbeRow> = emptyList(),
    @SerialName("sample_from") val sampleFrom: String = "",
    /** True when the sample came from a layer the quality gate rejected. */
    @SerialName("sample_rejected") val sampleRejected: Boolean = false,
)

@Serializable
data class ProbeLayer(
    val layer: String = "",
    val rows: Int = 0,
    val quality: Double = 0.0,
    val note: String = "",
    val wins: Boolean = false,
)

@Serializable
data class ProbeRow(
    val title: String = "",
    val url: String? = null,
    @SerialName("posted_text") val postedText: String? = null,
    @SerialName("closing_text") val closingText: String? = null,
    @SerialName("value_text") val valueText: String? = null,
    val reference: String? = null,
    /** What the date and value parsers actually see. */
    @SerialName("raw_text") val rawText: String = "",
)
