package jo.tendermonitor.data.github

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * Only the fields this app uses. `ignoreUnknownKeys` is on, so GitHub adding
 * one cannot break a screen -- and removing one shows up as a missing value
 * rather than a parse failure, which is the direction that keeps the app
 * usable while something is being fixed.
 */

@Serializable
data class WorkflowRunsPage(
    @SerialName("total_count") val totalCount: Int = 0,
    @SerialName("workflow_runs") val runs: List<WorkflowRun> = emptyList(),
)

@Serializable
data class WorkflowRun(
    val id: Long,
    @SerialName("run_number") val runNumber: Int = 0,
    val name: String? = null,
    /** queued | in_progress | completed | requested | waiting */
    val status: String? = null,
    /** success | failure | cancelled | skipped | timed_out | null while running */
    val conclusion: String? = null,
    val event: String? = null,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("updated_at") val updatedAt: String? = null,
    @SerialName("run_started_at") val runStartedAt: String? = null,
    @SerialName("html_url") val htmlUrl: String? = null,
    @SerialName("head_branch") val headBranch: String? = null,
) {
    val isFinished: Boolean get() = status == "completed"
    val isRunning: Boolean get() = status == "in_progress" || status == "queued" ||
        status == "requested" || status == "waiting"
}

@Serializable
data class ArtifactsPage(
    @SerialName("total_count") val totalCount: Int = 0,
    val artifacts: List<Artifact> = emptyList(),
)

@Serializable
data class Artifact(
    val id: Long,
    val name: String,
    @SerialName("size_in_bytes") val sizeInBytes: Long = 0,
    /**
     * True once the retention window has passed. The download then returns
     * 410, and the app must say "expired", not "download failed": one is the
     * documented end of a 90-day window and the other suggests something is
     * wrong.
     */
    val expired: Boolean = false,
    @SerialName("created_at") val createdAt: String? = null,
    @SerialName("expires_at") val expiresAt: String? = null,
)

@Serializable
data class DispatchRequest(
    val ref: String,
    val inputs: Map<String, String> = emptyMap(),
)

@Serializable
data class GitHubUser(
    val login: String = "",
)

/** GitHub's own error body. Its message is usually the most useful sentence. */
@Serializable
data class GitHubError(
    val message: String = "",
    @SerialName("documentation_url") val documentationUrl: String? = null,
)

@Serializable
data class ContentsResponse(
    val sha: String = "",
    val content: String = "",
    val encoding: String = "",
    val path: String = "",
)

@Serializable
data class CommitResponse(
    val commit: CommitInfo = CommitInfo(),
    val content: ContentSummary? = null,
)

@Serializable
data class CommitInfo(
    val sha: String = "",
    @SerialName("html_url") val htmlUrl: String? = null,
    val message: String = "",
)

@Serializable
data class ContentSummary(
    val sha: String = "",
    val path: String = "",
)

@Serializable
data class PutFileRequest(
    val message: String,
    /** Base64, no line breaks. */
    val content: String,
    /** The sha of the file being replaced. Omitted only when creating one. */
    val sha: String? = null,
    val branch: String? = null,
)
