package com.gs3.marketingops.core.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import com.gs3.marketingops.campaigns.data.MarketBudgetEntity
import com.gs3.marketingops.compliance.data.ContractClaimEntity
import com.gs3.marketingops.inventory.data.UnitEntity
import com.gs3.marketingops.outreach.data.MessageTemplateEntity
import com.gs3.marketingops.outreach.data.ObjectionEntity
import kotlinx.coroutines.flow.Flow

/**
 * Reads return `Flow`, writes are `suspend`.
 *
 * Both matter. A `Flow` means a unit's status changing on the detail screen
 * updates the inventory list and the dashboard without anything having to
 * remember to go and refresh them — the class of bug where a sold unit still
 * shows as available on one screen. `suspend` keeps every write off the main
 * thread by construction rather than by discipline.
 *
 * Ordering is always explicit. Without `ORDER BY`, SQLite's row order is not
 * guaranteed, and an inventory list that reshuffles between launches looks
 * broken to the person using it every day.
 */
@Dao
interface UnitDao {

    @Query("SELECT * FROM units ORDER BY number")
    fun observeAll(): Flow<List<UnitEntity>>

    @Query("SELECT * FROM units WHERE number = :number")
    fun observe(number: Int): Flow<UnitEntity?>

    @Query("SELECT * FROM units ORDER BY number")
    suspend fun getAll(): List<UnitEntity>

    @Query("SELECT COUNT(*) FROM units")
    suspend fun count(): Int

    @Update
    suspend fun update(unit: UnitEntity)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertIfAbsent(units: List<UnitEntity>)
}

@Dao
interface MarketBudgetDao {

    @Query("SELECT * FROM market_budgets ORDER BY track, marketKey")
    fun observeAll(): Flow<List<MarketBudgetEntity>>

    @Query("SELECT * FROM market_budgets ORDER BY track, marketKey")
    suspend fun getAll(): List<MarketBudgetEntity>

    @Query("SELECT COUNT(*) FROM market_budgets")
    suspend fun count(): Int

    @Update
    suspend fun update(budget: MarketBudgetEntity)

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertIfAbsent(budgets: List<MarketBudgetEntity>)
}

@Dao
interface OutreachDao {

    @Query("SELECT * FROM message_templates ORDER BY templateKey")
    suspend fun getTemplates(): List<MessageTemplateEntity>

    @Query("SELECT * FROM message_templates ORDER BY templateKey")
    fun observeTemplates(): Flow<List<MessageTemplateEntity>>

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertTemplatesIfAbsent(templates: List<MessageTemplateEntity>)

    @Query("SELECT * FROM objections ORDER BY displayOrder")
    suspend fun getObjections(): List<ObjectionEntity>

    @Query("SELECT * FROM objections ORDER BY displayOrder")
    fun observeObjections(): Flow<List<ObjectionEntity>>

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertObjectionsIfAbsent(objections: List<ObjectionEntity>)
}

@Dao
interface ComplianceDao {

    @Query("SELECT * FROM contract_claims ORDER BY claim")
    fun observeClaims(): Flow<List<ContractClaimEntity>>

    @Query("SELECT * FROM contract_claims ORDER BY claim")
    suspend fun getClaims(): List<ContractClaimEntity>

    @Insert(onConflict = OnConflictStrategy.IGNORE)
    suspend fun insertClaimsIfAbsent(claims: List<ContractClaimEntity>)

    @Update
    suspend fun update(claim: ContractClaimEntity)
}
