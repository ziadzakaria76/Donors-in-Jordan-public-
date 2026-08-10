package com.gs3.marketingops.domain.export

/**
 * CSV that survives being opened in Excel on Windows, which is where these
 * files actually get opened.
 *
 * The byte-order mark is the whole point. Without it Excel reads a UTF-8 file
 * as the machine's legacy code page, and every Arabic string arrives as
 * mojibake — while the file is perfectly valid and looks correct in every other
 * tool, so the bug gets blamed on the person who opened it. Three bytes fix it.
 */
object CsvWriter {

    /** UTF-8 BOM: EF BB BF. */
    val BOM: ByteArray = byteArrayOf(0xEF.toByte(), 0xBB.toByte(), 0xBF.toByte())

    /**
     * Excel splits on the list separator of the user's locale, and in Arabic
     * and many European locales that is a semicolon, not a comma. The comma
     * stays the default because it is what every other tool expects; the
     * separator is a parameter so an Arabic Excel user can be given a file that
     * opens in columns rather than in one.
     */
    const val DEFAULT_SEPARATOR: Char = ','

    fun write(
        headers: List<String>,
        rows: List<List<String>>,
        separator: Char = DEFAULT_SEPARATOR,
    ): ByteArray {
        require(headers.isNotEmpty()) { "A CSV needs at least one column" }
        rows.forEachIndexed { index, row ->
            require(row.size == headers.size) {
                "Row $index has ${row.size} cells but there are ${headers.size} columns"
            }
        }

        val text = buildString {
            append(escapeRow(headers, separator))
            rows.forEach { row ->
                // CRLF, because that is what the CSV spec says and what Excel expects.
                append("\r\n")
                append(escapeRow(row, separator))
            }
        }
        return BOM + text.toByteArray(Charsets.UTF_8)
    }

    private fun escapeRow(cells: List<String>, separator: Char): String =
        cells.joinToString(separator.toString()) { escapeCell(it, separator) }

    /**
     * Quotes a cell when it contains the separator, a quote or a line break,
     * doubling any embedded quotes.
     *
     * A leading `=`, `+`, `-` or `@` is also quoted and prefixed with a single
     * quote: Excel treats such a cell as a formula, so a note beginning
     * "=" or a phone number written "+962…" becomes either a broken formula or,
     * with an unlucky payload, a spreadsheet that runs something. A sales note
     * is data and should never be executable.
     */
    private fun escapeCell(cell: String, separator: Char): String {
        val deFanged = if (cell.isNotEmpty() && cell.first() in FORMULA_TRIGGERS) "'$cell" else cell
        val mustQuote = deFanged.any { it == separator || it == '"' || it == '\n' || it == '\r' } ||
            deFanged != cell
        return if (mustQuote) "\"${deFanged.replace("\"", "\"\"")}\"" else deFanged
    }

    private val FORMULA_TRIGGERS = setOf('=', '+', '-', '@')
}
