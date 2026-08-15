plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
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

    sourceSets {
        named("main") { kotlin.srcDir("src/main/kotlin") }
        named("test") { kotlin.srcDir("src/test/kotlin") }
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
}

/**
 * `verifyStrings` is the bilingual guard. It is wired into this module's
 * `check` as well as :domain's, because the strings it polices are this
 * module's — a hardcoded literal in a Composable can only appear here.
 */
tasks.named("check") {
    dependsOn(rootProject.tasks.named("verifyStrings"))
}
