package jo.tendermonitor.data.settings

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

/**
 * Everything the app is configured with, and where the token lives.
 *
 * THE TOKEN IS NEVER IN PLAIN SHARED PREFERENCES. It is written to
 * EncryptedSharedPreferences, whose keys are held by the Android Keystore --
 * hardware-backed where the device has a TEE or StrongBox, and in no case
 * readable from the app's data directory by a file copy.
 *
 * It is also never in the APK, never in source, never in a log line and never
 * in an error the UI shows: see [Redact], which every failure path runs
 * through.
 */
data class AppSettings(
    val repoOwner: String = DEFAULT_OWNER,
    val repoName: String = DEFAULT_REPO,
    val workflowFile: String = DEFAULT_WORKFLOW,
    /** Phase 3. Minutes between background checks; 0 disables them. */
    val pollMinutes: Int = 0,
    val notifyOnResults: Boolean = true,
    val notifyOnFailures: Boolean = true,
    /**
     * Off by default. Polling a metered connection to find out that nothing
     * has changed is someone's data allowance, spent without being asked.
     */
    val pollOnMetered: Boolean = false,
) {
    val repoSlug: String get() = "$repoOwner/$repoName"

    val isComplete: Boolean
        get() = repoOwner.isNotBlank() && repoName.isNotBlank() && workflowFile.isNotBlank()

    companion object {
        const val DEFAULT_OWNER = "ziadzakaria76"
        const val DEFAULT_REPO = "Donors-in-Jordan-public-"
        const val DEFAULT_WORKFLOW = "monitor.yml"
    }
}

/** Split out so the parts that are not the Keystore can be unit tested. */
interface TokenStore {
    fun token(): String?
    fun saveToken(value: String?)
    fun hasToken(): Boolean = !token().isNullOrBlank()
}

interface SettingsStore {
    fun settings(): AppSettings
    fun save(settings: AppSettings)
}

/**
 * The real store. One encrypted file holds the token and the settings alike --
 * the settings are not secret, but a second unencrypted file would be one more
 * thing to get wrong for no benefit.
 *
 * NOT COVERED BY A UNIT TEST: EncryptedSharedPreferences needs the Android
 * Keystore, which does not exist on a JVM. The logic that can be tested off
 * the device -- redaction, validation, defaults -- is deliberately not in this
 * class. What this class does is call two AndroidX methods.
 */
class KeystoreSettings(context: Context) : TokenStore, SettingsStore {

    private val prefs: SharedPreferences by lazy {
        val key = MasterKey.Builder(context)
            .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
            .build()
        EncryptedSharedPreferences.create(
            context,
            FILE_NAME,
            key,
            EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
            EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
        )
    }

    override fun token(): String? = prefs.getString(KEY_TOKEN, null)?.takeIf { it.isNotBlank() }

    override fun saveToken(value: String?) {
        prefs.edit().apply {
            if (value.isNullOrBlank()) remove(KEY_TOKEN) else putString(KEY_TOKEN, value.trim())
        }.apply()
    }

    override fun settings(): AppSettings = AppSettings(
        repoOwner = prefs.getString(KEY_OWNER, AppSettings.DEFAULT_OWNER)
            ?: AppSettings.DEFAULT_OWNER,
        repoName = prefs.getString(KEY_REPO, AppSettings.DEFAULT_REPO)
            ?: AppSettings.DEFAULT_REPO,
        workflowFile = prefs.getString(KEY_WORKFLOW, AppSettings.DEFAULT_WORKFLOW)
            ?: AppSettings.DEFAULT_WORKFLOW,
        pollMinutes = prefs.getInt(KEY_POLL_MINUTES, 0),
        notifyOnResults = prefs.getBoolean(KEY_NOTIFY_RESULTS, true),
        notifyOnFailures = prefs.getBoolean(KEY_NOTIFY_FAILURES, true),
        pollOnMetered = prefs.getBoolean(KEY_POLL_METERED, false),
    )

    override fun save(settings: AppSettings) {
        prefs.edit()
            .putString(KEY_OWNER, settings.repoOwner.trim())
            .putString(KEY_REPO, settings.repoName.trim())
            .putString(KEY_WORKFLOW, settings.workflowFile.trim())
            .putInt(KEY_POLL_MINUTES, settings.pollMinutes)
            .putBoolean(KEY_NOTIFY_RESULTS, settings.notifyOnResults)
            .putBoolean(KEY_NOTIFY_FAILURES, settings.notifyOnFailures)
            .putBoolean(KEY_POLL_METERED, settings.pollOnMetered)
            .apply()
    }

    private companion object {
        const val FILE_NAME = "jtm-secure"
        const val KEY_TOKEN = "github_token"
        const val KEY_OWNER = "repo_owner"
        const val KEY_REPO = "repo_name"
        const val KEY_WORKFLOW = "workflow_file"
        const val KEY_POLL_MINUTES = "poll_minutes"
        const val KEY_NOTIFY_RESULTS = "notify_results"
        const val KEY_NOTIFY_FAILURES = "notify_failures"
        const val KEY_POLL_METERED = "poll_metered"
    }
}

/**
 * What can be said about a token before spending a request on it.
 *
 * Deliberately does NOT reject anything that merely looks unfamiliar: GitHub
 * has changed its token formats before, and an app that refuses a valid
 * credential because it did not recognise the prefix is worse than one that
 * tries and reports a 401. So this warns and never blocks.
 */
object TokenAdvice {
    fun looksLikeGitHubToken(token: String?): Boolean {
        val value = token?.trim().orEmpty()
        return value.startsWith("github_pat_") || Regex("""^gh[pousr]_\w{20,}$""")
            .matches(value)
    }

    fun warning(token: String?): String? {
        val value = token?.trim().orEmpty()
        if (value.isEmpty()) return null
        if (value.contains(' ') || value.contains('\n')) {
            return "That contains a space or a line break. Pasting from an email " +
                "often picks one up, and GitHub will reject it as invalid."
        }
        if (!looksLikeGitHubToken(value)) {
            return "That does not look like a GitHub token (they start with " +
                "github_pat_ or ghp_). Saving it anyway -- if GitHub rejects it " +
                "you will see 'the token was refused' on the next run."
        }
        return null
    }
}
