package com.almadina.app.data.local.preferences

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private const val APP_PREFERENCES = "almadina_preferences"

val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = APP_PREFERENCES)

class AppPreferences(private val context: Context) {
    companion object {
        private val API_BASE_URL = stringPreferencesKey("api_base_url")
        private val AI_MODEL = stringPreferencesKey("ai_model")
        private val LANGUAGE_PREFERENCE = stringPreferencesKey("language_preference")
        private val CACHE_ENABLED = stringPreferencesKey("cache_enabled")
        private val APP_THEME = stringPreferencesKey("app_theme")

        private const val DEFAULT_API_URL = "http://api.almadina.local"
        private const val DEFAULT_MODEL = "gemini-2.0-flash"
        private const val DEFAULT_LANGUAGE = "en"
        private const val DEFAULT_THEME = "system"
    }

    val apiBaseUrl: Flow<String> = context.dataStore.data.map { preferences ->
        preferences[API_BASE_URL] ?: DEFAULT_API_URL
    }

    val aiModel: Flow<String> = context.dataStore.data.map { preferences ->
        preferences[AI_MODEL] ?: DEFAULT_MODEL
    }

    val languagePreference: Flow<String> = context.dataStore.data.map { preferences ->
        preferences[LANGUAGE_PREFERENCE] ?: DEFAULT_LANGUAGE
    }

    val cacheEnabled: Flow<Boolean> = context.dataStore.data.map { preferences ->
        preferences[CACHE_ENABLED]?.toBoolean() ?: true
    }

    val appTheme: Flow<String> = context.dataStore.data.map { preferences ->
        preferences[APP_THEME] ?: DEFAULT_THEME
    }

    suspend fun setApiBaseUrl(url: String) {
        context.dataStore.edit { preferences ->
            preferences[API_BASE_URL] = url
        }
    }

    suspend fun setAiModel(model: String) {
        context.dataStore.edit { preferences ->
            preferences[AI_MODEL] = model
        }
    }

    suspend fun setLanguagePreference(language: String) {
        context.dataStore.edit { preferences ->
            preferences[LANGUAGE_PREFERENCE] = language
        }
    }

    suspend fun setCacheEnabled(enabled: Boolean) {
        context.dataStore.edit { preferences ->
            preferences[CACHE_ENABLED] = enabled.toString()
        }
    }

    suspend fun setAppTheme(theme: String) {
        context.dataStore.edit { preferences ->
            preferences[APP_THEME] = theme
        }
    }
}
