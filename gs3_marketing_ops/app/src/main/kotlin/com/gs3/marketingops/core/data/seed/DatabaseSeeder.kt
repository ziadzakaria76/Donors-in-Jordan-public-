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
 * The one exception is the eligibility gate row, which is inserted only when
 * absent for the same reason: it starts closed, and once someone has cleared it
 * with a real reference number the seed must never close it again.
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

        database.complianceDao().apply {
            insertClaimsIfAbsent(Gs3Seed.contractClaims())
            if (getGate() == null) upsertGate(Gs3Seed.eligibilityGate())
        }
    }
}
