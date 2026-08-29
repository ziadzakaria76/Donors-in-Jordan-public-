package com.gs3.marketingops.core.data.seed

import com.gs3.marketingops.core.data.db.Gs3Database
import javax.inject.Inject
import javax.inject.Singleton

/**
 * Puts the reference data in place, and is safe to run on every launch.
 *
 * Seeding is done here rather than in a `RoomDatabase.Callback.onCreate`, and
 * the difference matters. `onCreate` fires exactly once in the database's life,
 * so a template or objection added in a later version of the app would never
 * reach anyone who already had it installed — they would need to reinstall,
 * which on an offline app means losing their data. Running an idempotent seed
 * on every open means new reference rows arrive with the update.
 *
 * Idempotent because every insert is `OnConflictStrategy.IGNORE`: a row whose
 * primary key is already present is left exactly as it is. That is what
 * protects edits. A salesperson who has reworded a template, or an owner who
 * has finally ticked a contract claim, must not have that overwritten by the
 * seed on next launch — which is precisely what `REPLACE` would do, silently,
 * and only to the people who had customised something.
 *
 * The price of insert-only is that this class can never *remove* anything. When
 * the non-Jordanian track was dropped, taking four market-budget rows with it,
 * the rows already on someone's phone had to be deleted by a schema migration
 * instead — see `Gs3Database.MIGRATION_1_2` and DECISIONS.md → D-23.
 */
@Singleton
class DatabaseSeeder @Inject constructor(
    private val database: Gs3Database,
) {

    suspend fun seed() {
        database.unitDao().insertIfAbsent(Gs3Seed.units())
        database.marketBudgetDao().insertIfAbsent(Gs3Seed.marketBudgets())

        database.outreachDao().apply {
            insertTemplatesIfAbsent(Gs3Seed.messageTemplates())
            insertObjectionsIfAbsent(Gs3Seed.objections())
        }

        database.complianceDao().insertClaimsIfAbsent(Gs3Seed.contractClaims())
    }
}
