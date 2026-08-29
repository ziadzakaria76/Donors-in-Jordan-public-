package jo.tendermonitor.data.portals

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject

/**
 * `portals.json`, edited as a tree rather than as a typed object.
 *
 * THIS IS THE POINT OF THE CLASS. Deserialising into a data class and
 * re-serialising would silently delete every field this app does not model --
 * `code_owned`, `no_listing_reason`, the long `notes` that carry why a portal
 * is configured as it is, and the `_readme` block at the top of the file.
 * Those are the most valuable things in it, and losing them would look exactly
 * like a successful save.
 *
 * So an edit touches the one key it means to touch and leaves the rest of the
 * document byte-for-byte alone. What this app cannot render, it also cannot
 * destroy.
 */
object PortalsFile {

    /** The path in the repository. Also what the commit message names. */
    const val PATH = "jordan_tender_monitor/portals.json"

    // prettyPrintIndent is still marked experimental. Opted in explicitly
    // rather than left as a warning: the two-space indent is what keeps a
    // portals.json edited from a phone diffing cleanly against one edited by
    // hand, and an unannotated experimental call is the kind that disappears
    // in a library upgrade with no warning that the formatting changed.
    @OptIn(ExperimentalSerializationApi::class)
    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = false
        prettyPrint = true
        prettyPrintIndent = "  "
    }

    private val parser = Json { ignoreUnknownKeys = true; isLenient = false }

    /** One entry, as much of it as the app understands. */
    data class Entry(
        val key: String,
        val name: String,
        val enabled: Boolean,
        val tier: Int,
        val urls: List<String>,
        /** Non-empty when the portal's fetch logic lives in a module. */
        val module: String,
        /** Fields that module owns; the file must not set them. */
        val codeOwned: List<String>,
        val selectors: List<String>,
        val noListingReason: String,
        val notes: String,
    ) {
        val isDataOnly: Boolean get() = module.isEmpty()

        /**
         * True when this app would be editing something it cannot see the
         * consequences of. A module-backed portal can be toggled and renamed,
         * but its extraction is code and is not editable from here.
         */
        val isCodeBacked: Boolean get() = module.isNotEmpty()
    }

    data class Document(val root: JsonObject, val entries: List<Entry>)

    class MalformedException(message: String) : Exception(message)

    fun parse(text: String): Document {
        val root = try {
            parser.parseToJsonElement(text).jsonObject
        } catch (error: Exception) {
            throw MalformedException(
                "portals.json is not a JSON object: ${error.message.orEmpty().take(160)}"
            )
        }
        val array = root["portals"] as? JsonArray
            ?: throw MalformedException(
                "portals.json has no \"portals\" array. This app will not " +
                    "rewrite a file it cannot recognise."
            )
        return Document(root, array.map { it.jsonObject.toEntry() })
    }

    fun serialise(root: JsonObject): String =
        // A trailing newline, because every other file in the repository has
        // one and a diff that flips it is noise in a commit that should be
        // about a portal.
        json.encodeToString(JsonObject.serializer(), root) + "\n"

    // -----------------------------------------------------------------------
    // Edits. Each returns a new root; none mutates.
    // -----------------------------------------------------------------------

    fun withEnabled(root: JsonObject, key: String, enabled: Boolean): JsonObject =
        mapEntries(root) { entry ->
            if (entry.stringOf("key") == key) {
                JsonObject(entry.toMutableMap().apply {
                    put("enabled", JsonPrimitive(enabled))
                })
            } else {
                entry
            }
        }

    fun withRemoved(root: JsonObject, key: String): JsonObject {
        val kept = (root["portals"] as JsonArray)
            .filter { it.jsonObject.stringOf("key") != key }
        return JsonObject(root.toMutableMap().apply {
            put("portals", JsonArray(kept))
        })
    }

    /**
     * Append a new entry.
     *
     * Appended rather than sorted in: the file's order is the order portals
     * are polled and reported, and quietly reordering thirteen existing lines
     * to insert one would make the diff unreadable — which is the diff someone
     * has to check when a run goes wrong.
     */
    fun withAdded(root: JsonObject, entry: JsonObject): JsonObject {
        val existing = (root["portals"] as JsonArray).toMutableList()
        existing += entry
        return JsonObject(root.toMutableMap().apply {
            put("portals", JsonArray(existing))
        })
    }

    fun hasKey(root: JsonObject, key: String): Boolean =
        (root["portals"] as? JsonArray)?.any { it.jsonObject.stringOf("key") == key } == true

    /**
     * Build an entry from what the Add form collected.
     *
     * Optional fields are omitted rather than written empty: the loader treats
     * an absent `anchor_hint` and a null one identically, but a file full of
     * empty strings is harder to read, and this file is meant to be read.
     */
    fun buildEntry(
        key: String,
        name: String,
        urls: List<String>,
        tier: Int = 2,
        enabled: Boolean = true,
        selectors: List<String> = emptyList(),
        anchorHint: String? = null,
        currency: String? = null,
        filterToJordan: Boolean = true,
        notes: String = "",
    ): JsonObject = buildJsonObject {
        put("key", JsonPrimitive(key))
        put("name", JsonPrimitive(name))
        put("enabled", JsonPrimitive(enabled))
        put("tier", JsonPrimitive(tier))
        put("urls", buildJsonArray { urls.forEach { add(JsonPrimitive(it)) } })
        if (selectors.isNotEmpty()) {
            put("selectors", buildJsonArray { selectors.forEach { add(JsonPrimitive(it)) } })
        }
        if (!anchorHint.isNullOrBlank()) put("anchor_hint", JsonPrimitive(anchorHint))
        if (!currency.isNullOrBlank()) put("currency", JsonPrimitive(currency))
        put("filter_to_jordan", JsonPrimitive(filterToJordan))
        if (notes.isNotBlank()) put("notes", JsonPrimitive(notes))
    }

    private fun mapEntries(root: JsonObject, transform: (JsonObject) -> JsonObject): JsonObject {
        val mapped = (root["portals"] as JsonArray).map { transform(it.jsonObject) }
        return JsonObject(root.toMutableMap().apply { put("portals", JsonArray(mapped)) })
    }

    private fun JsonObject.toEntry(): Entry = Entry(
        key = stringOf("key"),
        name = stringOf("name").ifBlank { stringOf("key") },
        enabled = boolOf("enabled", default = true),
        tier = intOf("tier", default = 2),
        urls = stringsOf("urls"),
        module = stringOf("module"),
        codeOwned = stringsOf("code_owned"),
        selectors = stringsOf("selectors"),
        noListingReason = stringOf("no_listing_reason"),
        notes = stringOf("notes"),
    )

    private fun JsonObject.stringOf(key: String): String =
        (this[key] as? JsonPrimitive)?.contentOrNull.orEmpty()

    private fun JsonObject.boolOf(key: String, default: Boolean): Boolean =
        (this[key] as? JsonPrimitive)?.booleanOrNull ?: default

    private fun JsonObject.intOf(key: String, default: Int): Int =
        (this[key] as? JsonPrimitive)?.intOrNull ?: default

    private fun JsonObject.stringsOf(key: String): List<String> =
        (this[key] as? JsonArray)
            ?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }
            .orEmpty()
}

