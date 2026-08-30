package com.gs3.marketingops.domain.outreach

import org.junit.jupiter.api.Assertions.assertEquals
import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertNull
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class WhatsAppLinkTest {

    @Test
    fun `a number written any of the usual ways reaches the same client`() {
        // All four of these are how the same Jordanian mobile gets written in
        // practice, and three of them produce a dead wa.me link untouched.
        listOf(
            "+962 79073 0903",
            "+962790730903",
            "00962790730903",
            "0790730903",
        ).forEach { written ->
            assertEquals("962790730903", WhatsAppLink.normalisePhone(written), "failed for: $written")
        }
    }

    @Test
    fun `an international number keeps its own country code`() {
        assertEquals("14165551234", WhatsAppLink.normalisePhone("+1 416 555 1234"))
        assertEquals("971501234567", WhatsAppLink.normalisePhone("+971 50 123 4567"))
    }

    @Test
    fun `a number already carrying the country code is not given a second one`() {
        // The branch no test reached until a QA pass went looking. It is not
        // hypothetical: a salesperson copying a number out of a listing or a
        // CRM gets "962790730903" with no plus and no leading zero.
        //
        // What makes it worth a test is how it fails. Without this branch the
        // number falls through to the default and becomes
        // "962962790730903" -- fifteen digits, which passes the E.164 length
        // check and produces a wa.me link that looks perfectly valid and
        // reaches nobody. A wrong number that validates is worse than a null.
        assertEquals("962790730903", WhatsAppLink.normalisePhone("962790730903"))
        assertEquals("962790730903", WhatsAppLink.normalisePhone("962 79 073 0903"))
        assertEquals("971501234567", WhatsAppLink.normalisePhone("971501234567", defaultCountryCode = "971"))
    }

    @Test
    fun `nonsense returns null rather than a dead link`() {
        assertNull(WhatsAppLink.normalisePhone(""))
        assertNull(WhatsAppLink.normalisePhone("   "))
        assertNull(WhatsAppLink.normalisePhone("call me"))
        assertNull(WhatsAppLink.normalisePhone("+1"))
    }

    @Test
    fun `the deep link carries no plus, spaces or dashes`() {
        val url = WhatsAppLink.deepLink("+962 79073-0903", "Hello")
        assertEquals("https://wa.me/962790730903?text=Hello", url)
        assertFalse(url!!.substringBefore("?").contains("+"))
    }

    @Test
    fun `spaces encode as percent-twenty, not as a plus sign`() {
        // URLEncoder emits "+" for a space, which wa.me renders literally. The
        // client would receive "Unit+6+is+available".
        val url = WhatsAppLink.deepLink("962790730903", "Unit 6 is available")!!
        assertTrue(url.contains("Unit%20 6%20is%20available".replace(" ", "")), "actual: $url")
        assertFalse(url.substringAfter("?text=").contains("+"))
    }

    @Test
    fun `Arabic survives the round trip`() {
        val message = "الشقة رقم ٦ متاحة"
        val url = WhatsAppLink.deepLink("962790730903", message)!!
        val decoded = java.net.URLDecoder.decode(url.substringAfter("?text="), Charsets.UTF_8)
        assertEquals(message, decoded)
    }

    @Test
    fun `no WhatsApp means the share sheet, never a crash or a blank screen`() {
        val target = WhatsAppLink.shareTarget("962790730903", "مرحباً", whatsAppInstalled = false)
        assertTrue(target is ShareTarget.SystemShareSheet)
        assertEquals("مرحباً", (target as ShareTarget.SystemShareSheet).text)
    }

    @Test
    fun `an unusable number also falls back rather than failing silently`() {
        val target = WhatsAppLink.shareTarget("not a number", "مرحباً", whatsAppInstalled = true)
        assertTrue(target is ShareTarget.SystemShareSheet)
    }

    @Test
    fun `a good number with WhatsApp installed opens WhatsApp`() {
        val target = WhatsAppLink.shareTarget("0790730903", "Hello", whatsAppInstalled = true)
        assertTrue(target is ShareTarget.WhatsApp)
        assertTrue((target as ShareTarget.WhatsApp).url.startsWith("https://wa.me/962790730903"))
    }
}

class MessageTemplateTest {

    private val template = MessageTemplate(
        "unit_card",
        "الشقة {unit_number} — {area} م² — {price} د.أ\n{link}\n{contact}",
    )

    @Test
    fun `placeholders are found`() {
        assertEquals(
            setOf("unit_number", "area", "price", "link", "contact"),
            template.placeholders(),
        )
    }

    @Test
    fun `a missing value fails loudly instead of shipping a literal brace to a client`() {
        val partial = mapOf("unit_number" to "6", "area" to "151")
        assertEquals(setOf("price", "link", "contact"), template.missingFrom(partial))
        assertNull(template.render(partial))
    }

    @Test
    fun `a complete set renders`() {
        val rendered = template.render(
            mapOf(
                "unit_number" to "٦",
                "area" to "١٥١",
                "price" to "٩٠٬٠٠٠",
                "link" to "https://general-sherman-housing.com/",
                "contact" to "+962790730903",
            )
        )
        assertEquals(
            "الشقة ٦ — ١٥١ م² — ٩٠٬٠٠٠ د.أ\nhttps://general-sherman-housing.com/\n+962790730903",
            rendered,
        )
    }

    @Test
    fun `every unit variable the brief names is supported`() {
        assertEquals(
            setOf("unit_number", "area", "price", "external_area", "link", "contact"),
            MessageTemplate.UNIT_VARIABLES,
        )
    }
}

