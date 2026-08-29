package jo.tendermonitor

import android.app.Application
import android.content.Context
import androidx.room.Room
import jo.tendermonitor.data.ReportRepository
import jo.tendermonitor.data.db.TenderDatabase
import jo.tendermonitor.data.github.GitHubClient
import jo.tendermonitor.data.portals.PortalsRepository
import jo.tendermonitor.data.settings.KeystoreSettings
import jo.tendermonitor.work.Notifier
import jo.tendermonitor.work.PollScheduler
import jo.tendermonitor.work.PollState
import java.io.File

/**
 * Wiring, by hand.
 *
 * A dependency-injection framework would earn its keep in a bigger app; here
 * it would be one more thing between a bug and its cause, in a codebase whose
 * whole argument is that you can see why something happened.
 */
class TenderMonitorApp : Application() {

    val graph: Graph by lazy { Graph(this) }

    override fun onCreate() {
        super.onCreate()
        // Channels are created up front rather than at first post: a person
        // who wants to make failures noisier should be able to find the
        // channel in Android's settings before one has ever fired.
        Notifier(this).ensureChannels()
        // Re-applied on every launch so the schedule survives a reboot, an
        // app update, or WorkManager's database being cleared. Enqueuing the
        // same unique work again is a no-op when nothing changed.
        PollScheduler.apply(this, graph.settings.settings())
    }

    class Graph(context: Context) {
        val settings = KeystoreSettings(context)

        private val database: TenderDatabase = Room.databaseBuilder(
            context,
            TenderDatabase::class.java,
            "tenders.db",
        ).build()

        val client = GitHubClient(settings)

        /**
         * Inside files/, not cache/: a downloaded bid pack should still be
         * there tomorrow, and the system empties the cache directory whenever
         * it wants to.
         */
        private val artifactDir = File(context.filesDir, "artifacts")

        val reports = ReportRepository(
            client = client,
            dao = database.reports(),
            settings = settings,
            artifactDir = artifactDir,
        )

        val portals = PortalsRepository(client = client, settings = settings)

        val pollState = PollState(context)
    }
}
