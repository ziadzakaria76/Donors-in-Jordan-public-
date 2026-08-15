package com.gs3.marketingops

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import com.gs3.marketingops.ui.Gs3App
import com.gs3.marketingops.ui.theme.Gs3Theme
import dagger.hilt.android.AndroidEntryPoint

/**
 * The single activity.
 *
 * `enableEdgeToEdge()` is called before `setContent`, from the first commit
 * rather than as a later polish pass. On API 36 the opt-out is gone — an app
 * targeting 36 is edge-to-edge whether it asks to be or not — so calling it
 * explicitly changes nothing about the result and everything about whether the
 * insets were thought through. Every screen below handles its own insets; see
 * `Gs3App`.
 */
@AndroidEntryPoint
class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        super.onCreate(savedInstanceState)

        setContent {
            Gs3Theme {
                Gs3App()
            }
        }
    }
}
