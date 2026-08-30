package com.gs3.marketingops.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.gs3.marketingops.core.data.db.Gs3Database
import com.gs3.marketingops.core.data.seed.DatabaseSeeder
import com.gs3.marketingops.core.data.seed.Gs3Seed
import com.gs3.marketingops.domain.inventory.UnitStatus
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.io.File

/**
 * The database as it actually behaves, not as the seed object describes it.
 *
 * A **file-backed** database rather than an in-memory one, deliberately: the
 * properties worth testing here are what survives a close and reopen, and an
 * in-memory database cannot be reopened at all. It is also what makes the
 * destructive-migration test possible.
 */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [36])
class DatabaseSeedTest {

    private lateinit var context: Context
    private lateinit var database: Gs3Database
    private lateinit var databaseFile: File

    @Before
    fun setUp() {
        context = ApplicationProvider.getApplicationContext()
        databaseFile = context.getDatabasePath("seed_test.db")
        databaseFile.parentFile?.mkdirs()
        databaseFile.delete()
        database = Gs3Database.build(context, databaseFile.name)
    }

    @After
    fun tearDown() {
        database.close()
        databaseFile.delete()
    }

    private suspend fun seed() = DatabaseSeeder(database).seed()

    @Test
    fun `a first launch has the whole reference set in place`() = runTest {
        seed()

        assertEquals(14, database.unitDao().count())
        assertEquals(5, database.marketBudgetDao().count())
        assertEquals(Gs3Seed.messageTemplates().size, database.outreachDao().getTemplates().size)
        assertEquals(Gs3Seed.objections().size, database.outreachDao().getObjections().size)
        assertEquals(2, database.complianceDao().getClaims().size)
    }

    @Test
    fun `the units come back out of SQLite as the schedule went in`() = runTest {
        seed()

        val stored = database.unitDao().getAll().map { it.toDomain() }

        // The round trip that matters: prices are stored as Long fils and
        // rebuilt as Jod, so this is where a lost fils or a mangled Arabic
        // position string would show up.
        assertEquals(com.gs3.marketingops.domain.inventory.Gs3Schedule.apartments, stored)
    }

    @Test
    fun `seeding twice changes nothing`() = runTest {
        seed()
        seed()

        assertEquals(14, database.unitDao().count())
        assertEquals(5, database.marketBudgetDao().count())
        assertEquals(Gs3Seed.objections().size, database.outreachDao().getObjections().size)
        assertEquals(2, database.complianceDao().getClaims().size)
    }

    /**
     * The test this whole seeding design exists for.
     *
     * The seed runs on every launch so that a template added in a later release
     * reaches people who already have the app. The price of that is the risk of
     * overwriting someone's work — and it would be paid only by the people who
     * had customised something, which is the worst possible distribution of a
     * bug.
     */
    @Test
    fun `a launch after someone has done real work does not undo it`() = runTest {
        seed()

        val sold = database.unitDao().getAll().first { it.number == 6 }.copy(
            status = UnitStatus.CONTRACTED.name,
            agreedPriceFils = 88_000_000L,
            discountJustification = "Cash, no financing",
        )
        database.unitDao().update(sold)

        seed()

        val afterRestart = database.unitDao().getAll().first { it.number == 6 }
        assertEquals(UnitStatus.CONTRACTED.name, afterRestart.status)
        assertEquals(88_000_000L, afterRestart.agreedPriceFils)
        assertEquals("Cash, no financing", afterRestart.discountJustification)
    }

    @Test
    fun `a confirmed contract claim survives the next launch`() = runTest {
        seed()

        val claim = database.complianceDao().getClaims().first()
        database.complianceDao().update(
            claim.copy(confirmedPresent = true, contractReference = "Annex 3"),
        )

        seed()

        val after = database.complianceDao().getClaims().first { it.claim == claim.claim }
        assertTrue(after.confirmedPresent)
        assertEquals("Annex 3", after.contractReference)
    }

    @Test
    fun `edits survive the database being closed and reopened`() = runTest {
        seed()
        database.unitDao().update(
            database.unitDao().getAll().first { it.number == 1 }
                .copy(status = UnitStatus.RESERVED.name),
        )
        database.close()

        database = Gs3Database.build(context, databaseFile.name)
        seed()

        assertEquals(
            UnitStatus.RESERVED.name,
            database.unitDao().getAll().first { it.number == 1 }.status,
        )
    }

    /**
     * Proof that `fallbackToDestructiveMigration` is absent, rather than a
     * comment saying so.
     *
     * That call means "if the schema moved and nobody wrote a migration, delete
     * the user's data and start again". On a device holding the only copy of
     * every lead and agreed price the company has, it is data loss dressed as
     * convenience — and its absence is exactly the kind of thing code review
     * does not notice, because there is nothing on the screen to notice.
     *
     * The database file is stamped with a version far in the future and then
     * opened. Room must refuse. If someone adds the destructive line, Room will
     * instead wipe the file and open happily, no exception will be thrown, and
     * this test fails — which is the point.
     *
     * It goes through `Gs3Database.build`, the same builder Hilt uses, so it
     * cannot pass against a replica while production does something else.
     */
    @Test
    fun `Room refuses to wipe a database it cannot migrate`() = runTest {
        seed()
        database.close()

        // Stamp a version this build knows nothing about, and no way back to 1.
        android.database.sqlite.SQLiteDatabase
            .openDatabase(databaseFile.path, null, android.database.sqlite.SQLiteDatabase.OPEN_READWRITE)
            .use { it.version = 9_999 }

        val reopened = Gs3Database.build(context, databaseFile.name)
        assertThrows(IllegalStateException::class.java) {
            // Room opens lazily, so the failure surfaces on first use.
            kotlinx.coroutines.runBlocking { reopened.unitDao().count() }
        }
        reopened.close()

        // And the data is still there afterwards, which is the property that
        // actually matters to the person whose phone it is.
        android.database.sqlite.SQLiteDatabase
            .openDatabase(databaseFile.path, null, android.database.sqlite.SQLiteDatabase.OPEN_READWRITE)
            .use { raw ->
                raw.version = Gs3Database.VERSION
                raw.rawQuery("SELECT COUNT(*) FROM units", null).use { cursor ->
                    cursor.moveToFirst()
                    assertEquals(14, cursor.getInt(0))
                }
            }
    }
}
