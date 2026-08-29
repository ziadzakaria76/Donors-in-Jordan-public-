package jo.tendermonitor.data.report

import java.io.File
import java.io.InputStream
import java.util.zip.ZipInputStream

/**
 * Artifacts arrive as a zip, always -- even when there is one file inside.
 *
 * Two properties this has to hold, both of them about not lying:
 *
 *  * **A capped read says it was capped.** [readTextEntry] will not load an
 *    unbounded file into memory on a handset, and if it stops early it returns
 *    null rather than a truncated document that would parse as a shorter
 *    report.
 *  * **A path from a zip is not trusted.** An entry named `../../x` would
 *    write outside the target directory. Every extracted name is checked
 *    against the destination before anything is written.
 */
object ArtifactZip {

    /** Beyond this a report is not a report; it is something else. */
    const val MAX_TEXT_BYTES = 24 * 1024 * 1024

    data class Entry(val name: String, val size: Long)

    /**
     * The first entry whose name matches, decoded as UTF-8.
     *
     * @return null if no entry matched, or if the match was larger than
     *   [MAX_TEXT_BYTES] -- callers must treat null as "not read", never as
     *   "empty".
     */
    fun readTextEntry(zip: InputStream, matches: (String) -> Boolean): String? {
        ZipInputStream(zip.buffered()).use { stream ->
            var entry = stream.nextEntry
            while (entry != null) {
                if (!entry.isDirectory && matches(entry.name)) {
                    val bytes = stream.readAtMost(MAX_TEXT_BYTES) ?: return null
                    return String(bytes, Charsets.UTF_8)
                }
                stream.closeEntry()
                entry = stream.nextEntry
            }
        }
        return null
    }

    /**
     * Extract every entry into [target], returning what was written.
     *
     * Entries that would escape [target] are skipped and named in
     * [skipped] -- silently dropping one would leave a file list that does not
     * match what is on disk.
     */
    fun extractAll(
        zip: InputStream,
        target: File,
        skipped: MutableList<String> = mutableListOf(),
    ): List<File> {
        target.mkdirs()
        val canonicalTarget = target.canonicalFile
        val written = mutableListOf<File>()

        ZipInputStream(zip.buffered()).use { stream ->
            var entry = stream.nextEntry
            while (entry != null) {
                if (!entry.isDirectory) {
                    // Flatten: these artifacts are a handful of files in one
                    // folder, and a nested path from an untrusted archive buys
                    // nothing but a traversal check to get wrong.
                    val name = File(entry.name).name
                    val destination = File(canonicalTarget, name)
                    if (destination.canonicalFile.parentFile != canonicalTarget) {
                        skipped += entry.name
                    } else {
                        destination.outputStream().buffered().use { out ->
                            stream.copyTo(out)
                        }
                        written += destination
                    }
                }
                stream.closeEntry()
                entry = stream.nextEntry
            }
        }
        return written
    }

    /** Reads up to [limit] bytes, or returns null if the stream has more. */
    private fun InputStream.readAtMost(limit: Int): ByteArray? {
        val buffer = ByteArray(64 * 1024)
        val out = java.io.ByteArrayOutputStream()
        while (true) {
            val read = read(buffer)
            if (read <= 0) break
            if (out.size() + read > limit) return null
            out.write(buffer, 0, read)
        }
        return out.toByteArray()
    }

    /** The report file inside a run's artifact, by name. */
    fun isReportJson(name: String): Boolean =
        name.endsWith(".json", ignoreCase = true) && name.contains("jordan_tenders")

    fun isDocx(name: String): Boolean = name.endsWith(".docx", ignoreCase = true)

    fun isXlsx(name: String): Boolean = name.endsWith(".xlsx", ignoreCase = true)
}
