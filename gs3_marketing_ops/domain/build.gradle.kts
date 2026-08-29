plugins {
    alias(libs.plugins.kotlin.jvm)
    jacoco
}

/**
 * Pure Kotlin, no Android. That is the point: every rule the business actually
 * cares about — funnel maths, budget normalisation, fee calculation, SLA
 * timing, the discount guard — is a function over plain data, so it is tested
 * at JVM speed with no emulator, no Robolectric, and no Android SDK.
 */

kotlin {
    jvmToolchain(21)
    compilerOptions {
        allWarningsAsErrors = true
    }
}

dependencies {
    testImplementation(libs.junit.jupiter)
    testRuntimeOnly(libs.junit.platform.launcher)
}

tasks.test {
    useJUnitPlatform()
    finalizedBy(tasks.jacocoTestReport)
    testLogging {
        events("failed")
    }
}

tasks.jacocoTestReport {
    dependsOn(tasks.test)
    reports {
        xml.required = true
        html.required = true
    }
}

/**
 * The brief asks for ≥80% coverage of business logic, reported as an actual
 * number rather than asserted. This fails the build below the line — and the
 * line is not to be lowered to make a build pass (brief §0).
 */
tasks.jacocoTestCoverageVerification {
    dependsOn(tasks.test)
    violationRules {
        rule {
            limit {
                counter = "LINE"
                minimum = "0.80".toBigDecimal()
            }
        }
    }
}

tasks.named("check") {
    dependsOn(tasks.jacocoTestCoverageVerification)
}

/** Prints the coverage percentage, so a milestone report can quote a real figure. */
tasks.register("coverage") {
    group = "verification"
    description = "Prints line coverage from the JaCoCo report."
    dependsOn(tasks.jacocoTestReport)
    val report = layout.buildDirectory.file("reports/jacoco/test/jacocoTestReport.xml")
    doLast {
        val xml = report.get().asFile.readText()
        val line = Regex("""<counter type="LINE" missed="(\d+)" covered="(\d+)"/>""")
            .findAll(xml).lastOrNull()
        if (line == null) {
            logger.lifecycle("coverage: no LINE counter in the report")
        } else {
            val missed = line.groupValues[1].toInt()
            val covered = line.groupValues[2].toInt()
            val pct = covered * 100.0 / (missed + covered)
            logger.lifecycle("coverage: %.1f%% of lines (%d covered, %d missed)".format(pct, covered, missed))
        }
    }
}
