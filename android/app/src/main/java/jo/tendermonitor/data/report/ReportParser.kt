package jo.tendermonitor.data.report

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Outcome
import jo.tendermonitor.data.Problem
import kotlinx.serialization.json.Json

/**
 * Turning the pipeline's JSON into a [Report], or saying why it could not.
 *
 * The schema check is the point. An older app reading a newer document would
 * render fields that may have changed meaning and look entirely normal doing
 * it -- and the backend's own hard-won rule is that a wrong answer which looks
 * checked is worse than no answer. So a document from the future is refused
 * with a sentence, not parsed hopefully.
 *
 * An OLDER document is accepted: every field this app reads existed at schema
 * 1, and refusing to open a report you already downloaded because it predates
 * an app update would be a self-inflicted outage.
 */
object ReportParser {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        explicitNulls = false
    }

    fun parse(text: String): Outcome<Report> {
        if (text.isBlank()) {
            return Outcome.Failed(
                Problem(
                    headline = "The run's report file was empty",
                    detail = "The artifact contained a report file with nothing in it.",
                    kind = Kind.MALFORMED,
                    fixHint = "This means the run failed before writing its report. " +
                        "The run page will say where.",
                )
            )
        }

        val report = try {
            json.decodeFromString(Report.serializer(), text)
        } catch (error: Exception) {
            return Outcome.Failed(
                Problem(
                    headline = "The report could not be read",
                    detail = error.message?.take(300).orEmpty(),
                    kind = Kind.MALFORMED,
                    fixHint = "The file downloaded but is not the shape this app " +
                        "expects. Nothing is being guessed at.",
                )
            )
        }

        if (report.schema > Report.SUPPORTED_SCHEMA) {
            return Outcome.Failed(
                Problem(
                    headline = "This app is older than the report",
                    detail = "The run wrote schema ${report.schema}; this app " +
                        "understands ${Report.SUPPORTED_SCHEMA}. Fields may have " +
                        "changed meaning, so it is not being rendered.",
                    kind = Kind.MALFORMED,
                    fixHint = "Install the newer APK from the repository's Actions " +
                        "or Releases page.",
                )
            )
        }

        if (report.schema == 0) {
            return Outcome.Failed(
                Problem(
                    headline = "That file is not a tender report",
                    detail = "It parsed as JSON but carries no schema version, so it " +
                        "is not the document this app reads.",
                    kind = Kind.MALFORMED,
                )
            )
        }

        return Outcome.Ok(report)
    }
}
