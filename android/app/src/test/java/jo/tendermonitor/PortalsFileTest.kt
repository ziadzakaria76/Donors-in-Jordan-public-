package jo.tendermonitor

import jo.tendermonitor.data.portals.EntryRules
import jo.tendermonitor.data.portals.PortalsFile
import jo.tendermonitor.data.portals.PortalsRepository
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Editing portals.json without destroying it.
 *
 * The failure this class exists to prevent is not a crash. It is a successful
 * save that quietly drops the `notes` explaining why KfW points at GTAI, the
 * `no_listing_reason` that keeps ADFD out of the red, or the `_readme` block at
 * the top of the file. Those would look exactly like a working commit, and the
 * loss would only surface months later when someone asked why a portal was
 * configured that way.
 */
class PortalsFileTest {

    private val realish = """
        {
          "version": 1,
          "_readme": [
            "The portal list. Validated on load by portal_config.py."
          ],
          "portals": [
            {
              "key": "ungm",
              "name": "UNGM",
              "enabled": true,
              "tier": 2,
              "module": "ungm",
              "urls": ["https://www.ungm.org/Public/Notice"],
              "code_owned": ["selectors", "field_selectors", "filter_to_jordan"],
              "anchor_hint": "/Public/Notice/",
              "currency": "USD",
              "notes": "The richest Jordan source. Its rows come from a POST search endpoint."
            },
            {
              "key": "kfw",
              "name": "KfW (via Germany Trade & Invest)",
              "enabled": true,
              "tier": 2,
              "urls": ["https://www.gtai.de/en/trade/tenders"],
              "selectors": ["div.gtai-teaser", "article.teaser"],
              "anchor_hint": "/tenders/",
              "currency": "EUR",
              "filter_to_jordan": true,
              "notes": "KfW does NOT publish tender notices on kfw.de."
            },
            {
              "key": "jica",
              "name": "JICA",
              "enabled": true,
              "tier": 3,
              "urls": ["https://www.jica.go.jp/x/procurement.html"],
              "filter_to_jordan": false,
              "no_listing_reason": "JICA's Jordan office has no procurement page."
            }
          ]
        }
    """.trimIndent()

    @Test
    fun `entries are read with the fields the app renders`() {
        val document = PortalsFile.parse(realish)
        assertEquals(3, document.entries.size)

        val ungm = document.entries[0]
        assertEquals("UNGM", ungm.name)
        assertTrue(ungm.enabled)
        assertEquals(2, ungm.tier)
        assertTrue(ungm.isCodeBacked)
        assertEquals(
            listOf("selectors", "field_selectors", "filter_to_jordan"),
            ungm.codeOwned,
        )

        val kfw = document.entries[1]
        assertTrue(kfw.isDataOnly)
        assertEquals(2, kfw.selectors.size)
        assertTrue(kfw.notes.contains("does NOT publish"))

        val jica = document.entries[2]
        assertTrue(jica.noListingReason.contains("no procurement page"))
    }

    @Test
    fun `toggling one portal changes nothing else in the file`() {
        val document = PortalsFile.parse(realish)
        val updated = PortalsFile.withEnabled(document.root, "kfw", false)
        val text = PortalsFile.serialise(updated)

        // The prose is the most valuable thing in this file and a typed
        // round-trip would have deleted every line of it.
        assertTrue("lost the readme", text.contains("Validated on load"))
        assertTrue("lost KfW's note", text.contains("does NOT publish tender notices"))
        assertTrue("lost UNGM's note", text.contains("POST search endpoint"))
        assertTrue("lost code_owned", text.contains("field_selectors"))
        assertTrue("lost no_listing_reason", text.contains("no procurement page"))
        assertTrue("lost version", text.contains("\"version\""))

        val reread = PortalsFile.parse(text)
        assertEquals(3, reread.entries.size)
        assertFalse(reread.entries.first { it.key == "kfw" }.enabled)
        assertTrue(reread.entries.first { it.key == "ungm" }.enabled)
    }

