package jo.tendermonitor

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Outcome
import jo.tendermonitor.data.github.GitHubClient
import jo.tendermonitor.data.settings.TokenStore
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * The API client's failure paths.
 *
 * Every one of these arrives as "the request failed" and needs a different
 * sentence, because each one needs a different action from the person holding
 * the phone. Collapsing them is how an app teaches someone to ignore its
 * errors -- the same lesson the backend learned about its status table.
 */
class GitHubClientTest {

    private lateinit var server: MockWebServer
    private lateinit var client: GitHubClient

    private val token = "github_pat_11TESTTOKEN0abcdefghijkl_ZYXWVUTSRQPONMLKJIHGFEDCBA01"

    private var stored: String? = token
    private val tokens = object : TokenStore {
        override fun token(): String? = stored
        override fun saveToken(value: String?) { stored = value }
    }

    @Before
    fun setUp() {
        server = MockWebServer()
        server.start()
        client = GitHubClient(tokens, server.url("/").toString())
    }

    @After
    fun tearDown() {
        server.shutdown()
        stored = token
    }

    @Test
    fun `no token is a setup step, not a failure`() = runTest {
        stored = null
        val result = client.call("checking the token") { it.user() }
        val problem = (result as Outcome.Failed).problem
        assertEquals(Kind.NO_TOKEN, problem.kind)
        assertNotNull(problem.fixHint)
        // Nothing was sent: asking GitHub without a credential wastes a request
        // and returns a less useful error than we can write ourselves.
        assertEquals(0, server.requestCount)
    }

    @Test
    fun `the token is sent as a bearer credential`() = runTest {
        server.enqueue(MockResponse().setResponseCode(200).setBody("""{"login":"someone"}"""))
        client.call("checking the token") { it.user() }
        val request = server.takeRequest()
        assertEquals("Bearer $token", request.getHeader("Authorization"))
        assertEquals("2022-11-28", request.getHeader("X-GitHub-Api-Version"))
    }

    @Test
    fun `401 says the token was refused, and does not echo it`() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(401)
                .setBody("""{"message":"Bad credentials"}""")
        )
        val result = client.call("checking the token") { it.user() }
        val problem = (result as Outcome.Failed).problem
        assertEquals(Kind.UNAUTHORIZED, problem.kind)
        assertTrue(problem.detail.contains("Bad credentials"))
        assertFalse("${problem.headline} ${problem.detail}".contains(token))
    }

    @Test
    fun `403 with the budget spent is a rate limit, not a permission problem`() = runTest {
        // Told apart because the fix is completely different: one is "wait",
        // the other is "go and edit your token's scopes".
        server.enqueue(
            MockResponse().setResponseCode(403)
                .setHeader("x-ratelimit-remaining", "0")
                .setHeader("x-ratelimit-limit", "5000")
                .setHeader("x-ratelimit-reset", "1900000000")
                .setBody("""{"message":"API rate limit exceeded"}""")
        )
        val result = client.call("listing runs") { it.user() }
        val problem = (result as Outcome.Failed).problem
        assertEquals(Kind.RATE_LIMITED, problem.kind)
        assertEquals(1900000000L, problem.retryAtEpochSeconds)
        assertTrue(problem.isTransient)
    }

    @Test
    fun `403 with budget remaining is a permission problem`() = runTest {
        server.enqueue(
            MockResponse().setResponseCode(403)
                .setHeader("x-ratelimit-remaining", "4999")
                .setBody("""{"message":"Resource not accessible by personal access token"}""")
        )
        val result = client.call("starting a run") { it.user() }
        val problem = (result as Outcome.Failed).problem
        assertEquals(Kind.FORBIDDEN, problem.kind)
        assertTrue(problem.fixHint!!.contains("Actions"))
        assertFalse(problem.isTransient)
    }

    @Test
    fun `404 admits it could be either missing or invisible`() = runTest {
        // GitHub deliberately answers 404 rather than 403 for a resource you
        // cannot see, so claiming "it does not exist" would be a guess.
        server.enqueue(MockResponse().setResponseCode(404).setBody("""{"message":"Not Found"}"""))
        val result = client.call("listing runs") { it.user() }
        val problem = (result as Outcome.Failed).problem
        assertEquals(Kind.NOT_FOUND, problem.kind)
        assertTrue(problem.fixHint!!.contains("cannot see it"))
    }

    @Test
    fun `410 is expiry, and says there is nothing to retry`() = runTest {
        server.enqueue(MockResponse().setResponseCode(410).setBody("""{"message":"Gone"}"""))
        val result = client.call("downloading files") { it.user() }
        val problem = (result as Outcome.Failed).problem
        assertEquals(Kind.EXPIRED, problem.kind)
        assertFalse(problem.isTransient)
        assertTrue(problem.fixHint!!.contains("nothing to retry"))
    }

    @Test
    fun `a 5xx is marked as theirs and worth retrying`() = runTest {
        server.enqueue(MockResponse().setResponseCode(502))
        val result = client.call("listing runs") { it.user() }
        val problem = (result as Outcome.Failed).problem
        assertEquals(Kind.SERVER, problem.kind)
        assertTrue(problem.isTransient)
    }

    @Test
    fun `an unreachable host is offline, and says the cache still works`() = runTest {
        server.shutdown()
        val result = client.call("listing runs") { it.user() }
        val problem = (result as Outcome.Failed).problem
        assertEquals(Kind.OFFLINE, problem.kind)
        assertTrue(problem.isTransient)
    }

    @Test
    fun `204 with no body is a success, because dispatch returns one`() = runTest {
        server.enqueue(MockResponse().setResponseCode(204))
        val result = client.call("starting a run") { api ->
            api.dispatch("o", "r", "monitor.yml",
                jo.tendermonitor.data.github.DispatchRequest("main"))
        }
        assertTrue(result is Outcome.Ok)
    }

    @Test
    fun `a body GitHub did not send as JSON is still reported`() = runTest {
        server.enqueue(MockResponse().setResponseCode(400).setBody("<html>nope</html>"))
        val result = client.call("listing runs") { it.user() }
        val problem = (result as Outcome.Failed).problem
        assertTrue(problem.detail.contains("nope"))
    }

    @Test
    fun `unknown fields in a response do not break parsing`() = runTest {
        // GitHub adds fields. An app that fell over when it did would break on
        // their schedule rather than ours.
        server.enqueue(
            MockResponse().setResponseCode(200).setBody(
                """{"total_count":1,"workflow_runs":[
                    {"id":5,"run_number":9,"status":"completed","conclusion":"success",
                     "something_new":{"nested":true}}]}"""
            )
        )
        val result = client.call("listing runs") { api ->
            api.workflowRuns("o", "r", "monitor.yml", 1)
        }
        val page = (result as Outcome.Ok).value
        assertEquals(1, page.runs.size)
        assertEquals(9, page.runs[0].runNumber)
    }
}
