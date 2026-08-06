package jo.tendermonitor.data.github

import okhttp3.ResponseBody
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.PUT
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming
import retrofit2.http.Url

/**
 * The GitHub REST endpoints this app uses, and no others.
 *
 * Every one returns Response<T> rather than T: the status code and the headers
 * are half the diagnosis. A 403 with `x-ratelimit-remaining: 0` and a 403
 * because the token lacks a permission are the same exception to Retrofit and
 * two completely different sentences to a user.
 *
 * WHAT IS NOT HERE, AND WHY. There is no endpoint for a job's step summary,
 * because GitHub does not publish one -- summaries are written to an internal
 * container that the artifacts API does not list. The report is read from the
 * run's artifacts instead; see ReportRepository.
 */
interface GitHubApi {

    /** Cheapest call that proves a token works. */
    @GET("user")
    suspend fun user(): Response<GitHubUser>

    @GET("repos/{owner}/{repo}/actions/workflows/{workflow}/runs")
    suspend fun workflowRuns(
        @Path("owner") owner: String,
        @Path("repo") repo: String,
        @Path("workflow") workflow: String,
        @Query("per_page") perPage: Int = 20,
    ): Response<WorkflowRunsPage>

    /**
     * Returns 204 with no body. It does NOT say which run it started, which is
     * why the caller has to watch for a new run appearing rather than being
     * handed one.
     */
    @POST("repos/{owner}/{repo}/actions/workflows/{workflow}/dispatches")
    suspend fun dispatch(
        @Path("owner") owner: String,
        @Path("repo") repo: String,
        @Path("workflow") workflow: String,
        @Body body: DispatchRequest,
    ): Response<Unit>

    @GET("repos/{owner}/{repo}/actions/runs/{runId}")
    suspend fun run(
        @Path("owner") owner: String,
        @Path("repo") repo: String,
        @Path("runId") runId: Long,
    ): Response<WorkflowRun>

    @GET("repos/{owner}/{repo}/actions/runs/{runId}/artifacts")
    suspend fun artifacts(
        @Path("owner") owner: String,
        @Path("repo") repo: String,
        @Path("runId") runId: Long,
    ): Response<ArtifactsPage>

    /**
     * A zip, always -- even for one file. Streamed rather than buffered: the
     * Word pack can run to megabytes and a handset should not hold it twice.
     */
    @Streaming
    @GET("repos/{owner}/{repo}/actions/artifacts/{artifactId}/zip")
    suspend fun artifactZip(
        @Path("owner") owner: String,
        @Path("repo") repo: String,
        @Path("artifactId") artifactId: Long,
    ): Response<ResponseBody>

    @GET("repos/{owner}/{repo}/contents/{path}")
    suspend fun fileContents(
        @Path("owner") owner: String,
        @Path("repo") repo: String,
        @Path("path", encoded = true) path: String,
        @Query("ref") ref: String? = null,
    ): Response<ContentsResponse>

    @PUT("repos/{owner}/{repo}/contents/{path}")
    suspend fun putFile(
        @Path("owner") owner: String,
        @Path("repo") repo: String,
        @Path("path", encoded = true) path: String,
        @Body body: PutFileRequest,
    ): Response<CommitResponse>

    /** Used only to follow a redirect the artifact download may hand back. */
    @Streaming
    @GET
    suspend fun download(
        @Url url: String,
        @Header("Authorization") authorization: String? = null,
    ): Response<ResponseBody>
}
