package com.gs3.marketingops.inventory.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.gs3.marketingops.core.data.db.UnitDao
import com.gs3.marketingops.domain.inventory.Apartment
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

@HiltViewModel
internal class InventoryViewModel @Inject constructor(
    unitDao: UnitDao,
) : ViewModel() {

    /**
     * Straight from the DAO's `Flow`, so a unit marked Contracted on the detail
     * screen updates this list and its summary without anything having to
     * remember to refresh — the class of bug where a sold apartment still shows
     * as available on the screen the salesperson happens to be looking at.
     *
     * Ordering is the DAO's `ORDER BY number`, not a sort here. SQLite gives no
     * guarantee without it, and an inventory list that reshuffles between
     * launches looks broken to someone who uses it every day.
     *
     * `WhileSubscribed(5_000)` matches `SettingsViewModel`: the five seconds
     * carry the flow across a rotation without re-reading the database, while a
     * backgrounded screen does not keep a collector alive indefinitely.
     */
    val units: StateFlow<List<Apartment>> = unitDao.observeAll()
        .map { rows -> rows.map { it.toDomain() } }
        .stateIn(
            scope = viewModelScope,
            started = SharingStarted.WhileSubscribed(5_000),
            initialValue = emptyList(),
        )
}
