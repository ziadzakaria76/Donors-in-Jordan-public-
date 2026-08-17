package com.gs3.marketingops.campaigns.data

import androidx.room.Entity
import androidx.room.PrimaryKey
import com.gs3.marketingops.domain.budget.MarketAllocation
import com.gs3.marketingops.domain.funnel.Track
import com.gs3.marketingops.domain.money.Jod

/**
 * The annual paid-media budget for one market.
 *
 * **Annual only.** The monthly figure is derived on demand and never stored —
 * D-4. The brief's own monthly column is the annual figure ÷ 12 rounded, and
 * those roundings do not re-sum: the expatriate rows total 389 JOD against a
 * true 390. Storing the monthly numbers would let a rounding artefact
 * accumulate into a twelve-dinar hole in a plan that is supposed to balance.
 *
 * `marketKey` is a code — `UAE`, `IRQ`, `GULF` — not a display name. The
 * name a user reads comes from `strings.xml` in their language, so the same row
 * reads «الإمارات» and "UAE" without the database holding either.
 */
@Entity(tableName = "market_budgets")
data class MarketBudgetEntity(
    @PrimaryKey val marketKey: String,
    val track: String,
    val annualFils: Long,
) {
    fun toDomain(): MarketAllocation = MarketAllocation(
        track = Track.valueOf(track),
        marketKey = marketKey,
        annual = Jod.ofFils(annualFils),
    )

    internal companion object {
        fun fromDomain(allocation: MarketAllocation): MarketBudgetEntity = MarketBudgetEntity(
            marketKey = allocation.marketKey,
            track = allocation.track.name,
            annualFils = allocation.annual.fils,
        )
    }
}
