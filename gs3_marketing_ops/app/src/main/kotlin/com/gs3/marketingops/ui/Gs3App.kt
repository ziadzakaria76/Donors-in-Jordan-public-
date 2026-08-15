package com.gs3.marketingops.ui

import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.adaptive.navigationsuite.ExperimentalMaterial3AdaptiveNavigationSuiteApi
import androidx.compose.material3.adaptive.navigationsuite.NavigationSuiteScaffold
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.res.stringResource
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavHostController
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.gs3.marketingops.ui.navigation.Gs3Destination
import com.gs3.marketingops.ui.navigation.Gs3NavHost

/**
 * The app shell.
 *
 * `NavigationSuiteScaffold` is what keeps the layout legal on API 36. The
 * platform no longer honours an orientation lock at >= 600dp, so the app has to
 * be usable in any window it is given: this moves the navigation from a bottom
 * bar on a phone, to a rail on a small tablet or an unfolded foldable, to a
 * permanent drawer on a desktop-sized window — without any screen below knowing
 * which one it got.
 *
 * It also owns the navigation bar's own insets, which is why individual screens
 * only handle what is left over. See [Gs3ScreenScaffold].
 */
@OptIn(ExperimentalMaterial3AdaptiveNavigationSuiteApi::class)
@Composable
internal fun Gs3App(
    navController: NavHostController = rememberNavController(),
) {
    val backStackEntry by navController.currentBackStackEntryAsState()
    val current = Gs3Destination.fromRoute(backStackEntry?.destination?.route)

    NavigationSuiteScaffold(
        navigationSuiteItems = {
            Gs3Destination.entries.forEach { destination ->
                item(
                    selected = destination == current,
                    onClick = { navController.navigateToTopLevel(destination) },
                    icon = {
                        // The label sits beside the icon, so repeating it as a
                        // content description would make TalkBack say the same
                        // word twice.
                        Icon(imageVector = destination.icon, contentDescription = null)
                    },
                    // `stringResource` is read here rather than hoisted above
                    // the loop: `navigationSuiteItems` is a plain builder
                    // lambda, not a composable one.
                    label = { Text(stringResource(destination.labelRes)) },
                )
            }
        },
    ) {
        Gs3NavHost(navController = navController)
    }
}

/**
 * Moves between top-level destinations without growing the back stack.
 *
 * Without `popUpTo`, tapping Dashboard → Leads → Dashboard → Leads five times
 * leaves ten entries behind it, and the user has to press back ten times to
 * leave the app. `launchSingleTop` stops a second copy of the destination the
 * user is already on, and `restoreState`/`saveState` keep each tab's scroll
 * position where they left it.
 */
private fun NavHostController.navigateToTopLevel(destination: Gs3Destination) {
    navigate(destination.route) {
        popUpTo(graph.findStartDestination().id) { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}
