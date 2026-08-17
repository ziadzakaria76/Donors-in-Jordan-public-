package com.gs3.marketingops

import android.app.Application
import com.gs3.marketingops.core.data.seed.DatabaseSeeder
import dagger.hilt.android.HiltAndroidApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import javax.inject.Inject

/**
 * The application object.
 *
 * The one job it does beyond being Hilt's entry point is putting the reference
 * data in place, and it does so **off the main thread**. Nothing here blocks the
 * first frame: the seed is a handful of `INSERT OR IGNORE` statements that are a
 * no-op on every launch after the first, and the screens that read the data
 * observe it through `Flow`, so they fill in as it lands rather than waiting on
 * it.
 *
 * `SupervisorJob` so that a failure seeding one table cannot cancel the scope
 * and take the others with it, and the scope is never cancelled — it lives as
 * long as the process, which is the correct lifetime for work that must finish
 * regardless of which screen the user happens to be on.
 */
@HiltAndroidApp
class Gs3Application : Application() {

    @Inject
    lateinit var seeder: DatabaseSeeder

    private val applicationScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate() {
        super.onCreate()
        applicationScope.launch { seeder.seed() }
    }
}
