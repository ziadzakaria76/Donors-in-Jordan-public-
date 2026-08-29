package com.gs3.marketingops.core.data.db

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import com.gs3.marketingops.campaigns.data.MarketBudgetEntity
import com.gs3.marketingops.compliance.data.ContractClaimEntity
import com.gs3.marketingops.inventory.data.UnitEntity
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
        const val VERSION: Int = 2
        const val NAME: String = "gs3_marketing_ops.db"

        /**
         * Version 1 → 2: the non-Jordanian track leaves the database.
         *
         * Two statements, and the second one is the one that is easy to forget.
         *
         * `eligibility_gate` held the answer to a question — may non-Jordanians
         * own units here — that nothing asks any more. Its table goes with the
         * module it locked (DECISIONS.md → D-23).
         *
         * `market_budgets` is the part a `DROP TABLE` alone would miss. It is a
         * shared table, and four of its nine rows were the non-Jordanian
         * markets: IRQ, GULF, PSE and TEST. The seed no longer produces them,
         * but the seed only ever *inserts* — every insert is
         * `OnConflictStrategy.IGNORE`, deliberately, so that nothing the seed
         * does can overwrite someone's work (D-19). That protection means a
         * phone upgraded from version 1 would keep showing 2,520 JOD of
         * non-Jordanian media forever, on a track the app no longer has. So the
         * rows are deleted here, once, by the migration.
         *
         * Nothing else is touched. The fourteen units, the templates, the
         * objections and all four contract claims — which are not
         * non-Jordanian-specific and stay — cross into version 2 untouched.
         */
        val MIGRATION_1_2: Migration = object : Migration(1, 2) {
            override fun migrate(db: SupportSQLiteDatabase) {
                db.execSQL("DELETE FROM `market_budgets` WHERE `track` = 'NONJO'")
                db.execSQL("DROP TABLE IF EXISTS `eligibility_gate`")
            }
        }

        /**
         * The list was created empty at version 1 so that adding version 2
         * would be an edit to an established mechanism rather than a decision
         * taken in a hurry, at the point where the tempting alternative is one
         * destructive line. This is that edit, and it is the whole of it —
         * `Gs3Database.build` already passed `addMigrations(*MIGRATIONS)`, so
         * no wiring changed to accommodate the first real migration.
         */
        val MIGRATIONS: Array<Migration> = arrayOf(MIGRATION_1_2)

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
