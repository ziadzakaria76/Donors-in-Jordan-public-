package jo.tendermonitor.data.github

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Problem
import jo.tendermonitor.data.settings.Redact
import kotlinx.serialization.json.Json
import okhttp3.Headers
import retrofit2.Response
import java.io.IOException
import java.net.SocketTimeoutException
import java.net.UnknownHostException
import javax.net.ssl.SSLException

/**
 * Turning an HTTP response or a thrown exception into something worth reading.
 *
 * This is where the backend's rule about failures lands in the app: a
 * diagnosed reason, not a status code. Five different things arrive here as
 * "the request failed", and each needs a different action from the person
 * holding the phone:
 *
 *   401  the token is wrong or revoked          -> paste a new one
 *   403  the token lacks a permission           -> fix the token's scopes
 *   403  rate limited                           -> wait, and it says how long
 *   404  no such repo, OR no access to it       -> both, because GitHub will
 *                                                  not say which
 *   410  the artifact is past its retention     -> nothing to fix; it is gone
 *
 * Every message runs through [Redact] before it can reach a screen.
 */
object Failures {

    private val lenientJson = Json { ignoreUnknownKeys = true; isLenient = true }

    fun fromResponse(
        response: Response<*>,
        context: String,
        token: String?,
    ): Problem {
        val code = response.code()
        val body = runCatching { response.errorBody()?.string() }.getOrNull().orEmpty()
        val message = Redact.scrub(gitHubMessage(body) ?: response.message(), token)
        val headers = response.headers()

        return when {
            code == 401 -> Problem(
                headline = "GitHub refused the token",
                detail = message.ifBlank { "The request was rejected as unauthenticated." },
                kind = Kind.UNAUTHORIZED,
                fixHint = "Check the token in Settings. A fine-grained token also " +
                    "expires -- GitHub does not warn you, it just starts saying this.",
            )

            code == 403 && isRateLimited(headers) -> {
                val resetAt = headers["x-ratelimit-reset"]?.toLongOrNull()
                Problem(
                    headline = "GitHub is rate-limiting this app",
                    detail = buildString {
                        append(message.ifBlank { "The hourly request budget is spent." })
                        val limit = headers["x-ratelimit-limit"]
                        if (limit != null) append("  Limit: $limit requests/hour.")
                    },
                    kind = Kind.RATE_LIMITED,
                    fixHint = "It will work again on its own. Background checks back " +
                        "off automatically; nothing is lost.",
                    retryAtEpochSeconds = resetAt,
                )
            }

            code == 403 -> Problem(
                headline = "The token is not allowed to do that",
                detail = message.ifBlank { "GitHub returned 403 for $context." },
                kind = Kind.FORBIDDEN,
                fixHint = "This app needs Actions: read and write, and Contents: " +
                    "read and write, on this one repository. See ANDROID.md.",
            )

            code == 404 -> Problem(
                headline = "Not found",
                detail = message.ifBlank { "GitHub returned 404 for $context." },
                kind = Kind.NOT_FOUND,
                // Worth saying plainly: GitHub deliberately answers 404 rather
                // than 403 for a private resource you cannot see, so "not
                // found" and "not yours" are indistinguishable from here.
                fixHint = "Either it does not exist, or the token cannot see it -- " +
                    "GitHub answers 404 for both, so check the repository name and " +
                    "that the token is scoped to it.",
            )

            code == 410 -> Problem(
                headline = "These files have expired",
                detail = message.ifBlank {
                    "Run artifacts are kept for 90 days and this run's are past that."
                },
                kind = Kind.EXPIRED,
                fixHint = "Nothing is broken and there is nothing to retry. Trigger a " +
                    "new run to get a current pack.",
            )

            code in 500..599 -> Problem(
                headline = "GitHub had a problem",
                detail = message.ifBlank { "GitHub returned $code for $context." },
                kind = Kind.SERVER,
                fixHint = "Their side, not yours. Try again shortly.",
            )

            else -> Problem(
                headline = "The request failed ($code)",
                detail = message.ifBlank { "GitHub returned $code for $context." },
                kind = Kind.UNKNOWN,
            )
        }
    }

    fun fromException(error: Throwable, context: String, token: String?): Problem {
        val detail = Redact.scrub(error.message ?: error::class.java.simpleName, token)
        return when (error) {
            is UnknownHostException -> Problem(
                headline = "No connection",
                detail = "The phone could not reach github.com while $context.",
                kind = Kind.OFFLINE,
                fixHint = "The last report you downloaded is still readable offline.",
            )

            is SocketTimeoutException -> Problem(
                headline = "GitHub did not answer in time",
                detail = "Timed out while $context.",
                kind = Kind.OFFLINE,
            )

            is SSLException -> Problem(
                headline = "The secure connection failed",
                detail = detail,
                kind = Kind.OFFLINE,
                fixHint = "A captive portal or a filtering proxy usually causes this.",
            )

            is IOException -> Problem(
                headline = "The connection dropped",
                detail = detail,
                kind = Kind.OFFLINE,
            )

            is kotlinx.serialization.SerializationException -> Problem(
                headline = "GitHub's answer could not be read",
                detail = detail,
                kind = Kind.MALFORMED,
                fixHint = "This usually means the API changed shape. The app is not " +
                    "guessing at it.",
            )

            else -> Problem(
                headline = "Something went wrong",
                detail = detail,
                kind = Kind.UNKNOWN,
            )
        }
    }

    /**
     * A rate limit is a 403 with the budget at zero. Without this check every
     * rate limit reads as a permissions problem, and the user goes and edits a
     * token that was never the issue.
     */
    private fun isRateLimited(headers: Headers): Boolean {
        val remaining = headers["x-ratelimit-remaining"]?.toIntOrNull()
        return remaining == 0 || headers["retry-after"] != null
    }

    private fun gitHubMessage(body: String): String? {
        if (body.isBlank()) return null
        return runCatching {
            lenientJson.decodeFromString(GitHubError.serializer(), body).message
        }.getOrNull()?.takeIf { it.isNotBlank() }
            ?: body.take(300).replace('\n', ' ').trim().takeIf { it.isNotBlank() }
    }
}
