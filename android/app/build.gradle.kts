plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
}

/**
 * The version, from the build environment.
 *
 * A hard-coded versionCode means every APK ever built claims to be the same
 * one: Android will install any of them over any other without a word, and
 * there is no way to tell from the phone which build is on it. The commit
 * count is monotonic on `main`, available to CI and to a local clone, and
 * needs nothing kept in sync by hand.
 *
 * Falls back to 1 / "dev" so a checkout with no git history still builds.
 */
val apkVersionCode = (System.getenv("APK_VERSION_CODE") ?: "1").toIntOrNull() ?: 1
val apkVersionName = System.getenv("APK_VERSION_NAME")?.takeIf { it.isNotBlank() } ?: "dev"

android {
    namespace = "jo.tendermonitor"
    compileSdk = 35

    defaultConfig {
        applicationId = "jo.tendermonitor"
        // 26 is where EncryptedSharedPreferences' Keystore-backed AES keys are
        // available without a fallback path. Below that the token would have to
        // be stored some other way, and "some other way" for a credential is
        // not a trade worth making for a handset the user already owns.
        minSdk = 26
        targetSdk = 35
        versionCode = apkVersionCode
        versionName = apkVersionName
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    buildTypes {
        debug {
            // Debug-signed, and that is deliberate for now: the APK is
            // installed from the phone by the one person who builds it, and a
            // release keystore that is lost means never updating that install
            // again. See ANDROID.md.
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"),
                          "proguard-rules.pro")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }

    packaging {
        resources.excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.graphics)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.material.icons)
    implementation(libs.androidx.navigation.compose)

    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    ksp(libs.androidx.room.compiler)

    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.androidx.security.crypto)

    implementation(libs.retrofit)
    implementation(libs.retrofit.serialization)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    testImplementation(libs.kotlinx.coroutines.test)
}
