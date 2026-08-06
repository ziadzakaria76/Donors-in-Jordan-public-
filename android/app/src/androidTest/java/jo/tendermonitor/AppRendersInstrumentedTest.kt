package jo.tendermonitor

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.ext.junit.runners.AndroidJUnit4
import jo.tendermonitor.ui.MainActivity
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith

/**
 * Does it run.
 *
 * Not a subtle question, and until this existed nobody could answer it. The
 * app compiled and its logic was unit tested; no screen had ever been drawn.
 * A Compose screen can compile perfectly and still throw on first composition
 * -- an unresolved theme attribute, a ViewModel that touches the network on
 * construction, a list that indexes an empty state.
 *
 * DELIBERATELY RUN WITH NO TOKEN AND NO NETWORK EXPECTATION. This is exactly
 * the state a phone is in thirty seconds after install, and it is the state
 * most likely to be broken: every screen has to say what it does not know yet
 * rather than render an empty success. A crash here is the difference between
 * an app and a screenshot.
 */
@RunWith(AndroidJUnit4::class)
class AppRendersInstrumentedTest {

    @get:Rule
    val compose = createAndroidComposeRule<MainActivity>()

    @Test
    fun the_app_launches_and_shows_the_first_screen() {
        compose.waitForIdle()

        compose.onNodeWithText("Latest report").assertIsDisplayed()
    }

    @Test
    fun every_tab_is_reachable_and_draws_without_crashing() {
        // The icons carry the tab name as their content description, which is
        // how this reaches the bar item rather than the label text -- "Files"
        // is both a tab and a title, and matching on text alone is ambiguous.
        TABS.forEach { (tab, title) ->
            compose.onNodeWithContentDescription(tab).performClick()
            compose.waitForIdle()

            compose.onNodeWithText(title).assertIsDisplayed()
        }
    }

    @Test
    fun going_back_and_forth_between_tabs_does_not_break_them() {
        // State is remembered per tab. Leaving and returning is where a
        // `remember` that should have been a `rememberSaveable`, or a list
        // index kept across a data change, shows itself.
        repeat(2) {
            TABS.forEach { (tab, _) ->
                compose.onNodeWithContentDescription(tab).performClick()
                compose.waitForIdle()
            }
        }

        compose.onNodeWithContentDescription("Latest").performClick()
        compose.waitForIdle()
        compose.onNodeWithText("Latest report").assertIsDisplayed()
    }

    private companion object {
        /**
         * Tab name -> a string that only appears once that tab has drawn.
         *
         * Mostly the top bar title. Two are not:
         *
         * Files, because its title is the word "Files", which is also its tab
         * label -- matching that would pass on the label alone and prove
         * nothing about the screen. Its first heading is used instead.
         *
         * Settings, because its title is the repository slug, which is a
         * setting; asserting on it would test the default rather than the
         * navigation.
         *
         * Every string here is unconditional -- drawn before any request,
         * with no token, on an empty cache. An assertion on content that only
         * appears once data arrives would fail for the wrong reason.
         */
        val TABS = listOf(
            "Latest" to "Latest report",
            "Run" to "Run the monitor",
            "Health" to "Portal health",
            "Portals" to "Manage portals",
            "Files" to "Report pack",
            "Settings" to "GitHub token",
        )
    }
}
