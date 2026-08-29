# R8 rules for the release build.
#
# Room, Hilt and Compose all ship their own consumer rules, so this file stays
# deliberately short: a rule kept here that the library already provides is a
# rule that silently goes stale.

# Keep the domain module's data classes intact. They are pure Kotlin with no
# reflection today, but they are what CSV export and the encrypted backup
# serialise, and a renamed field would change a backup's contents without any
# compile error to warn about it.
-keep class com.gs3.marketingops.domain.** { *; }

# Kotlin metadata is needed for the reflective bits of Compose tooling.
-keepattributes RuntimeVisibleAnnotations,RuntimeVisibleParameterAnnotations
-keepattributes Signature,InnerClasses,EnclosingMethod
