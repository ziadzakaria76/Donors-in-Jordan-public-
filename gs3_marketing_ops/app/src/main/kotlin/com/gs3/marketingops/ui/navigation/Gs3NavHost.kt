package com.gs3.marketingops.ui.navigation

import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import com.gs3.marketingops.campaigns.ui.CampaignsScreen
import com.gs3.marketingops.dashboard.ui.DashboardScreen
import com.gs3.marketingops.domain.money.AppLanguage
import com.gs3.marketingops.domain.money.NumeralStyle
import com.gs3.marketingops.inventory.ui.InventoryScreen
import com.gs3.marketingops.leads.ui.LeadsScreen
import com.gs3.marketingops.settings.data.AppSettings
import com.gs3.marketingops.settings.data.ThemeMode
import com.gs3.marketingops.settings.ui.SettingsScreen

/**
 * These are `fadeIn`/`fadeOut` rather than a slide on purpose: a slide has a
 * direction, and a direction has to be flipped for Arabic. A fade is correct
 * both ways round and cannot rot when someone adds a screen and forgets.
 */
private val FadeSpec = tween<Float>(durationMillis = 180)

/**
 * The top-level navigation graph.
 *
 * Predictive back works here because of three things together, and all three
 * are worth naming since removing any one breaks it silently: the manifest opts
 * in with `android:enableOnBackInvokedCallback`, Navigation Compose drives the
 * gesture through the platform's `OnBackInvokedDispatcher`, and the transitions
 * below are declared rather than defaulted — so there is an animation for the
 * system to scrub through as the user drags. Without a declared transition the
 * gesture still works but shows nothing moving, which reads as a frozen app.
 */
@Composable
internal fun Gs3NavHost(
    navController: NavHostController,
    settings: AppSettings,
    onLanguageChange: (AppLanguage) -> Unit,
    onNumeralsChange: (NumeralStyle) -> Unit,
    onShowHijriChange: (Boolean) -> Unit,
    onThemeChange: (ThemeMode) -> Unit,
    modifier: Modifier = Modifier,
) {
    NavHost(
        navController = navController,
        startDestination = Gs3Destination.Dashboard.route,
        modifier = modifier,
        enterTransition = { fadeIn(animationSpec = FadeSpec) },
        exitTransition = { fadeOut(animationSpec = FadeSpec) },
        popEnterTransition = { fadeIn(animationSpec = FadeSpec) },
        popExitTransition = { fadeOut(animationSpec = FadeSpec) },
    ) {
        composable(Gs3Destination.Dashboard.route) { DashboardScreen() }
        composable(Gs3Destination.Inventory.route) { InventoryScreen(settings = settings) }
        composable(Gs3Destination.Leads.route) { LeadsScreen() }
        composable(Gs3Destination.Campaigns.route) { CampaignsScreen() }

        // "More" is the settings screen for now. The calculators, content
        // planner and reports join it here as their milestones land, at which
        // point this becomes a menu and Settings moves one level down.
        composable(Gs3Destination.More.route) {
            SettingsScreen(
                settings = settings,
                onLanguageChange = onLanguageChange,
                onNumeralsChange = onNumeralsChange,
                onShowHijriChange = onShowHijriChange,
                onThemeChange = onThemeChange,
            )
        }
    }
}