    @Test
    fun `an unknown field on an entry survives an edit`() {
        // The app must be able to edit a file written by a newer pipeline
        // without silently discarding what it does not model.
        val withFuture = realish.replace(
            """"key": "kfw",""",
            """"key": "kfw", "a_field_from_the_future": {"nested": [1, 2]},"""
        )
        val document = PortalsFile.parse(withFuture)
        val text = PortalsFile.serialise(
            PortalsFile.withEnabled(document.root, "kfw", false)
        )
        assertTrue(text.contains("a_field_from_the_future"))
        assertTrue(text.contains("nested"))
    }

    @Test
    fun `removing a portal removes exactly one`() {
        val document = PortalsFile.parse(realish)
        val text = PortalsFile.serialise(PortalsFile.withRemoved(document.root, "jica"))
        val reread = PortalsFile.parse(text)

        assertEquals(2, reread.entries.size)
        assertTrue(reread.entries.none { it.key == "jica" })
        assertTrue(reread.entries.any { it.key == "ungm" })
        assertTrue("lost KfW's note", text.contains("does NOT publish"))
    }

    @Test
    fun `a new portal is appended rather than sorted in`() {
        // The file's order is the order portals are polled and reported.
        // Reordering thirteen lines to insert one makes the diff unreadable,
        // and that diff is what someone checks when a run goes wrong.
        val document = PortalsFile.parse(realish)
        val entry = PortalsFile.buildEntry(
            key = "aaafirst", name = "Alphabetically First",
            urls = listOf("https://example.org/tenders"),
        )
        val reread = PortalsFile.parse(
            PortalsFile.serialise(PortalsFile.withAdded(document.root, entry))
        )
        assertEquals(4, reread.entries.size)
        assertEquals("aaafirst", reread.entries.last().key)
        assertEquals("ungm", reread.entries.first().key)
    }

    @Test
    fun `a built entry omits optional fields rather than writing them empty`() {
        val entry = PortalsFile.buildEntry(
            key = "example", name = "Example",
            urls = listOf("https://example.org/tenders"),
        )
        val keys = entry.keys
        assertTrue(keys.contains("key"))
        assertTrue(keys.contains("urls"))
        assertTrue(keys.contains("filter_to_jordan"))
        assertFalse("an empty anchor_hint would be noise in a file meant to be read",
                    keys.contains("anchor_hint"))
        assertFalse(keys.contains("currency"))
        assertFalse(keys.contains("selectors"))
        assertFalse(keys.contains("notes"))
    }

    @Test
    fun `a built entry keeps the optional fields that were filled in`() {
        val entry = PortalsFile.buildEntry(
            key = "example", name = "Example",
            urls = listOf("https://example.org/a", "https://example.org/b"),
            tier = 3,
            selectors = listOf("div.tender"),
            anchorHint = "/tenders/",
            currency = "EUR",
            filterToJordan = false,
            notes = "Why this is here.",
        )
        val text = PortalsFile.serialise(
            PortalsFile.withAdded(PortalsFile.parse(realish).root, entry)
        )
        val added = PortalsFile.parse(text).entries.last()
        assertEquals(listOf("https://example.org/a", "https://example.org/b"), added.urls)
        assertEquals(3, added.tier)
        assertEquals(listOf("div.tender"), added.selectors)
        assertEquals("Why this is here.", added.notes)
        assertTrue(text.contains("\"filter_to_jordan\": false"))
    }

    @Test
    fun `a file this app does not recognise is refused rather than rewritten`() {
        for (bad in listOf("[]", "{\"something\": 1}", "not json at all")) {
            try {
                PortalsFile.parse(bad)
                org.junit.Assert.fail("should have refused: $bad")
            } catch (expected: PortalsFile.MalformedException) {
                assertNotNull(expected.message)
            }
        }
    }

    @Test
    fun `hasKey finds an existing portal`() {
        val root = PortalsFile.parse(realish).root
        assertTrue(PortalsFile.hasKey(root, "ungm"))
        assertFalse(PortalsFile.hasKey(root, "nonesuch"))
    }

