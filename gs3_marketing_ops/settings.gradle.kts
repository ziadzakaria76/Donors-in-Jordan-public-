pluginManagement {
    repositories {
        gradlePluginPortal()
        mavenCentral()
        // google() is deliberately absent until :app exists. Adding it now would
        // make every build fail on a blocked host for no benefit — :domain has
        // no Android dependency. See DECISIONS.md → D-1 and D-7.
    }
}

dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories {
        mavenCentral()
    }
}

rootProject.name = "gs3-marketing-ops"

// :domain is pure Kotlin and builds today.
include(":domain")

// :app is Android and cannot resolve here yet — see DECISIONS.md → D-1.
// include(":app")