/**
 * The same rules `portal_config.py` enforces, applied before a commit is made.
 *
 * NOT a substitute for the backend's validation -- that one decides. This one
 * exists so that an entry which would be rejected on load never becomes a
 * commit in the first place, because a commit that breaks the next run is a
 * worse outcome than a form that says no.
 */
object EntryRules {

    private val KEY = Regex("^[a-z0-9][a-z0-9_-]{0,39}$")

    fun keyProblem(key: String, existing: List<String>): String? = when {
        key.isBlank() -> "A key is required. It is how the portal is named in " +
            "the run, in --only, and in the output filename."
        !KEY.matches(key) -> "Keys are lower-case letters, digits, '_' or '-', " +
            "starting with a letter or digit. \"$key\" is not."
        key in existing -> "\"$key\" is already used by another portal."
        else -> null
    }

    fun urlProblem(urls: List<String>): String? = when {
        urls.isEmpty() -> "At least one listing URL is required. A portal with " +
            "no source would report as broken on every run."
        urls.any { !it.startsWith("http://") && !it.startsWith("https://") } ->
            "Every URL must start with http:// or https://."
        else -> null
    }

    fun tierProblem(tier: Int): String? =
        if (tier in 1..3) null
        else "Tier must be 1 (API), 2 (HTML) or 3 (announcements only)."
}
