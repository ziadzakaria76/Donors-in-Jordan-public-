package com.gs3.marketingops.domain.export

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

/**
 * The byte-order-mark trap test the brief calls for by name.
 *
 * The failure it guards against is nasty precisely because the file is not
 * broken: it is valid UTF-8, it looks right in every text editor and every
 * other tool, and it only turns into mojibake in Excel on Windows — which is
 * exactly where the team will open it. So the bug gets blamed on the person who
 * opened the file rather than on the file.
 */
class CsvWriterTest {

    @Test
    fun `every export starts with the UTF-8 byte order mark`() {
        val bytes = CsvWriter.write(listOf("unit", "price"), listOf(listOf("6", "90000")))
        assertEquals(0xEF.toByte(), bytes[0])
        assertEquals(0xBB.toByte(), bytes[1])
        assertEquals(0xBF.toByte(), bytes[2])
    }

    @Test
    fun `Arabic survives the round trip byte for byte`() {
        val headers = listOf("الشقة", "الحالة")
        val rows = listOf(listOf("الطابق الأول (الجنوبية)", "متاحة"))
        val bytes = CsvWriter.write(headers, rows)

        val text = String(bytes, Charsets.UTF_8).removePrefix("﻿")
        assertEquals("الشقة,الحالة\r\nالطابق الأول (الجنوبية),متاحة", text)
    }

    @Test
    fun `rows end with CRLF, which is what the spec says and Excel expects`() {
        val bytes = CsvWriter.write(listOf("a"), listOf(listOf("1"), listOf("2")))
        val text = String(bytes, Charsets.UTF_8).removePrefix("﻿")
        assertEquals("a\r\n1\r\n2", text)
    }

    @Test
    fun `a cell containing the separator is quoted`() {
        val bytes = CsvWriter.write(listOf("note"), listOf(listOf("Cash buyer, closing soon")))
        val text = String(bytes, Charsets.UTF_8).removePrefix("﻿")
        assertEquals("note\r\n\"Cash buyer, closing soon\"", text)
    }

    @Test
    fun `embedded quotes are doubled`() {
        val bytes = CsvWriter.write(listOf("note"), listOf(listOf("""He said "no" twice""")))
        val text = String(bytes, Charsets.UTF_8).removePrefix("﻿")
        assertEquals("""note${"\r\n"}"He said ""no"" twice"""", text)
    }

    @Test
    fun `a newline inside a note does not break the row`() {
        val bytes = CsvWriter.write(listOf("note"), listOf(listOf("line one\nline two")))
        val text = String(bytes, Charsets.UTF_8).removePrefix("﻿")
        assertTrue(text.startsWith("note\r\n\""))
        assertTrue(text.endsWith("\""))
    }

    @Test
    fun `a cell that looks like a formula is neutralised`() {
        // A note beginning "=" or a phone number written "+962..." is treated by
        // Excel as a formula. A sales note is data and must never be executable.
        val bytes = CsvWriter.write(
            listOf("phone", "note"),
            listOf(listOf("+962790730903", "=1+1")),
        )
        val text = String(bytes, Charsets.UTF_8).removePrefix("﻿")
        assertTrue(text.contains("\"'+962790730903\""), "actual: $text")
        assertTrue(text.contains("\"'=1+1\""), "actual: $text")
    }

    @Test
    fun `an ordinary cell is not quoted needlessly`() {
        val bytes = CsvWriter.write(listOf("unit"), listOf(listOf("6")))
        val text = String(bytes, Charsets.UTF_8).removePrefix("﻿")
        assertEquals("unit\r\n6", text)
        assertFalse(text.contains("\""))
    }

    @Test
    fun `a semicolon separator is available for locales where Excel expects one`() {
        val bytes = CsvWriter.write(listOf("a", "b"), listOf(listOf("1", "2")), separator = ';')
        val text = String(bytes, Charsets.UTF_8).removePrefix("﻿")
        assertEquals("a;b\r\n1;2", text)
    }

    @Test
    fun `a ragged row is rejected rather than written out misaligned`() {
        val thrown = runCatching {
            CsvWriter.write(listOf("a", "b"), listOf(listOf("1")))
        }.exceptionOrNull()
        assertTrue(thrown is IllegalArgumentException)
    }

    @Test
    fun `headers alone are a valid export`() {
        val bytes = CsvWriter.write(listOf("unit", "price"), emptyList())
        assertEquals("unit,price", String(bytes, Charsets.UTF_8).removePrefix("﻿"))
    }
}
