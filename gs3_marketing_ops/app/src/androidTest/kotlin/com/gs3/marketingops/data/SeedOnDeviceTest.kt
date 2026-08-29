package com.gs3.marketingops.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import androidx.test.ext.junit.runners.AndroidJUnit4
import com.gs3.marketingops.compliance.data.ContractClaim
import com.gs3.marketingops.core.data.db.Gs3Database
import com.gs3.marketingops.core.data.seed.DatabaseSeeder
import com.gs3.marketingops.core.data.seed.Gs3Seed
import com.gs3.marketingops.domain.budget.Gs3Budget
import com.gs3.marketingops.domain.inventory.Gs3Schedule
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith

/**
 * The seed, against a real Android SQLite on a real system image.
 *
 * WHY THIS CANNOT BE A UNIT TEST. Room writes its SQL at build time from the
 * DAO annotations, and nothing checks that SQL until it is executed by the
 * SQLite the device actually ships. `SeedContentTest` on the JVM asserts what
 * `Gs3Seed` *returns*; it never puts a row in a database. Between those two
 * lies every failure where the objects are right and the schema, the converters
 * or the conflict strategy are not — and those surface on a phone, on first
 * launch, to whoever installed it.
 *
 * The database is built through `Gs3Database.build`, the same builder Hilt
 * calls, rather than through `inMemoryDatabaseBuilder`. A test that assembles
 * its own Room instance proves its own instance is correct and would keep
 * passing after someone added `fallbackToDestructiveMigration` to production.
 *
 * No Hilt here on purpose: `Gs3Database.build` and `DatabaseSeeder` are both
 * directly constructible, so this suite needs no test runner beyond the
 * standard one and no injection graph to go wrong.
 */
@RunWith(AndroidJUnit4::class)
class SeedOnDeviceTest {

    private lateinit var context: Context
    private lateinit var database: Gs3Database
    private lateinit var seeder: DatabaseSeeder

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        context.deleteDatabase(TEST_DB)
        database = Gs3Database.build(context, TEST_DB)
        seeder = DatabaseSeeder(database)
    }

    @After
    fun tearDown() {
        database.close()
        context.deleteDatabase(TEST_DB)
    }

    @Test
    fun every_reference_row_reaches_a_real_database() = runTest {
        seeder.seed()

        assertEquals(
            "the fourteen apartments are derived from :domain, never re-typed",
            Gs3Schedule.apartments.size,
            database.unitDao().count(),
        )
        assertEquals(
            "five expatriate markets and no non-Jordanian ones -- D-23, D-24",
            Gs3Budget.externalTrackMarkets.size,
            database.marketBudgetDao().count(),
        )
        assertEquals(4, database.complianceDao().getClaims().size)
        assertTrue(database.outreachDao().getTemplates().isNotEmpty())
        assertTrue(database.outreachDao().getObjections().isNotEmpty())
    }

    @Test
    fun no_non_jordanian_market_reaches_a_real_database() = runTest {
        seeder.seed()

        // On the device, not just in the seed object. The four rows are gone
        // from what a fresh install writes; Gs3Database.MIGRATION_1_2 is what
        // clears them from an install that already had them.
        val tracks = database.marketBudgetDao().getAll().map { it.track }.toSet()
        assertEquals(setOf("EXPAT"), tracks)
    }

    @Test
    fun exactly_the_two_answered_contract_claims_are_confirmed() = runTest {
        seeder.seed()

        val claims = database.complianceDao().getClaims()
        val confirmed = claims.filter { it.confirmedPresent }.map { it.claimType }.toSet()

        assertEquals(
            setOf(
                ContractClaim.FINISHING_SPECIFICATIONS_ANNEX,
                ContractClaim.QUARTERLY_PHOTOGRAPHIC_PROGRESS_REPORT,
            ),
            confirmed,
        )
        // Four rows, so a partial answer to B-2 can be stored as a partial
        // answer. This is that partial answer, having survived a real database.
        assertEquals(4, claims.size)
    }

    @Test
    fun seeding_twice_inserts_nothing_the_second_time() = runTest {
        seeder.seed()
        val afterFirst = counts()

        seeder.seed()

        assertEquals(
            "the seed runs on every launch and must be idempotent",
            afterFirst,
            counts(),
        )
    }

    @Test
    fun a_confirmed_claim_is_not_overwritten_by_the_next_launch() = runTest {
        // The documented risk, and the reason every insert is IGNORE rather
        // than REPLACE. An owner ticks a claim; the app is opened again the
        // next morning; REPLACE would quietly undo the tick, and only for the
        // people who had actually done the work.
        seeder.seed()

        val dao = database.complianceDao()
        val target = dao.getClaims().first { !it.confirmedPresent }
        dao.update(
            target.copy(
                confirmedPresent = true,
                contractReference = "Annex B, clause 7",
            ),
        )

        seeder.seed()

        val after = dao.getClaims().first { it.claim == target.claim }
        assertTrue("the owner's confirmation survived the seed", after.confirmedPresent)
        assertEquals("Annex B, clause 7", after.contractReference)
    }

    @Test
    fun a_same_key_insert_cannot_overwrite_an_existing_row() = runTest {
        // The mechanism the edit protection rests on, tested directly.
        //
        // Named for what it actually proves. OutreachDao has no @Update, so a
        // template cannot yet be edited through it and a test claiming to
        // rewrite one would be asserting something that does not happen. What
        // can be proved today is the property every edit will depend on: an
        // insert carrying an existing primary key changes nothing. Once
        // templates become editable, this is the guarantee that stops the seed
        // undoing it on the next launch.
        seeder.seed()

        val dao = database.outreachDao()
        val original = dao.getTemplates().first()

        dao.insertTemplatesIfAbsent(listOf(original.copy(bodyAr = "نص مختلف تمامًا")))

        val after = dao.getTemplates().first { it.templateKey == original.templateKey }
        assertEquals(original.bodyAr, after.bodyAr)
        assertEquals(original.bodyEn, after.bodyEn)
    }

    @Test
    fun arabic_survives_the_round_trip_through_device_sqlite() = runTest {
        seeder.seed()

        val seeded = Gs3Seed.messageTemplates().associateBy { it.templateKey }
        val stored = database.outreachDao().getTemplates()

        assertTrue(stored.isNotEmpty())
        stored.forEach { row ->
            val expected = requireNotNull(seeded[row.templateKey])
            // Byte-for-byte, not "contains Arabic". An encoding fault mangles
            // characters rather than removing them, and a looser assertion
            // would pass straight through it.
            assertEquals(expected.bodyAr, row.bodyAr)
            assertEquals(expected.bodyEn, row.bodyEn)
        }
    }

    private suspend fun counts(): List<Int> = listOf(
        database.unitDao().count(),
        database.marketBudgetDao().count(),
        database.outreachDao().getTemplates().size,
        database.outreachDao().getObjections().size,
        database.complianceDao().getClaims().size,
    )

    private companion object {
        /**
         * Never the production name. A test that opened the real database would
         * delete the tester's own data in `tearDown`.
         */
        const val TEST_DB = "gs3-instrumented-test.db"
    }
}
