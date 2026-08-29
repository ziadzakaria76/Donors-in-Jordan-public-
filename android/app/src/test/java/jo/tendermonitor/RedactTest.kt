package jo.tendermonitor

import jo.tendermonitor.data.settings.Redact
import jo.tendermonitor.data.settings.TokenAdvice
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The token must not survive a trip through anything the user or a crash
 * reporter can see. These are the cases that would leak it.
 */
class RedactTest {

    private val fineGrained =
        "github_pat_11ABCDEFG0abcdefghijkl_ZYXWVUTSRQPONMLKJIHGFEDCBA0123456789"
    private val classic = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    @Test
    fun `the stored token is removed wherever it appears`() {
        val message = "GET https://api.github.com/user failed with token $fineGrained"
        val scrubbed = Redact.scrub(message, fineGrained)
        assertFalse(scrubbed.contains(fineGrained))
        assertTrue(scrubbed.contains(Redact.MASK))
    }

    @Test
    fun `a token we do not hold is still removed`() {
        // The case that matters in a crash report: nothing to compare against,
        // so only the shape rules can catch it.
        val message = "Unexpected header: Authorization: Bearer $classic"
        val scrubbed = Redact.scrub(message, known = null)
        assertFalse(scrubbed.contains(classic))
    }

    @Test
    fun `both GitHub token shapes are caught`() {
        for (token in listOf(fineGrained, classic, "gho_${"a".repeat(30)}",
                             "ghs_${"b".repeat(30)}")) {
            val scrubbed = Redact.scrub("value=$token end", known = null)
            assertFalse("leaked $token", scrubbed.contains(token))
        }
    }

    @Test
    fun `an authorization header is masked whatever it carries`() {
        val scrubbed = Redact.scrub("authorization: token some-unknown-format", null)
        assertFalse(scrubbed.contains("some-unknown-format"))
        assertTrue(scrubbed.lowercase().contains("authorization:"))
    }

    @Test
    fun `ordinary text is left alone`() {
        val text = "EBRD returned a bot wall (Cloudflare) - try a different network"
        assertEquals(text, Redact.scrub(text, fineGrained))
    }

    @Test
    fun `a very short stored value is not used as a needle`() {
        // Guarding against a pathological "token" of "a" turning every 'a' in
        // an error message into a mask, which would destroy the diagnosis.
        val scrubbed = Redact.scrub("a portal was unavailable", known = "a")
        assertEquals("a portal was unavailable", scrubbed)
    }

    @Test
    fun `null and empty are handled without throwing`() {
        assertEquals("", Redact.scrub(null, fineGrained))
        assertEquals("", Redact.scrub("", fineGrained))
    }

    @Test
    fun `a fingerprint identifies without revealing`() {
        val print = Redact.fingerprint(classic)
        assertFalse(print.contains(classic))
        assertTrue(print.contains(classic.takeLast(4)))
        assertEquals("none", Redact.fingerprint(null))
        assertEquals("none", Redact.fingerprint("   "))
    }

    @Test
    fun `advice warns but never blocks an unfamiliar token`() {
        assertNull(TokenAdvice.warning(fineGrained))
        assertNull(TokenAdvice.warning(classic))

        // GitHub has changed token formats before. Refusing a valid credential
        // because the prefix was unfamiliar would be worse than a 401.
        val unfamiliar = TokenAdvice.warning("some_future_format_abcdefghijklmnop")
        assertTrue(unfamiliar!!.contains("Saving it anyway"))

        val pasted = TokenAdvice.warning("ghp_ABCDEF GHIJKL")
        assertTrue(pasted!!.contains("space"))
    }
}