    @Test
    fun `the serialised file ends with a newline`() {
        // Every other file in the repository does. A commit that flips it is
        // noise in a diff that should be about a portal.
        val text = PortalsFile.serialise(PortalsFile.parse(realish).root)
        assertTrue(text.endsWith("\n"))
    }
}

/**
 * The rules that stop a bad entry becoming a commit.
 *
 * They mirror portal_config.py deliberately. The backend still decides -- but
 * an entry that would be rejected on load must not reach the repository,
 * because a commit that breaks tomorrow's run is worse than a form that says
 * no today.
 */
class EntryRulesTest {

    private val existing = listOf("ungm", "kfw")

    @Test
    fun `a key must be usable as a CLI argument and a filename`() {
        assertNotNull(EntryRules.keyProblem("", existing))
        assertNotNull(EntryRules.keyProblem("Bad Key", existing))
        assertNotNull(EntryRules.keyProblem("UPPER", existing))
        assertNotNull(EntryRules.keyProblem("_leading", existing))
        assertNull(EntryRules.keyProblem("example", existing))
        assertNull(EntryRules.keyProblem("example-2_b", existing))
    }

    @Test
    fun `a duplicate key is named rather than silently overwriting`() {
        val problem = EntryRules.keyProblem("ungm", existing)
        assertNotNull(problem)
        assertTrue(problem!!.contains("already used"))
    }

    @Test
    fun `a portal with no source is refused`() {
        val problem = EntryRules.urlProblem(emptyList())
        assertNotNull(problem)
        assertTrue(problem!!.contains("broken on every run"))
    }

    @Test
    fun `only http and https are accepted`() {
        assertNotNull(EntryRules.urlProblem(listOf("ftp://example.org")))
        assertNotNull(EntryRules.urlProblem(listOf("javascript:alert(1)")))
        assertNotNull(EntryRules.urlProblem(listOf("example.org/tenders")))
        assertNull(EntryRules.urlProblem(listOf("https://example.org/tenders")))
        assertNull(EntryRules.urlProblem(listOf("http://example.org/tenders")))
    }

    @Test
    fun `the tier must be one the report understands`() {
        assertNull(EntryRules.tierProblem(1))
        assertNull(EntryRules.tierProblem(3))
        assertNotNull(EntryRules.tierProblem(0))
        assertNotNull(EntryRules.tierProblem(9))
    }
}

/**
 * Which country's portal file the app edits.
 *
 * The Portals screen commits through the Contents API, and `PATH` was a
 * constant while `workflowFile` was a setting -- so with Settings pointed at
 * the Syria monitor the screen read Jordan's list, showed Jordan's portals as
 * though they were the running monitor's, and a save rewrote the OTHER
 * country's configuration. A commit that lands, on the wrong file, reads as
 * success.
 */
class PortalsFilePathTest {

    @Test
    fun `the Jordan monitor edits the Jordan portal file`() {
        assertEquals(
            "jordan_tender_monitor/portals.json",
            PortalsFile.pathFor("monitor.yml"),
        )
    }

    @Test
    fun `a workflow given with its directory still resolves`() {
        assertEquals(
            PortalsFile.PATH,
            PortalsFile.pathFor(".github/workflows/monitor.yml"),
        )
    }

    @Test
    fun `the Syria monitor has no editable portal file, and does not borrow Jordan's`() {
        // Syria's portals live in syria_tender_monitor/config.yml, which this
        // file's schema cannot describe. Null is the honest answer; falling
        // back to PATH is the bug.
        assertNull(
            PortalsFile.pathFor("syria-monitor.yml"),
        )
    }

    @Test
    fun `an unknown or blank workflow is refused rather than defaulted`() {
        assertNull(PortalsFile.pathFor("other.yml"))
        assertNull(PortalsFile.pathFor(""))
    }

    @Test
    fun `the refusal names both the file it edits and the workflow in use`() {
        val problem = PortalsRepository.notThisMonitorsFile("syria-monitor.yml")
        assertTrue(problem.detail.contains("jordan_tender_monitor/portals.json"))
        assertTrue(problem.detail.contains("syria-monitor.yml"))
        assertTrue(problem.fixHint.orEmpty().contains("monitor.yml"))
    }
}
