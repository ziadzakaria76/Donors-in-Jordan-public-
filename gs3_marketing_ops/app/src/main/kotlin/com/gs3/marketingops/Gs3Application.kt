package com.gs3.marketingops

import android.app.Application
import dagger.hilt.android.HiltAndroidApp

/**
 * The application object. Hilt's entry point and nothing else — no eager work
 * happens here, because anything done on this thread is time the salesperson
 * spends looking at a launch screen.
 */
@HiltAndroidApp
class Gs3Application : Application()
