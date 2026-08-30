package com.gs3.marketingops.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import androidx.test.core.app.ApplicationProvider
import com.gs3.marketingops.core.data.db.Gs3Database
import com.gs3.marketingops.domain.budget.Gs3Budget
import kotlinx.coroutines.test.runTest
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/**
 * The 1 → 2 migration, run against a real version 1 database.
 *
 * Two things make this worth the trouble of building version 1 by hand.
 *
 * The version 1 schema is **read out of the committed export**,
 * `app/schemas/…/1.json`, rather than retyped here. A migration test written
 * against a retyped guess at the old schema tests the guess. That export is the
 * only record of what is actually on an existing phone, and it is what this
 * builds from.
 *
 * And the database is then opened through [Gs3Database.build] — the same
 * builder Hilt uses. Room validates the post-migration schema against version 2
 * on the way through, so a migration that left the file in some third shape
 * fails here rather than on someone's phone.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [36])
class DatabaseMigrationTest {

    private lateinit var context: Context
    private lateinit var databaseFile: File

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        databaseFile = context.getDatabasePath("migration_test.db")
        databaseFile.parentFile?.mkdirs()
        databaseFile.delete()
    }

    @After
    fun tearDown() {
        databaseFile.delete()
    }

    @Test
    fun `version one upgrades to two, dropping the gate and the non-Jordanian budget rows`() = runTest {
        createVersionOne()

        val database = Gs3Database.build(context, databaseFile.name)
        try {
            // The four non-Jordanian markets are gone and the five expatriate
            // ones are untouched, values included. This is the half a
            // `DROP TABLE` would have missed: `market_budgets` is shared, and
            // the seed only ever inserts, so nothing else would have cleared
            // these rows from a phone that already had them.
            val budgets = database.marketBudgetDao().getAll()
            assertEquals(
                listOf("KSA", "KWT", "QAT", "UAE", "USA"),
                budgets.map { it.marketKey }.sorted(),
            )
            assertTrue("no NONJO row may survive", budgets.none { it.track == "NONJO" })

            // Opening a version 1 file runs all three migrations in turn, so
            // the surviving rows arrive carrying version 4's figures: 1 -> 2
            // keeps UAE at 1,370, 2 -> 3 re-sizes it to 1,700 (D-28) and
            // 3 -> 4 puts it back (D-29). Asserted against the domain rather
            // than a literal, so the migrations and the seed cannot drift
            // apart.
            assertEquals(
                Gs3Budget.expatriateMarkets.associate { it.marketKey to it.annual.fils },
                budgets.associate { it.marketKey to it.annualFils },
            )

            // Work someone had done survives the migration. A confirmed
            // contract claim is the case that matters: the claims are not
            // non-Jordanian-specific and were deliberately kept (D-23), so the
            // migration must not take them with the gate.
            val claim = database.complianceDao().getClaims().single()
            assertTrue(claim.confirmedPresent)
            assertEquals("Annex 3, clause 2", claim.contractReference)
        } finally {
            database.close()
        }

        assertTrue("the eligibility_gate table must be gone", "eligibility_gate" !in tableNames())
        assertEquals(Gs3Database.VERSION, versionOf(databaseFile))
    }

    @Test
    fun `version three's scaled-up budgets are put back to the brief's figures`() = runTest {
        // 3 -> 4 carries no schema change, so it is the one easiest to skip —
        // and skipping it is silent. The seed inserts with IGNORE (D-19), so a
        // database that ran D-28's scaling keeps UAE at 1,700 for ever while
        // the domain, the reports and the strategy all say 1,370.
        //
        // The starting state is deliberately version 3's *data*, not version
        // 4's. Winding back to the figures this migration is supposed to
        // produce would let the test pass whether or not the migration ran.
        createVersionOne()
        val migrated = Gs3Database.build(context, databaseFile.name)
        migrated.marketBudgetDao().getAll()
        migrated.close()

        SQLiteDatabase.openOrCreateDatabase(databaseFile, null).use { db ->
            listOf("UAE" to 1_700_000L, "USA" to 1_550_000L, "KSA" to 1_390_000L,
                "QAT" to 745_000L, "KWT" to 420_000L).forEach { (market, fils) ->
                db.execSQL("UPDATE market_budgets SET annualFils = ? WHERE marketKey = ?", arrayOf<Any>(fils, market))
            }
            db.version = 3
        }

        val database = Gs3Database.build(context, databaseFile.name)
        try {
            assertEquals(
                Gs3Budget.expatriateMarkets.associate { it.marketKey to it.annual.fils },
                database.marketBudgetDao().getAll().associate { it.marketKey to it.annualFils },
            )
            // 4,680 again, and asserted against the domain so the migration and
            // the seed cannot drift apart.
            assertEquals(
                Gs3Budget.externalTrackTotal.fils,
                database.marketBudgetDao().getAll().sumOf { it.annualFils },
            )
            assertEquals(4_680_000L, database.marketBudgetDao().getAll().sumOf { it.annualFils })
        } finally {
            database.close()
        }
    }

    /**
     * Builds a version 1 database: the exported `CREATE TABLE` statements, a
     * `room_master_table` carrying version 1's identity hash, and rows in the
     * three tables this migration has anything to say about.
     */
    private fun createVersionOne() {
        val schema = JSONObject(versionOneSchema().readText()).getJSONObject("database")
        val entities = schema.getJSONArray("entities")

        SQLiteDatabase.openOrCreateDatabase(databaseFile, null).use { db ->
            for (index in 0 until entities.length()) {
                val entity = entities.getJSONObject(index)
                db.execSQL(
                    entity.getString("createSql")
                        .replace("\${TABLE_NAME}", entity.getString("tableName")),
                )
            }
            db.execSQL(
                "CREATE TABLE IF NOT EXISTS room_master_table " +
                    "(id INTEGER PRIMARY KEY, identity_hash TEXT)",
            )
            db.execSQL(
                "INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES (42, ?)",
                arrayOf(schema.getString("identityHash")),
            )

            db.insert("market_budgets", null, budgetRow("UAE", "EXPAT", 1_370_000L))
            db.insert("market_budgets", null, budgetRow("USA", "EXPAT", 1_250_000L))
            db.insert("market_budgets", null, budgetRow("KSA", "EXPAT", 1_120_000L))
            db.insert("market_budgets", null, budgetRow("QAT", "EXPAT", 600_000L))
            db.insert("market_budgets", null, budgetRow("KWT", "EXPAT", 340_000L))
            db.insert("market_budgets", null, budgetRow("IRQ", "NONJO", 1_260_000L))
            db.insert("market_budgets", null, budgetRow("GULF", "NONJO", 560_000L))
            db.insert("market_budgets", null, budgetRow("PSE", "NONJO", 420_000L))
            db.insert("market_budgets", null, budgetRow("TEST", "NONJO", 280_000L))

            db.insert(
                "eligibility_gate",
                null,
                ContentValues().apply {
                    put("id", 1)
                    put("landsAndSurveyStatementObtained", 0)
                    put("lawyerOpinionObtained", 0)
                    put("reference", "")
                },
            )

            db.insert(
                "contract_claims",
                null,
                ContentValues().apply {
                    put("claim", "FINISHING_SPECIFICATIONS_ANNEX")
                    put("confirmedPresent", 1)
                    put("contractReference", "Annex 3, clause 2")
                    put("confirmedAt", 1_756_425_600_000L)
                },
            )

            db.version = 1
        }
    }

    private fun budgetRow(key: String, track: String, fils: Long) = ContentValues().apply {
        put("marketKey", key)
        put("track", track)
        put("annualFils", fils)
    }

    private fun tableNames(): List<String> =
        SQLiteDatabase.openDatabase(databaseFile.path, null, SQLiteDatabase.OPEN_READONLY).use { db ->
            db.rawQuery("SELECT name FROM sqlite_master WHERE type = 'table'", null).use { cursor ->
                buildList { while (cursor.moveToNext()) add(cursor.getString(0)) }
            }
        }

    private fun versionOf(file: File): Int =
        SQLiteDatabase.openDatabase(file.path, null, SQLiteDatabase.OPEN_READONLY).use { it.version }

    /**
     * The committed export, found by walking up from wherever the test runner
     * happens to have been started. Deliberately not a hardcoded relative path:
     * this file existing is the whole basis of the test, so it fails loudly
     * with the directory it searched rather than skipping.
     */
    private fun versionOneSchema(): File {
        val relative = "app/schemas/com.gs3.marketingops.core.data.db.Gs3Database/1.json"
        var directory: File? = File(System.getProperty("user.dir") ?: ".").absoluteFile
        while (directory != null) {
            listOf(File(directory, relative), File(directory, relative.removePrefix("app/")))
                .forEach { if (it.isFile) return it }
            directory = directory.parentFile
        }
        throw AssertionError("no committed version 1 schema under ${System.getProperty("user.dir")}")
    }
}
