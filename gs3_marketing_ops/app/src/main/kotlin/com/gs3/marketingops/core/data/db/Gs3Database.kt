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
        const val VERSION: Int = 5
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
         * Version 2 → 3: the expatriate market budgets are re-sized.
         *
         * **No schema change at all** — same tables, same columns. Room would
         * not have demanded a version bump for this. It is here because the
         * *data* is wrong on any database already created, and for exactly the
         * reason `MIGRATION_1_2` had to delete rather than rely on the seed:
         * every seed insert is `IGNORE` (D-19), so a row whose primary key
         * exists is left alone and the five markets would keep their old
         * annual figures for ever.
         *
         * A decision on 2026-08-29 moved 1,125 JOD back onto this track so it
         * could still fund three units, and the five values below are that
         * decision's figures. It was reverted the next day.
         *
         * **They are frozen literals, and they no longer match
         * `Gs3Budget.expatriateMarkets` — deliberately.** The 2026-08-30 revert undid the
         * scaling, so the domain says 1,370 where this says 1,700. Do not
         * "correct" one to the other: a migration describes what version 3 *was*,
         * not what the app currently believes, and a shipped migration that
         * changes meaning gives two databases different histories for the same
         * version. `MIGRATION_3_4` is what brings these rows back into line with
         * the domain.
         *
         * Nothing asserts these intermediate values, because there is nothing
         * to assert them against. `DatabaseMigrationTest` asserts the *end* of
         * the chain against `Gs3Budget`, which is the property that matters.
         *
         * **This overwrites the rows unconditionally, and that is only
         * acceptable today.** Nothing in the app can edit a market budget yet —
         * there is no Settings screen for it until Milestone 5 — so there is no
         * hand-made figure to destroy. Once budgets are editable this migration
         * would be the exact bug D-19 is written against, and the next one of
         * its kind must preserve edited rows instead.
         */
        val MIGRATION_2_3: Migration = object : Migration(2, 3) {
            override fun migrate(db: SupportSQLiteDatabase) {
                listOf(
                    "UAE" to 1_700_000L,
                    "USA" to 1_550_000L,
                    "KSA" to 1_390_000L,
                    "QAT" to 745_000L,
                    "KWT" to 420_000L,
                ).forEach { (market, annualFils) ->
                    db.execSQL(
                        "UPDATE `market_budgets` SET `annualFils` = ? WHERE `marketKey` = ?",
                        arrayOf<Any>(annualFils, market),
                    )
                }
            }
        }

        /**
         * Version 3 → 4: the expatriate market budgets go back to the brief's
         * own figures.
         *
         * They were scaled up on 2026-08-29 so the external track could fund
         * three units at an assumed 45 JOD per raw lead. The owner removed that
         * assumption on
         * 2026-08-30, and the scaling went with it — a figure derived
         * from an assumption does not outlive it.
         *
         * **This is a revert, and it is still written forwards.** Version 3
         * exists, some database somewhere may be sitting at it, and the way
         * back is a new migration rather than deleting `MIGRATION_2_3` and
         * standing the version number back down. Removing a migration that has
         * shipped strands every database that already ran it: Room would find
         * no path from 3 and refuse to open, which on this app means an
         * unopenable database holding the only copy of the company's leads.
         *
         * The same caveat as `MIGRATION_2_3` applies and is the reason both are
         * still acceptable: no screen can edit a market budget yet, so there is
         * no hand-made figure for an unconditional `UPDATE` to destroy. That
         * changes at Milestone 5.
         */
        val MIGRATION_3_4: Migration = object : Migration(3, 4) {
            override fun migrate(db: SupportSQLiteDatabase) {
                listOf(
                    "UAE" to 1_370_000L,
                    "USA" to 1_250_000L,
                    "KSA" to 1_120_000L,
                    "QAT" to 600_000L,
                    "KWT" to 340_000L,
                ).forEach { (market, annualFils) ->
                    db.execSQL(
                        "UPDATE `market_budgets` SET `annualFils` = ? WHERE `marketKey` = ?",
                        arrayOf<Any>(annualFils, market),
                    )
                }
            }
        }

        /**
         * Version 4 → 5: the two unconfirmed contract claims are deleted.
         *
         * `DELAY_PENALTY_IN_BUYERS_FAVOUR` and `TWO_YEAR_AND_TEN_YEAR_WARRANTY`
         * were the half of B-2 nobody had verified against the signed contract.
         * The owner removed them on 2026-08-30 (D-30). The seed no longer emits
         * them, and — as with every data change in this file — the seed alone
         * cannot clear them from a database that already has them, because
         * every insert is `IGNORE` (D-19) and none of them is a delete.
         *
         * Deleting by name rather than by "everything not in the current enum":
         * a `NOT IN` list built from `ContractClaim.entries` would silently
         * delete any *future* claim the moment someone rolled back the app, and
         * a migration must mean one fixed thing for ever.
         */
        val MIGRATION_4_5: Migration = object : Migration(4, 5) {
            override fun migrate(db: SupportSQLiteDatabase) {
                listOf(
                    "DELAY_PENALTY_IN_BUYERS_FAVOUR",
                    "TWO_YEAR_AND_TEN_YEAR_WARRANTY",
                ).forEach { claim ->
                    db.execSQL("DELETE FROM `contract_claims` WHERE `claim` = ?", arrayOf<Any>(claim))
                }
            }
        }

        /**
         * The list was created empty at version 1 so that adding version 2
         * would be an edit to an established mechanism rather than a decision
         * taken in a hurry, at the point where the tempting alternative is one
         * destructive line. It has stayed an edit —
         * `Gs3Database.build` already passed `addMigrations(*MIGRATIONS)`, so
         * no wiring has changed for any of them.
         */
        val MIGRATIONS: Array<Migration> = arrayOf(MIGRATION_1_2, MIGRATION_2_3, MIGRATION_3_4, MIGRATION_4_5)

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
