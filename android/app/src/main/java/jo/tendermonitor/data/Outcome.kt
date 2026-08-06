package jo.tendermonitor.data

/**
 * Every operation that can fail returns one of these.
 *
 * The backend's rule carried over: an empty result and a broken one must never
 * render the same. `Ok(emptyList())` is a portal with nothing to report;
 * `Failed` is a portal that could not be read, and the two take different
 * paths through every screen in this app.
 *
 * A [Problem] is not an exception message. It is a headline the user reads, a
 * detail they can act on, and a [Kind] the UI switches on -- because "expired",
 * "rate limited" and "your token cannot see this repository" all arrive as an
 * HTTP failure and need three different sentences.
 */
sealed interface Outcome<out T> {
    data class Ok<T>(val value: T) : Outcome<T>
    data class Failed(val problem: Problem) : Outcome<Nothing>

    fun valueOrNull(): T? = (this as? Ok)?.value
    fun problemOrNull(): Problem? = (this as? Failed)?.problem
}

enum class Kind {
    /** No token has been saved yet. Not a failure -- a setup step. */
    NO_TOKEN,

    /** 401. The token is wrong, revoked or expired. */
    UNAUTHORIZED,

    /** 403 that is not a rate limit: the token lacks a permission. */
    FORBIDDEN,

    /** 403/429 with the rate-limit headers. Carries when it resets. */
    RATE_LIMITED,

    /** 404. On GitHub this also means "exists, but your token cannot see it". */
    NOT_FOUND,

    /** The artifact is past its retention window. Not a download failure. */
    EXPIRED,

    /** No usable network, or the request never reached GitHub. */
    OFFLINE,

    /** 5xx. GitHub's problem, worth retrying. */
    SERVER,

    /** The response parsed but was not what this app was written for. */
    MALFORMED,

    UNKNOWN,
}

data class Problem(
    /** One line, in the user's terms. Never an exception class name. */
    val headline: String,
    /** What is known, including GitHub's own words where it gave any. */
    val detail: String = "",
    val kind: Kind = Kind.UNKNOWN,
    /** What to do about it, when there is something to do. */
    val fixHint: String? = null,
    /** When a rate limit lifts, epoch seconds. Null unless RATE_LIMITED. */
    val retryAtEpochSeconds: Long? = null,
) {
    /** True when trying again unchanged could plausibly work. */
    val isTransient: Boolean
        get() = kind == Kind.OFFLINE || kind == Kind.SERVER || kind == Kind.RATE_LIMITED
}

inline fun <T, R> Outcome<T>.map(transform: (T) -> R): Outcome<R> = when (this) {
    is Outcome.Ok -> Outcome.Ok(transform(value))
    is Outcome.Failed -> this
}

inline fun <T, R> Outcome<T>.flatMap(transform: (T) -> Outcome<R>): Outcome<R> =
    when (this) {
        is Outcome.Ok -> transform(value)
        is Outcome.Failed -> this
    }
