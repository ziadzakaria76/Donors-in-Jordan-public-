package com.gs3.marketingops.core.di

import android.content.Context
import com.gs3.marketingops.core.data.db.ComplianceDao
import com.gs3.marketingops.core.data.db.Gs3Database
import com.gs3.marketingops.core.data.db.MarketBudgetDao
import com.gs3.marketingops.core.data.db.OutreachDao
import com.gs3.marketingops.core.data.db.UnitDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DatabaseModule {

    /**
     * Note what is **not** called here: `fallbackToDestructiveMigration()`.
     *
     * It is the most tempting line in Room and it means "if the schema moved and
     * nobody wrote a migration, delete everything and start again". This
     * database is the only copy of every lead, agreed price and discount
     * justification the company holds — there is no server to re-sync from.
     * A test asserts its absence, because an absent line is not something code
     * review reliably notices.
     *
     * `addMigrations` is wired from version 1, while the array is still empty,
     * so writing the first real migration is filling in an existing mechanism
     * rather than making a decision under time pressure.
     */
    @Provides
    @Singleton
    fun provideDatabase(@ApplicationContext context: Context): Gs3Database =
        Gs3Database.build(context)

    @Provides
    fun provideUnitDao(database: Gs3Database): UnitDao = database.unitDao()

    @Provides
    fun provideMarketBudgetDao(database: Gs3Database): MarketBudgetDao = database.marketBudgetDao()

    @Provides
    fun provideOutreachDao(database: Gs3Database): OutreachDao = database.outreachDao()

    @Provides
    fun provideComplianceDao(database: Gs3Database): ComplianceDao = database.complianceDao()
}
