plugins {
    alias(libs.plugins.kotlin.jvm) apply false
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.kotlin.android) apply false
    alias(libs.plugins.kotlin.compose) apply false
    alias(libs.plugins.ksp) apply false
    alias(libs.plugins.hilt) apply false
}

/**
 * verifyStrings — the bilingual guard, run as part of `check`.
 *
 * Three separate failures, each reported with every offending line rather than
 * the first one, because fixing these one build at a time is miserable:
 *
 *  1. a user-visible string literal hardcoded in a Composable;
 *  2. a key present in one locale and missing from the other;
 *  3. a forbidden phrase — a promise the company must not make in writing.
 *
 * It is a Gradle task rather than a custom Lint check on purpose (brief §3):
 * Lint's API is unstable enough to eat a milestone, and this works on the first
 * build. It deliberately does not need the Android plugin, so it runs today.
 */

val stringsEn = layout.projectDirectory.file("app/src/main/res/values/strings.xml")
val stringsAr = layout.projectDirectory.file("app/src/main/res/values-ar/strings.xml")
val allowlistFile = layout.projectDirectory.file("config/hardcoded-strings-allowlist.txt")

/**
 * Phrases that must never reach a screen, in either language.
 *
 * These are not style preferences. The first is a legal claim the company is
 * not entitled to make — a capped *contribution* toward registration fees is
 * not an exemption from them, and calling it one in writing is a promise no one
 * can keep. The others promise an outcome that belongs to a government
 * authority, or a return that belongs to a market.
 */
val forbiddenPhrases = mapOf(
    "fee exemption" to "The company contributes toward fees; it cannot exempt anyone from them.",
    "إعفاء من الرسوم" to "المساهمة في الرسوم ليست إعفاءً منها.",
    "guaranteed approval" to "Approval rests solely with the competent authorities.",
    "ضمان الموافقة" to "الموافقة بيد الجهات المختصة وحدها.",
    "guaranteed return" to "A yield estimate is not a guarantee.",
    "عائد مضمون" to "تقدير العائد ليس ضماناً له.",
)

/** `Text("literal")`, `label = "literal"`, and friends — the ones a user reads. */
val hardcodedStringPattern = Regex(
    """(?:\bText\s*\(\s*|\b(?:text|label|contentDescription|placeholder|title|hint)\s*=\s*)"[^"]*[A-Za-z؀-ۿ][^"]*"""
)

tasks.register("verifyStrings") {
    group = "verification"
    description = "Fails on hardcoded UI strings, on locale key drift, and on forbidden phrases."

    val sourceDirs = listOf(file("app/src/main/kotlin"), file("app/src/main/java"))
    val en = stringsEn.asFile
    val ar = stringsAr.asFile
    val allowlist = allowlistFile.asFile

    // Everything the action needs is captured here, at configuration time, as
    // plain serialisable values. Nothing inside `doLast` may reach back to
    // `project` — the configuration cache cannot serialise a Project or a
    // reference to this build script, and doing so fails the build rather than
    // silently going slow. `projectDir` in particular used to be read inside
    // the action, which is exactly the pattern that breaks.
    val projectDirectory = projectDir
    val phrases = forbiddenPhrases
    val literalPattern = hardcodedStringPattern
    val keyPattern = Regex("""<string\s+name="([^"]+)"""")

    inputs.files(files(sourceDirs).asFileTree.matching { include("**/*.kt") })
    inputs.files(files(en, ar, allowlist))
    outputs.upToDateWhen { false }

    doLast {
        // Local, so it captures nothing but `keyPattern`.
        val parseStringKeys: (File) -> Set<String> = { xml ->
            keyPattern.findAll(xml.readText()).map { it.groupValues[1] }.toSet()
        }

        val failures = mutableListOf<String>()

        // 1 — hardcoded user-visible literals in Kotlin sources.
        val allowed = if (allowlist.exists()) {
            allowlist.readLines()
                .map { it.substringBefore('#').trim() }
                .filter { it.isNotEmpty() }
                .toSet()
        } else emptySet()

        sourceDirs.filter { it.exists() }.forEach { dir ->
            dir.walkTopDown().filter { it.extension == "kt" }.forEach { source ->
                source.readLines().forEachIndexed { index, line ->
                    if (literalPattern.containsMatchIn(line)) {
                        val relative = source.relativeTo(projectDirectory).path
                        val reference = "$relative:${index + 1}"
                        if (reference !in allowed) {
                            failures += "  hardcoded string  $reference\n      ${line.trim()}"
                        }
                    }
                }
            }
        }

        // 2 — key parity. Arabic is authored, not translated, so a key can go
        // missing on either side; both directions are reported.
        if (!en.exists()) failures += "  missing ${en.relativeTo(projectDirectory)}"
        if (!ar.exists()) failures += "  missing ${ar.relativeTo(projectDirectory)}"

        if (en.exists() && ar.exists()) {
            val enKeys = parseStringKeys(en)
            val arKeys = parseStringKeys(ar)
            (enKeys - arKeys).sorted().forEach { failures += "  key missing from Arabic:  $it" }
            (arKeys - enKeys).sorted().forEach { failures += "  key missing from English: $it" }

            // 3 — forbidden phrases, in either locale.
            listOf(en, ar).forEach { resource ->
                val text = resource.readText()
                phrases.forEach { (phrase, why) ->
                    if (text.contains(phrase, ignoreCase = true)) {
                        failures += "  forbidden phrase \"$phrase\" in ${resource.relativeTo(projectDirectory)}\n      $why"
                    }
                }
            }
        }

        if (failures.isNotEmpty()) {
            throw GradleException(
                "verifyStrings found ${failures.size} problem(s):\n" + failures.joinToString("\n")
            )
        }

        val count = if (en.exists()) parseStringKeys(en).size else 0
        logger.lifecycle("verifyStrings: $count keys, both locales in step, no forbidden phrases.")
    }
}

// Wire it into `check` for every module, so it cannot be forgotten.
subprojects {
    plugins.withId("org.jetbrains.kotlin.jvm") {
        tasks.named("check") { dependsOn(rootProject.tasks.named("verifyStrings")) }
    }
}
