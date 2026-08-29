package jo.tendermonitor.data.db

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.RoomDatabase
import androidx.room.Transaction
import kotlinx.coroutines.flow.Flow

/**
 * The last report, on disk, so the app opens with something to read.
 *
 * ONE ROW, NOT A HISTORY. The whole report is stored as the JSON that arrived,
 * plus the few columns needed to describe it in a list. Shredding it into
 * tables would mean the database schema and the report schema have to be
 * migrated in step, and the app would lose the ability to say "this document
 * is from a newer pipeline than I understand" -- it would already have thrown
 * away the parts it did not recognise on the way in.
 *
 * Storing the document whole also means an app update can start rendering a
 * field it previously ignored, from a report downloaded before the update.
 */
@Entity(tableName = "cached_reports")
data class CachedReport(
    /** The workflow run this came from. */
    @PrimaryKey val runId: Long,
    val runNumber: Int,
    /** Epoch millis when the app stored it -- not when the run happened. */
    val storedAt: Long,
    /** GitHub's own timestamp for the run, ISO-8601, as it sent it. */
    val runCreatedAt: String,
    val runConclusion: String,
    val runHtmlUrl: String,
    /** ok | quiet | partial | action_needed, from the report itself. */
    val status: String,
    val statusLine: String,
    val opportunityCount: Int,
    val portalsBroken: Int,
    /** The report document, exactly as downloaded. */
    val json: String,
)

/**
 * An abstract class rather than an interface, deliberately.
 *
 * `store()` has a body and is annotated `@Transaction`. Kotlin compiles a
 * default interface method into a synthetic `DefaultImpls` class unless the
 * whole module opts into JVM default methods, and Room's processor cannot
 * generate a transaction wrapper around that. An abstract class has none of
 * that ambiguity.
 */
@Dao
abstract class ReportDao {

    @Query("SELECT * FROM cached_reports ORDER BY runNumber DESC LIMIT 1")
    abstract fun latest(): Flow<CachedReport?>

    @Query("SELECT * FROM cached_reports ORDER BY runNumber DESC LIMIT 1")
    abstract suspend fun latestOnce(): CachedReport?

    @Query("SELECT * FROM cached_reports WHERE runId = :runId")
    abstract suspend fun byRun(runId: Long): CachedReport?

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    abstract suspend fun insert(report: CachedReport)

    @Query("DELETE FROM cached_reports WHERE runId NOT IN " +
        "(SELECT runId FROM cached_reports ORDER BY runNumber DESC LIMIT :keep)")
    abstract suspend fun trimTo(keep: Int)

    @Query("SELECT * FROM cached_reports ORDER BY runNumber DESC")
    abstract fun history(): Flow<List<CachedReport>>

    /**
     * Keeps a few runs rather than one. Comparing this morning's run with
     * yesterday's is the only way to answer "is this portal newly broken",
     * and that question is asked exactly when the network is worst.
     */
    @Transaction
    open suspend fun store(report: CachedReport, keep: Int = 5) {
        insert(report)
        trimTo(keep)
    }
}

@Database(entities = [CachedReport::class], version = 1, exportSchema = false)
abstract class TenderDatabase : RoomDatabase() {
    abstract fun reports(): ReportDao
}
