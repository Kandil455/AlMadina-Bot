# ProGuard configuration for AlMadina Android App

# Keep all model classes used for JSON serialization
-keep class com.almadina.app.data.remote.model.** { *; }
-keep class com.almadina.app.data.local.database.** { *; }

# Keep Retrofit
-keepclasseswithmembers class * {
    @retrofit2.http.* <methods>;
}

# Keep Gson
-keep class com.google.gson.** { *; }
-keep class * extends com.google.gson.TypeAdapter
-keep class * implements com.google.gson.JsonSerializer
-keep class * implements com.google.gson.JsonDeserializer

# Keep OkHttp
-dontwarn okhttp3.**
-dontwarn okio.**

# Keep Hilt
-keep class dagger.hilt.** { *; }
-keep class * extends dagger.hilt.android.lifecycle.HiltViewModel

# Keep Compose
-keep class androidx.compose.** { *; }

# Keep Room
-keep class androidx.room.** { *; }

# Keep DataStore
-keep class androidx.datastore.** { *; }

# Keep Kotlin
-keep class kotlin.** { *; }
-keep class kotlinx.coroutines.** { *; }

# Remove logging
-assumenosideeffects class android.util.Log {
    public static *** d(...);
    public static *** v(...);
    public static *** i(...);
}

# General optimization
-optimizationpasses 5
-dontusemixedcaseclassnames
