package jo.tendermonitor

import android.content.Context
import androidx.room.Room
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import jo.tendermonitor.data.db.CachedReport
import jo.tendermonitor.data.db.ReportDao
import jo.tendermonitor.data.db.TenderDatabase
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The cache, against real SQLite.
 *
 * Room writes the SQL at build time and does not check it until it runs. A
 * wrong ORDER BY, a LIMIT that trims the wrong end, a @Transaction that is not
 * one -- all of these compile, and all of them fail only against a real
 * database. The unit suite cannot see any of it.
 *
 * What is actually at stake: this cache is what the app shows when it is
 * offline. If `latest()` returns the wrong row, the phone displays an old
 * report as the current one, with no indication that it has done so.
 */
@RunWith(AndroidJUnit4::class)
class ReportDaoInstrumentedTest {

    private lateinit var database: TenderDatabase
    private lateinit var dao: ReportDao

    @Before
    fun setUp() {
        val context: Context = ApplicationProvider.getApplicationContext()
        // In-memory, so one test cannot leave a row behind for the next. The
        // schema and the generated SQL are the real ones either way.
        database = Room.inMemoryDatabaseBuilder(context, TenderDatabase::class.java)
            .allowMainThreadQueries()
            .build()
        dao = database.reports()
    }

    @After
    fun tearDown() {
        database.close()
    }

    @Test
    fun a_report_goes_in_and_comes_back_whole() = runBlocking {
        dao.insert(report(runId = 10, runNumber = 1))

        val stored = dao.latestOnce()

        assertEquals(10L, stored?.runId)
        assertEquals(1, stored?.runNumber)
        // The document is stored verbatim. Anything less and an app update
        // could not start rendering a field it previously ignored.
        assertEquals(json(10), stored?.json)
    }

    @Test
    fun latest_means_the_newest_run_not_the_last_one_written() = runBlocking {
        // Written out of order deliberately: if `latest()` returned the most
        // recently inserted row rather than the highest run, this is the only
        // arrangement that tells the difference.
        dao.insert(report(runId = 30, runNumber = 3))
        dao.insert(report(runId = 10, runNumber = 1))
        dao.insert(report(runId = 20, runNumber = 2))

        assertEquals(30L, dao.latestOnce()?.runId)
        assertEquals(30L, dao.latest().first()?.runId)
    }

    @Test
    fun a_run_can_be_fetched_by_its_id_and_a_missing_one_is_null_not_a_guess() = runBlocking {
        dao.insert(report(runId = 10, runNumber = 1))

        assertEquals(10L, dao.byRun(10)?.runId)
        // Absent means unknown. Returning the nearest row would be a wrong
        // answer that looks like a right one.
        assertNull(dao.byRun(999))
    }

    @Test
    fun storing_the_same_run_twice_replaces_it_rather_than_duplicating() = runBlocking {
        dao.insert(report(runId = 10, runNumber = 1, opportunities = 3))
        dao.insert(report(runId = 10, runNumber = 1, opportunities = 7))

        assertEquals(1, dao.history().first().size)
        assertEquals(7, dao.latestOnce()?.opportunityCount)
    }

    @Test
    fun trimming_keeps_the_newest_and_drops_the_oldest() = runBlocking {
        (1..8).forEach { n -> dao.insert(report(runId = n * 10L, runNumber = n)) }

        dao.trimTo(keep = 3)

        val remaining = dao.history().first().map { it.runId }
        assertEquals(3, remaining.size)
        assertEquals(
            "trimTo kept the wrong end of the list -- the app would be caching " +
                "the oldest reports and discarding the current one",
            listOf(80L, 70L, 60L),
            remaining,
        )
    }

    @Test
    fun store_inserts_and_trims_in_one_go() = runBlocking {
        (1..6).forEach { n -> dao.store(report(runId = n * 10L, runNumber = n), keep = 2) }

        val remaining = dao.history().first().map { it.runId }
        assertEquals(listOf(60L, 50L), remaining)
        assertEquals(60L, dao.latestOnce()?.runId)
    }

    @Test
    fun history_is_newest_first_because_that_is_how_it_is_displayed() = runBlocking {
        dao.insert(report(runId = 10, runNumber = 1))
        dao.insert(report(runId = 30, runNumber = 3))
        dao.insert(report(runId = 20, runNumber = 2))

        val ids = dao.history().first().map { it.runId }

        assertEquals(listOf(30L, 20L, 10L), ids)
    }

    @Test
    fun an_empty_cache_is_empty_rather_than_an_exception() = runBlocking {
        // First launch. "Nothing cached yet" has to be an ordinary answer, or
        // the app crashes on the screen it opens on.
        assertNull(dao.latestOnce())
        assertNull(dao.latest().first())
        assertTrue(dao.history().first().isEmpty())
    }

    private fun json(runId: Long) = """{"schema":1,"run_id":$runId}"""

    private fun report(
        runId: Long,
        runNumber: Int,
        opportunities: Int = 0,
    ) = CachedReport(
        runId = runId,
        runNumber = runNumber,
        storedAt = 1_700_000_000_000L + runId,
        runCreatedAt = "2026-01-01T00:00:00Z",
        runConclusion = "success",
        runHtmlUrl = "https://github.com/example/example/actions/runs/$runId",
        status = "ok",
        statusLine = "$opportunities new opportunities",
        opportunityCount = opportunities,
        portalsBroken = 0,
        json = json(runId),
    )
}
