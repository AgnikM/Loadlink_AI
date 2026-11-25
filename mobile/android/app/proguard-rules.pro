# Proguard rules for LoadLink Driver
-keepattributes *Annotation*
-keepclassmembers class * {
    @androidx.room.* *;
}
-keep class ai.loadlink.driver.data.local.** { *; }
-keep class ai.loadlink.driver.network.** { *; }
