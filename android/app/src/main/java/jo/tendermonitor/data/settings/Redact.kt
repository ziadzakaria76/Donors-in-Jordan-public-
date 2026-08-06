package jo.tendermonitor.data.settings

/**
 * Nothing that could contain the token reaches a screen, a log or a crash
 * report without passing through here.
 *
 * Two layers, because either alone is not enough:
 *
 *  1. The token this app holds is replaced wherever it appears. That covers an
 *     error that echoes a request header or a URL we built.
 *  2. Anything SHAPED like a GitHub credential is replaced too, whether or not
 *     it is the one we hold. GitHub's own error bodies sometimes quote a
 *     credential back, and a token the user pasted into the wrong field is
 *     still a token.
 *
 * The second layer is the one that matters most in a crash report, where the
 * first has no token to compare against.
 */
object Redact {

    /**
     * GitHub's documented credential prefixes.
     *
     * ghp_/gho_/ghu_/ghs_/ghr_ are the classic 40-char forms; github_pat_ is
     * the fine-grained one this app asks for, which is longer and has an
     * underscore in the middle. Matched on prefix and length rather than on an
     * exact grammar, so a format change degrades to over-redaction -- which is
     * the safe direction.
     */
    private val TOKEN_SHAPES = listOf(
        Regex("""github_pat_[A-Za-z0-9_]{20,}"""),
        Regex("""gh[pousr]_[A-Za-z0-9]{20,}"""),
        // Basic/Bearer headers, whatever they carry.
        Regex("""(?i)(authorization:\s*)(bearer|token|basic)\s+\S+"""),
    )

    const val MASK = "***REDACTED***"

    /**
     * @param known the token this app currently holds, if any.
     */
    fun scrub(text: String?, known: String? = null): String {
        // Declared non-null rather than relying on a smart cast: `var out =
        // text` infers the parameter's nullable type, and every later call
        // then has to be null-safe for a value that provably is not.
        var out: String = text ?: return ""
        if (out.isEmpty()) return out

        // The known token first: an exact match is the strongest signal, and
        // doing it before the shape rules means a token that does not match
        // any known shape is still removed.
        if (!known.isNullOrBlank() && known.length >= 8) {
            out = out.replace(known, MASK)
        }
        for (shape in TOKEN_SHAPES) {
            out = shape.replace(out) { match: MatchResult ->
                val prefix = match.groupValues.getOrNull(1).orEmpty()
                if (prefix.isEmpty()) MASK else prefix + MASK
            }
        }
        return out
    }

    /**
     * A token as it may be shown back to the user: enough to recognise which
     * one is stored, never enough to use.
     */
    fun fingerprint(token: String?): String {
        if (token.isNullOrBlank()) return "none"
        val trimmed = token.trim()
        if (trimmed.length <= 8) return "set (too short to be a GitHub token)"
        return "set, ending ${trimmed.takeLast(4)} (${trimmed.length} characters)"
    }
}
