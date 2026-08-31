package jo.tendermonitor

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.ReportRepository
import jo.tendermonitor.data.github.Artifact
import jo.tendermonitor.data.github.WorkflowRun
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Which artifact a run's files come from, and what to say when there are none.
 *
 * Both of these existed twice and the copies disagreed. fetchReport knew that
 * Syria uploads "syria-tender-report-N"; downloadFiles still demanded the
 * Jordan prefix, so the Files tab answered "No artifact named jordan-tenders-*
 * was uploaded" for a Syria run that was perfectly fine. These tests exist so
 * the two screens cannot drift apart again.
 */
class ReportArtifactTest {

    private fun artifact(name: String) = Artifact(id = 1L, name = name)

    private fun run(status: String?, conclusion: String? = null) =
        WorkflowRun(id = 1L, runNumber = 20, status = status, conclusion = conclusion)

    @Test
    fun `Jordan's pack is found by its exact name`() {
        val picked = ReportRepository.reportArtifact(listOf(artifact("jordan-tenders-117")))
        assertEquals("jordan-tenders-117", picked?.name)
    }

    @Test
    fun `Syria's pack is found although it is named nothing like Jordan's`() {
        // The whole bug: this is what a Syria run uploads.
        val picked = ReportRepository.reportArtifact(listOf(artifact("syria-tender-report-20")))
        assertEquals("syria-tender-report-20", picked?.name)
    }

    @Test
    fun `Jordan wins over another tender artifact rather than the list order deciding`() {
        val picked = ReportRepository.reportArtifact(
            listOf(artifact("syria-tender-report-20"), artifact("jordan-tenders-117")),
        )
        assertEquals("jordan-tenders-117", picked?.name)
    }

    @Test
    fun `an unrecognised name is still returned, because one artifact is the pack`() {
        val picked = ReportRepository.reportArtifact(listOf(artifact("build-output")))
        assertEquals("build-output", picked?.name)
    }

    @Test
    fun `no artifacts is null, which callers must not read as an empty pack`() {
        assertNull(ReportRepository.reportArtifact(emptyList()))
    }

    @Test
    fun `a run still going is not a run that produced nothing`() {
        // Tapping Files mid-run used to blame a missing Jordan-named artifact:
        // a cause that is not the cause, pointing at a fix that does not exist.
        val problem = ReportRepository.noArtifacts(run(status = "in_progress"))
        assertEquals("This run has not finished", problem.headline)
        assertTrue(problem.detail.contains("in_progress"))
        assertTrue(problem.fixHint.orEmpty().contains("Wait"))
    }

    @Test
    fun `a finished run that uploaded nothing says so, and says why it might have`() {
        val problem = ReportRepository.noArtifacts(run(status = "completed", conclusion = "failure"))
        assertEquals("This run produced no files", problem.headline)
        assertEquals(Kind.NOT_FOUND, problem.kind)
        assertTrue(problem.fixHint.orEmpty().contains("log"))
    }

    @Test
    fun `a finished successful run with no files points at the retention window`() {
        val problem = ReportRepository.noArtifacts(run(status = "completed", conclusion = "success"))
        assertTrue(problem.fixHint.orEmpty().contains("90 days"))
    }
}
