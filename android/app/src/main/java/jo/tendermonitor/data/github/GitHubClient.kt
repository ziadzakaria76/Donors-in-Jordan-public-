package jo.tendermonitor.data.github

import jo.tendermonitor.data.Kind
import jo.tendermonitor.data.Outcome
import jo.tendermonitor.data.Problem
import jo.tendermonitor.data.settings.TokenStore
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Interceptor
import retrofit2.Response
import retrofit2.Retrofit
import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

/**
 * The one place a request is made, and the one place a token is attached.
 *
 * The token is read per request from the [TokenStore] rather than captured
 * when the client is built: pasting a new token in Settings has to take effect
 * without restarting the app, and a stale copy held in an interceptor is
 * exactly how "I changed it and it still says unauthorised" happens.
 *
 * NO LOGGING INTERCEPTOR. Not even at debug level, not even behind a flag.
 * OkHttp's logging interceptor prints request headers, and the Authorization
 * header is a request header.
 */
class GitHubClient(
    private val tokens: TokenStore,
    baseUrl: String = "https://api.github.com/",
) {

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
        explicitNulls = false
        encodeDefaults = true
    }

    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .addInterceptor(authInterceptor())
        .build()

    val api: GitHubApi = Retrofit.Builder()
        .baseUrl(baseUrl)
        .client(http)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(GitHubApi::class.java)

    private fun authInterceptor() = Interceptor { chain ->
        val token = tokens.token()
        val builder = chain.request().newBuilder()
            .header("Accept", "application/vnd.github+json")
            .header("X-GitHub-Api-Version", "2022-11-28")
            .header("User-Agent", "JordanTenderMonitor-Android")
        if (!token.isNullOrBlank()) {
            builder.header("Authorization", "Bearer $token")
        }
        chain.proceed(builder.build())
    }

    /**
     * Runs one call and turns anything that can go wrong into an [Outcome].
     *
     * [context] is a phrase that reads naturally after "while ..." -- it ends
     * up in the message the user sees, so "reading the run's files" beats
     * "artifactZip".
     */
    suspend fun <T> call(
        context: String,
        requiresToken: Boolean = true,
        block: suspend (GitHubApi) -> Response<T>,
    ): Outcome<T> {
        if (requiresToken && !tokens.hasToken()) {
            return Outcome.Failed(
                Problem(
                    headline = "No token yet",
                    detail = "This app needs a GitHub token to reach the repository.",
                    kind = Kind.NO_TOKEN,
                    fixHint = "Settings -> GitHub token. ANDROID.md has the exact " +
                        "permissions to grant, which are the minimum that work.",
                )
            )
        }
        return try {
            val response = block(api)
            if (response.isSuccessful) {
                val body = response.body()
                @Suppress("UNCHECKED_CAST")
                when {
                    body != null -> Outcome.Ok(body)
                    // 204 No Content is a success with nothing in it, which is
                    // what workflow_dispatch returns.
                    response.code() == 204 -> Outcome.Ok(Unit as T)
                    else -> Outcome.Failed(
                        Problem(
                            headline = "GitHub answered with nothing",
                            detail = "HTTP ${response.code()} and an empty body while " +
                                "$context.",
                            kind = Kind.MALFORMED,
                        )
                    )
                }
            } else {
                Outcome.Failed(Failures.fromResponse(response, context, tokens.token()))
            }
        } catch (error: Throwable) {
            if (error is kotlinx.coroutines.CancellationException) throw error
            Outcome.Failed(Failures.fromException(error, context, tokens.token()))
        }
    }
}
