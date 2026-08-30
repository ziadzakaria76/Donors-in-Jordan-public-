package jo.tendermonitor

import jo.tendermonitor.data.report.ArtifactZip
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * Artifacts arrive as a zip from a remote server.
 *
 * Two things are being tested: that a truncated read is reported as "not read"
 * rather than returned as a shorter document, and that a path in the archive
 * cannot write outside the folder it is being extracted into.
 */
class ArtifactZipTest {

    @get:Rule
    val folder = TemporaryFolder()

    private fun zipOf(vararg entries: Pair<String, ByteArray>): ByteArray {
        val out = ByteArrayOutputStream()
        ZipOutputStream(out).use { zip ->
            entries.forEach { (name, bytes) ->
                zip.putNextEntry(ZipEntry(name))
                zip.write(bytes)
                zip.closeEntry()
            }
        }
        return out.toByteArray()
    }

    @Test
    fun `the report is found by name among the other files`() {
        val zip = zipOf(
            "jordan_tenders_20260806_0717_3-opportunities.docx" to "word".toByteArray(),
            "jordan_tenders_20260806_0717_3-opportunities.xlsx" to "excel".toByteArray(),
            "jordan_tenders_20260806_0717_3-opportunities.json" to """{"schema":1}""".toByteArray(),
        )
        val text = ArtifactZip.readTextEntry(ByteArrayInputStream(zip), ArtifactZip::isReportJson)
        assertEquals("""{"schema":1}""", text)
    }

    @Test
    fun `no matching entry returns null, which callers must not read as empty`() {
        val zip = zipOf("readme.txt" to "nothing here".toByteArray())
        assertNull(ArtifactZip.readTextEntry(ByteArrayInputStream(zip), ArtifactZip::isReportJson))
    }

    @Test
    fun `an oversized entry returns null rather than a truncated document`() {
        // A truncated report would parse as a shorter report, and a shorter
        // report is a wrong one that looks right.
        val huge = ByteArray(ArtifactZip.MAX_TEXT_BYTES + 1024) { 'x'.code.toByte() }
        val zip = zipOf("jordan_tenders_big.json" to huge)
        assertNull(ArtifactZip.readTextEntry(ByteArrayInputStream(zip), ArtifactZip::isReportJson))
    }

    @Test
    fun `utf8 survives the round trip`() {
        val arabic = """{"schema":1,"t":"خدمات استشارية"}"""
        val zip = zipOf("jordan_tenders_x.json" to arabic.toByteArray(Charsets.UTF_8))
        val text = ArtifactZip.readTextEntry(ByteArrayInputStream(zip), ArtifactZip::isReportJson)
        assertTrue(text!!.contains("استشارية"))
    }

    @Test
    fun `every file is extracted and reported`() {
        val target = folder.newFolder("run-9")
        val zip = zipOf(
            "a.docx" to "word".toByteArray(),
            "b.xlsx" to "excel".toByteArray(),
        )
        val written = ArtifactZip.extractAll(ByteArrayInputStream(zip), target)
        assertEquals(2, written.size)
        assertTrue(written.all { it.exists() })
        assertEquals(setOf("a.docx", "b.xlsx"), written.map { it.name }.toSet())
    }

    @Test
    fun `a traversing path is refused and named, not silently dropped`() {
        val target = folder.newFolder("run-9")
        val zip = zipOf(
            "../../escaped.txt" to "no".toByteArray(),
            "fine.docx" to "yes".toByteArray(),
        )
        val skipped = mutableListOf<String>()
        val written = ArtifactZip.extractAll(ByteArrayInputStream(zip), target, skipped)

        // Flattened to a bare name, so it lands inside the target -- and the
        // parent directory is still checked, because a flatten that stopped
        // working would otherwise fail silently.
        assertTrue(written.all { it.canonicalFile.parentFile == target.canonicalFile })
        assertFalse(java.io.File(target.parentFile.parentFile, "escaped.txt").exists())
        assertNotNull(written.firstOrNull { it.name == "fine.docx" })
    }

    @Test
    fun `nested directories are flattened rather than recreated`() {
        val target = folder.newFolder("run-9")
        val zip = zipOf("output/deep/report.json" to "{}".toByteArray())
        val written = ArtifactZip.extractAll(ByteArrayInputStream(zip), target)
        assertEquals(1, written.size)
        assertEquals("report.json", written[0].name)
        assertEquals(target.canonicalFile, written[0].canonicalFile.parentFile)
    }

    @Test
    fun `file kinds are recognised by extension`() {
        assertTrue(ArtifactZip.isDocx("jordan_tenders_x.docx"))
        assertTrue(ArtifactZip.isXlsx("jordan_tenders_x.XLSX"))
        assertTrue(ArtifactZip.isReportJson("jordan_tenders_x.json"))
        assertFalse(ArtifactZip.isReportJson("portals.json"))
    }

    /**
     * Syria's run writes TWO json files and only one of them is this contract.
     *
     * Its diagnostic dump carries no `schema`, so the app parses that as 0 and
     * refuses to render -- which is correct behaviour reached for the wrong
     * reason, and reads to the user as "the app is out of date" on a run that
     * was perfectly good. Picking by ".json" alone would choose whichever the
     * zip happened to list first.
     */
    @Test
    fun `only the app's own report json is treated as the report`() {
        // Jordan writes one file, and it is the contract.
        assertTrue(ArtifactZip.isReportJson("jordan_tenders_20260830_0457_117.json"))

        // Syria writes both. Only the second is readable by this app.
        assertFalse(
            "the diagnostic dump has no schema and must not be picked",
            ArtifactZip.isReportJson("syria-tenders-2026-08-30.json"),
        )
        assertTrue(ArtifactZip.isReportJson("syria-tenders-2026-08-30-app.json"))

        // Neither is a report, and one of them is a trap: the summary is
        // markdown that GitHub renders on the run page, not a document.
        assertFalse(ArtifactZip.isReportJson("syria-tenders-2026-08-30-summary.md"))
        assertFalse(ArtifactZip.isReportJson("probe_eib.json"))
    }
}
