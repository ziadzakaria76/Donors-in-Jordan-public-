plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
    alias(libs.plugins.roborazzi)
}

/**
 * The Android half of GS3 Marketing Ops.
 *
 * Everything Android lives here — Compose, Room, WorkManager, Hilt. The
 * business rules live in `:domain`, which has no Android dependency at all and
 * is therefore tested at JVM speed. This module wires proven rules to screens;
 * it does not restate them.
 *
 * Annotation processing is **KSP only**. `kotlin-kapt` appears nowhere in this
 * project: it runs a second Java compilation over stubs, roughly doubling the
 * build, and it is in maintenance mode for Kotlin 2.x.
 */

android {
    namespace = "com.gs3.marketingops"
    compileSdk = libs.versions.compileSdk.get().toInt()

    defaultConfig {
        applicationId = "com.gs3.marketingops"
        minSdk = libs.versions.minSdk.get().toInt()
        targetSdk = libs.versions.targetSdk.get().toInt()
        versionCode = 1
        versionName = "0.1.0"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // Arabic is authored, not translated. Pinning the set stops a stray
        // transitive library from adding a locale we have not written.
        resourceConfigurations += setOf("ar", "en")

        // Room's schemas are exported so a migration can be tested against the
        // previous version rather than assumed. Migrations exist from day one
        // (IMPLEMENTATION_PLAN.md → Milestone 2).
        ksp { arg("room.schemaLocation", "$projectDir/schemas") }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            isMinifyEnabled = false
        }
        release {
            // R8 full mode. The keystore is deliberately absent from version
            // control — see .gitignore, and DECISIONS.md on the two
            // irreversible losses.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_21
        targetCompatibility = JavaVersion.VERSION_21
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    /**
     * Both languages ship in every install.
     *
     * By default an Android App Bundle is split by language and a device
     * receives only the locales it is configured for, fetching the rest later
     * through Play's asset delivery. This app switches language *at runtime*
     * (see `Gs3Localized`), holds no INTERNET permission, and is sideloaded
     * long before it is ever on Play. Left at the default, a phone set to
     * English would install without the Arabic resources — and Arabic is the
     * language the app opens in. The switch would silently fall back to
     * English, on the one screen built to explain itself in Arabic.
     *
     * Lint catches precisely this as `AppBundleLocaleChanges`. This is the fix
     * it asks for, not a suppression of it.
     */
    bundle {
        language {
            enableSplit = false
        }
    }

    sourceSets {
        named("main") { kotlin.srcDir("src/main/kotlin") }
        named("test") { kotlin.srcDir("src/test/kotlin") }
        named("androidTest") { kotlin.srcDir("src/androidTest/kotlin") }
    }

    packaging {
        resources.excludes += setOf(
            "/META-INF/{AL2.0,LGPL2.1}",
            "META-INF/LICENSE.md",
            "META-INF/LICENSE-notice.md",
        )
    }

    testOptions {
        unitTests {
            isIncludeAndroidResources = true
            isReturnDefaultValues = true
        }
    }

    /**
     * Lint is a gate, not a report. A milestone is not complete while it is
     * failing, and the fix is to fix it — never to add a baseline file.
     */
    lint {
        abortOnError = true
        warningsAsErrors = true
        checkDependencies = true

        // Scoped exceptions, each carrying the evidence for why lint is wrong
        // about that one path. Named explicitly rather than relying on the file
        // being found by convention, so it is discoverable from here.
        lintConfig = file("lint.xml")

        // Absent translations are caught by `verifyStrings`, which reports both
        // directions with the offending keys. Lint's version of the same check
        // duplicates that failure and says less about it.
        disable += setOf("MissingTranslation", "ExtraTranslation")

        // OldTargetApi asks for targetSdk to be raised to the highest platform
        // it can see installed. Here that instruction is wrong, and following it
        // would break a rule the project is built on: 36 is pinned deliberately
        // (brief §2.1), it already clears the Play floor, and anything above it
        // today is a preview API — the exact "never step forward into a release
        // candidate" case the version matrix exists to prevent.
        //
        // It is environment-dependent, which is what made it confusing: the
        // check compares against the newest platform *installed*, so it stays
        // quiet in a container holding only android-36 and fires on a CI runner
        // whose image ships a newer one. Same commit, same lint, different
        // verdict — so this is disabled rather than left to depend on which
        // machine happened to run the build. See DECISIONS.md → D-18.
        disable += "OldTargetApi"

        // UnusedResources reports, but does not fail the build. See
        // DECISIONS.md → D-10 for the full reasoning; in short, the Arabic
        // string file is the *specification* and is authored ahead of the
        // screens that read it, so with `warningsAsErrors` every not-yet-built
        // milestone would fail the build of the milestone before it. The check
        // still runs and still lists every key in the HTML report, and it goes
        // back to being an error at Milestone 10, when every screen exists and
        // a genuinely unused key means a key nobody ever wired up.
        informational += setOf("UnusedResources")

        htmlReport = true
        textReport = true
    }
}

/**
 * Unit tests run on the debug variant only.
 *
 * This is not a test being switched off — every test still runs, in full, on
 * every `check`. It is the *second, identical* execution of them being switched
 * off, and there is a concrete reason it cannot work rather than a preference.
 *
 * `ui-test-manifest` contributes the `ComponentActivity` that `createComposeRule`
 * launches, and it is a `debugImplementation` because that activity has no
 * business in a shipping APK. Robolectric resolves the launcher intent against
 * the variant's merged manifest, so on release it fails with "Unable to resolve
 * activity for Intent". The only way to make it pass would be to add the test
 * scaffolding to the release manifest — shipping test code to clients to make a
 * duplicate test run go green, which is worse than the problem.
 *
 * Unit tests are not run through R8, so debug and release execute the same
 * bytecode. The release run was adding no coverage and doubling the time.
 */
androidComponents {
    beforeVariants(selector().withBuildType("release")) { variant ->
        variant.enableUnitTest = false
    }
}

kotlin {
    jvmToolchain(21)
    compilerOptions {
        allWarningsAsErrors = true
    }
}

dependencies {
    implementation(project(":domain"))

    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.navigation.compose)

    // Compose, all versions from the one BOM.
    val composeBom = platform(libs.compose.bom)
    implementation(composeBom)
    testImplementation(composeBom)
    androidTestImplementation(composeBom)
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.graphics)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.material3.navigation.suite)
    debugImplementation(libs.compose.ui.tooling)

    // Adaptive layout. Present from the first commit because a two-pane
    // scaffold cannot be retrofitted onto screens written without it, and
    // API 36 forbids locking orientation at >= 600dp.
    implementation(libs.material3.adaptive)
    implementation(libs.material3.adaptive.layout)
    implementation(libs.material3.adaptive.navigation)
    implementation(libs.androidx.window)

    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.work.runtime.ktx)

    implementation(libs.hilt.android)
    implementation(libs.hilt.navigation.compose)
    ksp(libs.hilt.compiler)

    // Screenshot and unit tests, all on the JVM. Robolectric supplies the
    // Android framework and Roborazzi renders Compose to a PNG from inside it,
    // so the both-language screenshot set is produced by `./gradlew test` on
    // any machine -- no emulator, no connected device, and therefore something
    // CI actually runs rather than something a person remembers to do.
    testImplementation(libs.junit4)
    testImplementation(libs.robolectric)
    testImplementation(libs.androidx.test.ext.junit)
    testImplementation(libs.compose.ui.test.junit4)
    testImplementation(libs.roborazzi)
    testImplementation(libs.roborazzi.compose)
    testImplementation(libs.roborazzi.junit.rule)
    testImplementation(libs.kotlinx.coroutines.test)
    debugImplementation(libs.compose.ui.test.manifest)

    // Instrumented tests. Deliberately a small stack: these suites use Room and
    // the resource table directly, not Hilt and not Compose, so they need no
    // custom test runner and no injection graph. See
    // .github/workflows/gs3-emulator.yml for what only a device can answer.
    androidTestImplementation(libs.junit4)
    androidTestImplementation(libs.androidx.test.ext.junit)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.kotlinx.coroutines.test)
}

/**
 * Roborazzi records on every test run.
 *
 * Without this property `captureRoboImage` is a **silent no-op**: the tests pass,
 * the report is green, and not a single PNG is written. That was observed here
 * before this block existed, and it is the exact shape of failure the plan warns
 * about -- a check that looks like it ran. The tests also assert that the file
 * they just captured exists on disk, so the guarantee does not rest on this one
 * line of build configuration staying put.
 */
tasks.withType<Test>().configureEach {
    systemProperty("roborazzi.test.record", "true")
}

/**
 * `verifyStrings` is the bilingual guard. It is wired into this module's
 * `check` as well as :domain's, because the strings it polices are this
 * module's — a hardcoded literal in a Composable can only appear here.
 */
tasks.named("check") {
    dependsOn(rootProject.tasks.named("verifyStrings"))
}
