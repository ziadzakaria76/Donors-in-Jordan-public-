package com.gs3.marketingops.core.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import androidx.room.migration.Migration
import com.gs3.marketingops.campaigns.data.MarketBudgetEntity
import com.gs3.marketingops.inventory.data.UnitEntity
import com.gs3.marketingops.nonjordanian.data.ContractClaimEntity
import com.gs3.marketingops.nonjordanian.data.EligibilityGateEntity
import com.gs3.marketingops.outreach.data.MessageTemplateEntity
import com.gs3.marketingops.outreach.data.ObjectionEntity

/**
 * The local database. There is no other copy of any of this.
 *
 * That is the fact that shapes every decision below. The app is offline and
 * local-only: no backend, no sync, no cloud backup (see
 * `data_extraction_rules.xml`). If a row is lost here it is lost, and the only
 * route back is the encrypted backup file the owner took by hand.
 *
 * **`fallbackToDestructiveMigration` is not called, and must never be.** It is
 * the single most tempting line in Room and it means "if the schema changed and
 * I did not write a migration, delete the user's data and start again". On a
 * device holding every lead, agreed price and discount justification the
 * company has, that is a data-loss bug wearing the costume of a convenience.
 * Its absence is asserted by a test, because an absence is not something code
 * review reliably notices.
 *
 * Schemas are exported to `app/schemas` (see `ksp { arg("room.schemaLocation" …) }`)
 * and committed, so version 2 can be migration-tested against the real version 1
 * rather than against a guess at what version 1 looked like.
 */
@Database(
    entities = [
        UnitEntity::class,
        MarketBudgetEntity::class,
        MessageTemplateEntity::class,
        ObjectionEntity::class,
        EligibilityGateEntity::class,
        ContractClaimEntity::class,
    ],
    version = Gs3Database.VERSION,
    exportSchema = true,
)
@TypeConverters(Converters::class)
abstract class Gs3Database : RoomDatabase() {

    abstract fun unitDao(): UnitDao
    abstract fun marketBudgetDao(): MarketBudgetDao
    abstract fun outreachDao(): OutreachDao
    abstract fun complianceDao(): ComplianceDao

    companion object {
        const val VERSION: Int = 1
        const val NAME: String = "gs3_marketing_ops.db"

        /**
         * Empty at version 1, and present anyway.
         *
         * The list exists now so that adding version 2 is an edit to an
         * established mechanism rather than a decision taken in a hurry, at the
         * point where the tempting alternative is one destructive line. The
         * database is built with `addMigrations(*MIGRATIONS)` from the first
         * commit, so nothing about the wiring changes when the first real
         * migration arrives.
         */
        val MIGRATIONS: Array<Migration> = emptyArray()

        /**
         * The one place the database is built.
         *
         * Extracted so the test that proves `fallbackToDestructiveMigration` is
         * absent exercises *this* builder rather than a copy of it in the test.
         * A test that asserts against its own replica of the production wiring
         * proves only that the replica is correct, and would keep passing after
         * someone added the destructive line here.
         */
        fun build(context: Context, name: String = NAME): Gs3Database =
            Room.databaseBuilder(context, Gs3Database::class.java, name)
                .addMigrations(*MIGRATIONS)
                .build()
    }
}