class NurtureSequenceTest {

    @Test
    fun `the sequence runs day zero to day thirty`() {
        val offsets = NurtureStep.sequence.map { it.dayOffset }
        assertEquals(offsets.sorted(), offsets)
        assertEquals(0, offsets.first())
        assertEquals(30, offsets.last())
    }

    @Test
    fun `only the acknowledgement is automatic — a human sends everything else`() {
        // An automated message to someone considering a six-figure purchase
        // reads as exactly what it is.
        assertEquals(1, NurtureStep.entries.count { it.isAutomaticAcknowledgement })
        assertEquals(NurtureStep.AUTO_ACKNOWLEDGEMENT, NurtureStep.entries.first { it.isAutomaticAcknowledgement })
        assertEquals(NurtureStep.entries.size - 1, NurtureStep.humanSent.size)
    }
}

class CopyRuleCheckerTest {

    private fun check(copy: String, rendered: Boolean = false) =
        CopyRuleChecker.check(copy, district = "مرج الحمام", price = "90,000", area = "151", mentionsRenderedImage = rendered)

    @Test
    fun `good copy passes every rule`() {
        val copy = """
            شقة ١٥١ م² في مرج الحمام بسعر 90,000 د.أ
            تشطيبات فاخرة، كراج ومستودع خاص لكل شقة.
            للاستفسار تواصلوا معنا.
        """.trimIndent()
        val checks = check(copy)
        assertTrue(CopyRuleChecker.isPublishable(checks), checks.filterNot { it.satisfied }.toString())
    }

    @Test
    fun `price, area and district must be in the first two lines`() {
        val buried = """
            فرصة لا تُفوَّت في عمّان الغربية
            تشطيبات فاخرة وموقع مميّز
            المساحة 151 م² والسعر 90,000 د.أ في مرج الحمام
        """.trimIndent()
        val essentials = check(buried).first { it.rule == CopyRule.ESSENTIALS_UP_FRONT }
        assertFalse(essentials.satisfied)
    }

    @Test
    fun `absolute claims are caught in both languages`() {
        assertFalse(check("The best apartment, 151 m2, 90,000, مرج الحمام").first { it.rule == CopyRule.NO_ABSOLUTE_CLAIMS }.satisfied)
        assertFalse(check("الأرخص في مرج الحمام 151 90,000").first { it.rule == CopyRule.NO_ABSOLUTE_CLAIMS }.satisfied)
    }

    @Test
    fun `a rendered image must say so`() {
        val unlabelled = check("151 م² 90,000 مرج الحمام\nصور المشروع", rendered = true)
        assertFalse(unlabelled.first { it.rule == CopyRule.RENDERED_IMAGE_LABELLED }.satisfied)

        val labelled = check("151 م² 90,000 مرج الحمام\nصور الواجهات تصاميم ثلاثية الأبعاد", rendered = true)
        assertTrue(labelled.first { it.rule == CopyRule.RENDERED_IMAGE_LABELLED }.satisfied)
    }

    @Test
    fun `naming Al-Andalus without the qualifier fails, in either language`() {
        // The hospital is not built. Saying so is not optional.
        val bare = check("151 م² 90,000 مرج الحمام\nبالقرب من مستشفى الأندلس")
        assertFalse(bare.first { it.rule == CopyRule.UNDER_CONSTRUCTION_QUALIFIED }.satisfied)

        val qualified = check("151 م² 90,000 مرج الحمام\nبالقرب من مستشفى الأندلس (قيد الإنشاء)")
        assertTrue(qualified.first { it.rule == CopyRule.UNDER_CONSTRUCTION_QUALIFIED }.satisfied)

        val english = check("151 m2 90,000 مرج الحمام\nNear Al-Andalus Hospital (under construction)")
        assertTrue(english.first { it.rule == CopyRule.UNDER_CONSTRUCTION_QUALIFIED }.satisfied)
    }

    @Test
    fun `Arabic-Indic digits count as the same number`() {
        // The app offers ٠-٩ as a numerals setting, so an Arabic ad reasonably
        // says «١٥١ م²» while the unit record holds 151. Matching the two
        // literally reports the area as missing on copy that is perfectly
        // correct, and a checklist that cries wolf gets ignored.
        val arabicDigits = "شقة ١٥١ م² في مرج الحمام بسعر ٩٠٬٠٠٠ د.أ\nتشطيبات فاخرة."
        val essentials = check(arabicDigits).first { it.rule == CopyRule.ESSENTIALS_UP_FRONT }
        assertTrue(essentials.satisfied, essentials.detail ?: "")
    }

    @Test
    fun `thousands separators do not defeat the match`() {
        val spaced = "151 م² في مرج الحمام بسعر 90 000 د.أ\nتشطيبات."
        assertTrue(check(spaced).first { it.rule == CopyRule.ESSENTIALS_UP_FRONT }.satisfied)
    }

    @Test
    fun `the rendered-image marker survives Arabic inflection`() {
        // The company's own site writes «تصاميم ثلاثية الأبعاد» — plural and
        // feminine. Markers matched as whole words would miss both.
        assertEquals("151", CopyRuleChecker.foldDigits("١٥١"))
        assertEquals("90000", CopyRuleChecker.foldDigits("٩٠٬٠٠٠"))
    }

    @Test
    fun `copy that never mentions the hospital passes that rule trivially`() {
        val checks = check("151 م² 90,000 مرج الحمام\nتشطيبات فاخرة")
        assertTrue(checks.first { it.rule == CopyRule.UNDER_CONSTRUCTION_QUALIFIED }.satisfied)
    }
}
