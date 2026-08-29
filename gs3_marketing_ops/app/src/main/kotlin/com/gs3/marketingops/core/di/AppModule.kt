package com.gs3.marketingops.core.di

import android.content.Context
import com.gs3.marketingops.settings.data.SettingsRepository
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

/**
 * Application-wide bindings.
 *
 * Deliberately small. Hilt earns its place here because the SLA engine, the
 * database and the reminder scheduler will all need the same few singletons
 * from several places later; it is not doing much yet, and that is fine.
 */
@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    /**
     * The **application** context, not an activity's.
     *
     * `SettingsRepository` outlives any one screen and holds a DataStore that
     * must not be recreated on rotation. Injecting an activity context into a
     * singleton would leak the activity for the life of the process.
     */
    @Provides
    @Singleton
    fun provideSettingsRepository(
        @ApplicationContext context: Context,
    ): SettingsRepository = SettingsRepository(context)
}
