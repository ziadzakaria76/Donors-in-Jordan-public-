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

/**
 * The signing key, shared across builds so one can upgrade another.
 *
 * WITHOUT THIS, NO CI BUILD COULD EVER UPDATE ANOTHER. Gradle signs debug
 * builds with ~/.android/debug.keystore and GENERATES ONE AT RANDOM when the
 * file is absent. Every GitHub runner is a fresh machine with no keystore, so
 * every run produced an APK signed by a different throwaway key, and Android
 * refuses to install one over another: "App not installed", with nothing said
 * about signatures. The only way through was uninstall and re-authenticate --
 * on every single update.
 *
 * The old comment here said debug signing was deliberate because "a release
 * keystore that is lost means never updating that install again". The reasoning
 * was sound; the setup delivered exactly the outcome it feared, every build.
 *
 * The key is not in the repository -- this one is public. CI restores it from
 * the ANDROID_KEYSTORE_BASE64 secret. With no secret set the build still works
 * and still produces an installable APK; it just cannot upgrade a previous one,
 * and the workflow says so rather than letting it be discovered on a handset.
 */
private val sharedKeystore: java.io.File? =
    System.getenv("ANDROID_KEYSTORE_PATH")
        ?.takeIf { it.isNotBlank() }
        ?.let(::File)
        ?.takeIf { it.isFile }

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

    signingConfigs {
        if (sharedKeystore != null) {
            create("shared") {
                storeFile = sharedKeystore
                storePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
                keyAlias = System.getenv("ANDROID_KEY_ALIAS")
                keyPassword = System.getenv("ANDROID_KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        debug {
            // Debug BUILD TYPE, but not necessarily the throwaway debug KEY.
            // When CI has restored the shared keystore this is signed with it,
            // so this build can upgrade the last one. See ANDROID.md.
            isMinifyEnabled = false
            if (sharedKeystore != null) {
                signingConfig = signingConfigs.getByName("shared")
            }
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

    // On-device tests. Everything here exists because it CANNOT be tested on a
    // JVM: the Keystore, Room's generated SQL against real SQLite, notification
    // channels, and whether a screen renders at all.
    androidTestImplementation(libs.junit)
    androidTestImplementation(libs.androidx.test.core)
    androidTestImplementation(libs.androidx.test.runner)
    androidTestImplementation(libs.androidx.test.rules)
    androidTestImplementation(libs.androidx.test.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(libs.androidx.uiautomator)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    androidTestImplementation(libs.androidx.room.testing)
    androidTestImplementation(libs.androidx.work.testing)
    androidTestImplementation(libs.kotlinx.coroutines.test)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
}
