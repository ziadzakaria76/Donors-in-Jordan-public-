package jo.tendermonitor

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Outcome
import jo.tendermonitor.data.report.Report
import jo.tendermonitor.data.report.ReportParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Reading the pipeline's report.
 *
 * The properties under test are the ones that would let the app say something
 * untrue: a null rendered as a zero, a newer document parsed hopefully, an
 * empty report and a broken run looking the same.
 */
class ReportParserTest {

    private fun report(
        status: String = "ok",
        schema: Int = 1,
        tenders: String = "[]",
        portals: String = "[]",
    ) = """
        {
          "schema": $schema,
          "generated_at": "2026-08-06T07:20:00",
          "run": {
            "status": "$status",
            "status_line": "3 new opportunities found. All 13 portals were read successfully.",
            "slug": "3-opportunities",
            "opportunity_count": 3,
            "scanned": 812,
            "merged_duplicates": 1,
            "dropped": {"closed": 12},
            "portals_total": 13,
            "portals_ok": 13,
            "portals_broken": 0,
            "new_only": false
          },
          "tender_count": 3,
          "tenders": $tenders,
          "portals": $portals
        }
    """.trimIndent()

    @Test
    fun `a well formed report parses with its counts intact`() {
        val parsed = ReportParser.parse(report())
        val value = (parsed as Outcome.Ok).value
        assertEquals(1, value.schema)
        assertEquals(812, value.run.scanned)
        assertEquals(1, value.run.mergedDuplicates)
        assertEquals(12, value.run.dropped["closed"])
    }

    @Test
    fun `a newer schema is refused rather than half rendered`() {
        // A wrong answer that looks checked is worse than no answer: fields
        // can change meaning between schema versions and nothing on screen
        // would say so.
        val parsed = ReportParser.parse(report(schema = 2))
        val problem = (parsed as Outcome.Failed).problem
        assertEquals(Kind.MALFORMED, problem.kind)
        assertTrue(problem.headline.contains("older than the report"))
        assertTrue(problem.fixHint!!.contains("newer APK"))
    }

    @Test
    fun `a document with no schema is not treated as a report`() {
        val parsed = ReportParser.parse("""{"hello":"world"}""")
        assertTrue(parsed is Outcome.Failed)
        assertEquals(Kind.MALFORMED, (parsed as Outcome.Failed).problem.kind)
    }

    @Test
    fun `an empty file is diagnosed as an empty file`() {
        val parsed = ReportParser.parse("")
        val problem = (parsed as Outcome.Failed).problem
        assertTrue(problem.headline.contains("empty"))
        assertTrue(problem.fixHint!!.contains("failed before writing"))
    }

    @Test
    fun `malformed json says so instead of throwing`() {
        val parsed = ReportParser.parse("""{"schema": 1, "run": """)
        assertTrue(parsed is Outcome.Failed)
        assertEquals(Kind.MALFORMED, (parsed as Outcome.Failed).problem.kind)
    }

    @Test
    fun `a null scanned stays null and never becomes zero`() {
        // The distinction five identical zeroes could not make: a portal that
        // read nothing and one that read 500 worldwide notices, none of them
        // Jordan, need entirely different fixes.
        val portals = """
            [{"key":"a","name":"Never filters","status":"ok","count":0,"scanned":null},
             {"key":"b","name":"Filtered","status":"ok","count":0,"scanned":500}]
        """.trimIndent()
        val value = (ReportParser.parse(report(portals = portals)) as Outcome.Ok).value

        assertNull(value.portals[0].scanned)
        assertNull(value.portals[0].filteredOut)
        assertEquals(500, value.portals[1].scanned)
        assertEquals(500, value.portals[1].filteredOut)
    }

    @Test
    fun `a missing scanned field is also null, not zero`() {
        val portals = """[{"key":"a","name":"A","status":"ok","count":0}]"""
        val value = (ReportParser.parse(report(portals = portals)) as Outcome.Ok).value
        assertNull(value.portals[0].scanned)
    }

    @Test
    fun `an undated notice has a null deadline and null days left`() {
        // Absent means unknown, never "no deadline". A 0 here would render as
        // "closes today" on the most urgent-looking row in the list.
        val tenders = """
            [{"id":"1","title":"Advisory services","portal":"ungm",
              "portal_name":"UNGM","score":61.4,"flags":["Deadline not published"],
              "closing_date":null,"days_left":null,"value_display":"Not published"}]
        """.trimIndent()
        val value = (ReportParser.parse(report(tenders = tenders)) as Outcome.Ok).value
        assertNull(value.tenders[0].closingDate)
        assertNull(value.tenders[0].daysLeft)
        assertEquals(1, value.tenders[0].flags.size)
    }

    @Test
    fun `a notice with no url parses rather than inventing one`() {
        val tenders = """
            [{"id":"1","title":"No link published","portal":"worldbank",
              "portal_name":"World Bank","score":40.0}]
        """.trimIndent()
        val value = (ReportParser.parse(report(tenders = tenders)) as Outcome.Ok).value
        assertNull(value.tenders[0].url)
    }

    @Test
    fun `a quiet run and a broken run are distinguishable after parsing`() {
        val quiet = (ReportParser.parse(report(status = "quiet")) as Outcome.Ok).value
        val dead = (ReportParser.parse(report(status = "action_needed")) as Outcome.Ok).value
        assertFalse(quiet.run.isActionNeeded)
        assertTrue(dead.run.isActionNeeded)
    }

    @Test
    fun `an older schema is still accepted`() {
        // Refusing to open a report already on the device because it predates
        // an app update would be a self-inflicted outage.
        assertTrue(ReportParser.parse(report(schema = 1)) is Outcome.Ok)
        assertEquals(1, Report.SUPPORTED_SCHEMA)
    }

    @Test
    fun `arabic survives parsing`() {
        val tenders = """
            [{"id":"1","title":"خدمات استشارية لتطوير القطاع المالي",
              "portal":"sfd","portal_name":"Saudi Fund","score":55.0,
              "language":"ar","flags":["Arabic-language notice"]}]
        """.trimIndent()
        val value = (ReportParser.parse(report(tenders = tenders)) as Outcome.Ok).value
        assertTrue(value.tenders[0].title.contains("استشارية"))
        assertEquals("ar", value.tenders[0].language)
    }

    @Test
    fun `unknown fields from a future pipeline do not break a same-schema report`() {
        val tenders = """
            [{"id":"1","title":"T","portal":"p","portal_name":"P","score":1.0,
              "a_field_added_later":"whatever"}]
        """.trimIndent()
        assertTrue(ReportParser.parse(report(tenders = tenders)) is Outcome.Ok)
    }
}
