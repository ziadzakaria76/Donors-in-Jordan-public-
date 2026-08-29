pluginManagement {
    repositories {
        // google() must be present in BOTH blocks: the Android Gradle Plugin
        // lives here, and so does every AndroidX and Compose artifact. Maven
        // Central does not mirror them (checked — 404), so one missing entry
        // takes out the whole Android half of the build.
        google()
        gradlePluginPortal()
        mavenCentral()
    }
}

dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "gs3-marketing-ops"

// :domain is pure Kotlin and builds today.
include(":domain")

// :app is Android. It was held back while `dl.google.com` was refused by the
// egress policy — see DECISIONS.md → D-1. That host is now allowed, the SDK is
// installed, and the Android version matrix is confirmed by an actual resolve
// rather than proposed.
include(":app")
