package com.gs3.marketingops.domain.content

import java.math.BigDecimal
import java.math.RoundingMode

/**
 * The four content pillars and the mix they are meant to hold.
 *
 * The target exists because the natural drift of a developer's feed is toward
 * 100% product — unit after unit, price after price — which stops working
 * within a month. Trust, education and place are what make the product posts
 * land at all.
 */
enum class ContentPillar(val targetShare: BigDecimal) {
    PRODUCT(BigDecimal("0.40")),
    TRUST(BigDecimal("0.25")),
    EDUCATION(BigDecimal("0.20")),
    PLACE(BigDecimal("0.15")),
}

/** The weekly cadence the plan commits to. */
object WeeklyCadence {
    const val FEED_POSTS = 4
    const val SHORT_VERTICAL_VIDEOS = 3
    const val STORIES_PER_DAY = 1
    const val GROUP_POSTS = 1
    const val BROKER_UPDATES = 1

    /** Everything that must be produced in a week, excluding daily stories. */
    val scheduledItemsPerWeek: Int = FEED_POSTS + SHORT_VERTICAL_VIDEOS + GROUP_POSTS + BROKER_UPDATES
}

data class PillarBalance(
    val pillar: ContentPillar,
    val published: Int,
    val actualShare: BigDecimal,
) {
    val targetShare: BigDecimal get() = pillar.targetShare

    /** Positive means over-represented this month. */
    val drift: BigDecimal get() = actualShare - targetShare

    /** More than ten points off target is worth flagging on the balance meter. */
    val isOffTarget: Boolean get() = drift.abs() > BigDecimal("0.10")
}

object PillarMix {

    /**
     * The month's actual mix against target.
     *
     * With nothing published yet every share is zero rather than undefined —
     * an empty month is not a balanced one, and the meter should say so.
     */
    fun balance(published: Map<ContentPillar, Int>): List<PillarBalance> {
        val total = ContentPillar.entries.sumOf { published[it] ?: 0 }
        return ContentPillar.entries.map { pillar ->
            val count = published[pillar] ?: 0
            val share = if (total == 0) BigDecimal.ZERO else
                BigDecimal.valueOf(count.toLong())
                    .divide(BigDecimal.valueOf(total.toLong()), 4, RoundingMode.HALF_UP)
            PillarBalance(pillar, count, share)
        }
    }

    /** Which pillar to write next: the one furthest below its target. */
    fun mostUnderRepresented(published: Map<ContentPillar, Int>): ContentPillar =
        balance(published).minBy { it.drift }.pillar
}

/** The creative assets the campaign depends on, and who owes them. */
enum class AssetKind {
    PROFESSIONAL_PHOTOGRAPHY,
    MAIN_VIDEO,
    PER_MODEL_TOURS,
    VERTICAL_SHORTS,
    DRONE_FOOTAGE,
    THREE_SIXTY_TOUR,
    ENHANCED_FLOOR_PLANS,
    BUYER_TESTIMONIALS,
    MONTHLY_CONSTRUCTION_DOCUMENTATION,
    EXPLAINER_GRAPHICS,
}

enum class AssetStatus { NOT_STARTED, IN_PRODUCTION, DELIVERED }

data class AssetChecklistItem(
    val kind: AssetKind,
    val status: AssetStatus = AssetStatus.NOT_STARTED,
    val owner: String? = null,
)

object AssetChecklist {
    fun initial(): List<AssetChecklistItem> = AssetKind.entries.map { AssetChecklistItem(it) }

    fun completionPercent(items: List<AssetChecklistItem>): BigDecimal {
        if (items.isEmpty()) return BigDecimal.ZERO
        val delivered = items.count { it.status == AssetStatus.DELIVERED }
        return BigDecimal.valueOf(delivered.toLong())
            .divide(BigDecimal.valueOf(items.size.toLong()), 4, RoundingMode.HALF_UP)
            .movePointRight(2)
            .setScale(1, RoundingMode.HALF_UP)
    }
}
