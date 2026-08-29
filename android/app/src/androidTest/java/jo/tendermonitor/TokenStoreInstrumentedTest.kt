package jo.tendermonitor

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import jo.tendermonitor.data.settings.AppSettings
import jo.tendermonitor.data.settings.KeystoreSettings
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File

/**
 * The token store, on a real device.
 *
 * THIS IS THE ONE THING NO UNIT TEST CAN COVER. `EncryptedSharedPreferences`
 * needs the Android Keystore, and there is no Keystore on a JVM -- which is why
 * `ANDROID.md` has listed this as unverified since the app was written. Every
 * other claim about the token has a test somewhere; this one had the class's
 * own docstring and nothing else.
 *
 * The claim being checked is not "it round-trips". A plain unencrypted file
 * round-trips perfectly. The claim is that **the token is not recoverable from
 * the app's storage by reading it**, which is the entire reason for the
 * dependency.
 */
@RunWith(AndroidJUnit4::class)
class TokenStoreInstrumentedTest {

    private val context: Context
        get() = ApplicationProvider.getApplicationContext()

    private lateinit var store: KeystoreSettings

    @Before
    fun setUp() {
        store = KeystoreSettings(context)
        store.saveToken(null)
    }

    @After
    fun tearDown() {
        store.saveToken(null)
    }

    @Test
    fun a_token_survives_the_round_trip_through_the_keystore() {
        store.saveToken(TOKEN)

        assertEquals(TOKEN, store.token())
        assertTrue(store.hasToken())
    }

    @Test
    fun a_token_survives_a_new_instance_which_is_what_a_restart_looks_like() {
        store.saveToken(TOKEN)

        // A fresh KeystoreSettings re-derives the master key from the Keystore
        // rather than reusing anything in memory. If the key were being held
        // only in this process, this is where it would come back null -- and
        // the app would silently ask for the token again on every launch.
        val afterRestart = KeystoreSettings(context)

        assertEquals(TOKEN, afterRestart.token())
    }

    @Test
    fun the_token_is_not_findable_in_plaintext_anywhere_in_the_apps_storage() {
        store.saveToken(TOKEN)

        // Every file the app owns, not just the one preferences file. Naming
        // the file would let a rename quietly narrow the search to nothing.
        val root = context.filesDir.parentFile
        requireNotNull(root) { "the app has no data directory" }

        val leaked = mutableListOf<String>()
        root.walkTopDown()
            .filter { it.isFile && it.length() < MAX_SCANNED_BYTES }
            .forEach { file ->
                val bytes = runCatching { file.readBytes() }.getOrNull() ?: return@forEach
                if (String(bytes, Charsets.ISO_8859_1).contains(TOKEN)) {
                    leaked += file.relativeToOrSelf(root).path
                }
                if (String(bytes, Charsets.UTF_16LE).contains(TOKEN)) {
                    leaked += file.relativeToOrSelf(root).path + " (utf-16)"
                }
            }

        assertTrue(
            "the token was readable as plaintext in: $leaked -- " +
                "EncryptedSharedPreferences is either not in use or not working",
            leaked.isEmpty(),
        )
    }

    @Test
    fun the_preferences_file_exists_so_the_search_above_was_looking_at_something() {
        // Guards the test above. If nothing were written at all, "no plaintext
        // found" would pass for the wrong reason -- the exact shape of false
        // negative this codebase keeps refusing to ship.
        store.saveToken(TOKEN)

        val prefsDir = File(context.filesDir.parentFile, "shared_prefs")
        val files = prefsDir.listFiles().orEmpty()

        assertTrue(
            "no shared_prefs files were written, so the plaintext scan proved nothing",
            files.isNotEmpty(),
        )
        assertTrue(
            "the stored file is empty, so the plaintext scan proved nothing",
            files.any { it.length() > 0 },
        )
    }

    @Test
    fun clearing_the_token_really_removes_it() {
        store.saveToken(TOKEN)
        store.saveToken(null)

        assertNull(store.token())
        assertFalse(store.hasToken())
        assertNull(KeystoreSettings(context).token())
    }

    @Test
    fun a_blank_token_is_absent_rather_than_present_and_empty() {
        store.saveToken("   ")

        // Absent means unknown, never "no": an empty string that reads as a
        // set token would send Authorization: Bearer  and get a confusing 401
        // instead of the app saying there is no token.
        assertNull(store.token())
        assertFalse(store.hasToken())
    }

    @Test
    fun surrounding_whitespace_is_trimmed_because_pasting_picks_it_up() {
        store.saveToken("  $TOKEN\n")

        assertEquals(TOKEN, store.token())
    }

    @Test
    fun the_settings_round_trip_and_defaults_survive_a_restart() {
        val wanted = AppSettings(
            repoOwner = "someone",
            repoName = "some-repo",
            workflowFile = "other.yml",
            pollMinutes = 180,
            notifyOnResults = false,
            notifyOnFailures = true,
            pollOnMetered = true,
        )
        store.save(wanted)

        assertEquals(wanted, KeystoreSettings(context).settings())
    }

    @Test
    fun settings_and_the_token_do_not_overwrite_each_other() {
        // They share one encrypted file. Saving settings must not drop the
        // token, which would log the user out every time they changed the
        // poll interval.
        store.saveToken(TOKEN)
        store.save(AppSettings(pollMinutes = 60))

        assertEquals(TOKEN, store.token())
        assertEquals(60, store.settings().pollMinutes)
    }

    private companion object {
        /** Synthetic, and shaped like the real thing so the scan is realistic. */
        const val TOKEN = "github_pat_11INSTRUMENTED0abcdefghij_ZYXWVUTSRQPONMLKJIHGFEDCBA01"

        /** Skip anything large enough to be a database page cache or a lock. */
        const val MAX_SCANNED_BYTES = 8L * 1024 * 1024
    }
}
