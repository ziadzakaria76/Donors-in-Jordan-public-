package com.gs3.marketingops.domain.outreach

/**
 * A rule the ad copy must satisfy, shown as a live checklist while writing
 * rather than as a rejection after the fact.
 *
 * The distinction matters: a checklist that updates as you type teaches the
 * rule, while a validator that refuses to save teaches people to write in a
 * text editor and paste it in.
 */
enum class CopyRule {
    /** Price, area and district must appear within the first two lines. */
    ESSENTIALS_UP_FRONT,

    /** No absolute unprovable claims — "the best", "the cheapest", "number one". */
    NO_ABSOLUTE_CLAIMS,

    /** A rendered or illustrative image must be labelled as such. */
    RENDERED_IMAGE_LABELLED,

    /** A hospital that is not built yet must be described as under construction. */
    UNDER_CONSTRUCTION_QUALIFIED,
}

data class CopyCheck(val rule: CopyRule, val satisfied: Boolean, val detail: String? = null)

object CopyRuleChecker {

    /**
     * Superlatives that cannot be substantiated, in both languages. The Arabic
     * is what the team will actually type, so it is not an afterthought.
     */
    private val absoluteClaims = listOf(
        "the best", "the cheapest", "number one", "no.1", "unbeatable", "guaranteed",
        "الأفضل", "الأرخص", "الأول", "رقم واحد", "لا يُضاهى", "مضمون",
    )

    /**
     * Markers are stems, not whole words.
     *
     * Arabic inflects: the company's own site says «صور الواجهات تصاميم ثلاثية
     * الأبعاد», and neither «تصميم» nor «ثلاثي الأبعاد» is a substring of that.
     * Matching on «تصام»/«تصمي» and «ثلاثي» catches the singular and the plural,
     * the masculine and the feminine, without a morphological analyser.
     */
    private val renderedImageMarkers = listOf(
        "3d", "render", "illustrative", "design study",
        "تصمي", "تصام", "ثلاثي", "تصويري",
    )

    private val underConstructionMarkers = listOf("under construction", "قيد الإنشاء")

    /** Hospitals and facilities that are not open yet and must always be qualified. */
    private val notYetBuilt = listOf("al-andalus", "الأندلس")

    /**
     * Folds Arabic-Indic digits to Western and drops thousands separators.
     *
     * Without this the checker fails on correct copy. The app offers ٠-٩ as a
     * numerals setting, so an Arabic ad reasonably says «١٥١ م²» while the unit
     * record holds `151` — a naive substring match reports the area as missing
     * and trains the writer to ignore the checklist.
     */
    internal fun foldDigits(text: String): String = buildString {
        text.forEach { character ->
            when (character) {
                in '٠'..'٩' -> append('0' + (character - '٠'))
                in '۰'..'۹' -> append('0' + (character - '۰'))   // Extended Arabic-Indic (Persian/Urdu)
                ',', '٬', ' ', ' ' -> Unit                   // grouping, not content
                else -> append(character)
            }
        }
    }

    fun check(
        copy: String,
        district: String,
        price: String,
        area: String,
        mentionsRenderedImage: Boolean = false,
    ): List<CopyCheck> {
        val lowered = copy.lowercase()
        val firstTwoLines = foldDigits(copy.lineSequence().take(2).joinToString(" ").lowercase())

        val essentials = listOf(
            "price" to price,
            "area" to area,
            "district" to district,
        ).filter { (_, value) ->
            value.isNotBlank() && !firstTwoLines.contains(foldDigits(value.lowercase()))
        }

        val claims = absoluteClaims.filter { lowered.contains(it.lowercase()) }

        val renderedOk = !mentionsRenderedImage ||
            renderedImageMarkers.any { lowered.contains(it) }

        // Only demanded when the copy actually names something unbuilt. A
        // general-purpose ad that never mentions the hospital passes trivially.
        val namesUnbuilt = notYetBuilt.filter { lowered.contains(it) }
        val underConstructionOk = namesUnbuilt.isEmpty() ||
            underConstructionMarkers.any { lowered.contains(it) }

        return listOf(
            CopyCheck(
                CopyRule.ESSENTIALS_UP_FRONT,
                essentials.isEmpty(),
                essentials.takeIf { it.isNotEmpty() }?.joinToString(", ") { it.first },
            ),
            CopyCheck(
                CopyRule.NO_ABSOLUTE_CLAIMS,
                claims.isEmpty(),
                claims.takeIf { it.isNotEmpty() }?.joinToString(", "),
            ),
            CopyCheck(CopyRule.RENDERED_IMAGE_LABELLED, renderedOk),
            CopyCheck(
                CopyRule.UNDER_CONSTRUCTION_QUALIFIED,
                underConstructionOk,
                namesUnbuilt.takeIf { !underConstructionOk }?.joinToString(", "),
            ),
        )
    }

    fun isPublishable(checks: List<CopyCheck>): Boolean = checks.all { it.satisfied }
}
