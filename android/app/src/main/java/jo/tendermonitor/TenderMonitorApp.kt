package jo.tendermonitor

import android.app.Application
import android.content.Context
import androidx.room.Room
import jo.tendermonitor.data.ReportRepository
import jo.tendermonitor.data.db.TenderDatabase
import jo.tendermonitor.data.github.GitHubClient
import jo.tendermonitor.data.settings.KeystoreSettings
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
    }
}
