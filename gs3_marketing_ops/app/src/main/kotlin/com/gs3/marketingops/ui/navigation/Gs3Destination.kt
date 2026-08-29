package com.gs3.marketingops.ui.navigation

import androidx.annotation.StringRes
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.List
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Person
import androidx.compose.ui.graphics.vector.ImageVector
import com.gs3.marketingops.R

/**
 * The five top-level destinations.
 *
 * The icons are the **auto-mirrored** variants wherever the glyph has a
 * direction to it. A list icon's ragged edge and a paper plane both point
 * somewhere, and in an Arabic-first app that points the wrong way round the
 * moment the layout flips. `Icons.AutoMirrored` costs nothing here and cannot
 * be retrofitted by remembering to.
 */
internal enum class Gs3Destination(
    val route: String,
    @StringRes val labelRes: Int,
    val icon: ImageVector,
) {
    Dashboard(
        route = "dashboard",
        labelRes = R.string.nav_dashboard,
        icon = Icons.Filled.Home,
    ),
    Inventory(
        route = "inventory",
        labelRes = R.string.nav_inventory,
        icon = Icons.AutoMirrored.Filled.List,
    ),
    Leads(
        route = "leads",
        labelRes = R.string.nav_leads,
        icon = Icons.Filled.Person,
    ),
    Campaigns(
        route = "campaigns",
        labelRes = R.string.nav_campaigns,
        icon = Icons.AutoMirrored.Filled.Send,
    ),
    More(
        route = "more",
        labelRes = R.string.nav_more,
        icon = Icons.Filled.MoreVert,
    ),
    ;

    internal companion object {
        /** The destination a route belongs to, or the dashboard if unrecognised. */
        fun fromRoute(route: String?): Gs3Destination =
            entries.firstOrNull { it.route == route } ?: Dashboard
    }
}
