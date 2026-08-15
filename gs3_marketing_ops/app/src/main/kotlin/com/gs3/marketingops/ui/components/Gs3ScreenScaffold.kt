package com.gs3.marketingops.ui.components

import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.TopAppBarScrollBehavior
import androidx.compose.material3.rememberTopAppBarState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll

/**
 * The scaffold every screen sits in, and the one place window insets are
 * reasoned about.
 *
 * Insets are handled explicitly here rather than left to defaults, because API
 * 36 removed the edge-to-edge opt-out: the content genuinely does run under the
 * status bar and under the gesture handle, and a screen that ignores that puts
 * its first row of text behind the clock. Getting this right once, in a shared
 * component, is the difference between four screens being right and forty
 * screens each being right by hand.
 *
 * The sides are split on purpose:
 *
 *  - the **top app bar** consumes the top inset, so it sits below the status
 *    bar rather than under it;
 *  - the content area therefore asks only for the horizontal and bottom
 *    portions of `safeDrawing`. Horizontal matters in landscape on a phone with
 *    a display cutout — an Arabic label pinned to `end` would otherwise sit
 *    under the notch;
 *  - the *navigation* inset is deliberately left out, because
 *    `NavigationSuiteScaffold` above has already consumed it. Asking for it
 *    again is the classic double-padding bug, and it shows up as a floating
 *    button that will not quite reach the bottom of the screen.
 *
 * `safeDrawing` is used rather than `systemBars` so that a display cutout and
 * the three-button navigation bar are both covered; the app must look right
 * under gesture navigation and under buttons, and those give different insets.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
internal fun Gs3ScreenScaffold(
    title: String,
    modifier: Modifier = Modifier,
    actions: @Composable () -> Unit = {},
    content: @Composable (PaddingValues) -> Unit,
) {
    val scrollBehavior: TopAppBarScrollBehavior =
        TopAppBarDefaults.enterAlwaysScrollBehavior(rememberTopAppBarState())

    Scaffold(
        modifier = modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        contentWindowInsets = WindowInsets.safeDrawing.only(
            WindowInsetsSides.Horizontal + WindowInsetsSides.Bottom,
        ),
        topBar = {
            TopAppBar(
                title = { Text(title) },
                actions = { actions() },
                scrollBehavior = scrollBehavior,
                windowInsets = WindowInsets.safeDrawing.only(
                    WindowInsetsSides.Horizontal + WindowInsetsSides.Top,
                ),
            )
        },
        content = content,
    )
}
