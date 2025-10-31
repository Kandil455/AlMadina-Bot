package com.almadina.app.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.almadina.app.data.local.database.AlMadinaDatabase
import com.almadina.app.data.local.preferences.AppPreferences
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class SettingsUiState(
    val apiBaseUrl: String = "",
    val aiModel: String = "",
    val languagePreference: String = "en",
    val cacheSize: Long = 0,
    val apiStatusConnected: Boolean = false,
    val isSaving: Boolean = false,
    val saveSuccess: Boolean = false
)

@HiltViewModel
class SettingsViewModel @Inject constructor(
    private val preferences: AppPreferences,
    private val database: AlMadinaDatabase
) : ViewModel() {

    private val _uiState = MutableStateFlow(SettingsUiState())
    val uiState: StateFlow<SettingsUiState> = _uiState.asStateFlow()

    private val availableModels = listOf(
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    )

    init {
        loadSettings()
        loadCacheSize()
    }

    private fun loadSettings() {
        viewModelScope.launch {
            combine(
                preferences.apiBaseUrl,
                preferences.aiModel,
                preferences.languagePreference
            ) { url, model, lang ->
                _uiState.update { state ->
                    state.copy(
                        apiBaseUrl = url,
                        aiModel = model,
                        languagePreference = lang
                    )
                }
            }.collect {}
        }
    }

    private fun loadCacheSize() {
        viewModelScope.launch {
            val historyCount = database.processingHistoryDao().getHistoryCount()
            val estimatedSize = historyCount * 50L // Rough estimate: 50KB per item
            _uiState.update { state ->
                state.copy(cacheSize = estimatedSize)
            }
        }
    }

    fun updateApiBaseUrl(url: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isSaving = true) }
            try {
                preferences.setApiBaseUrl(url)
                _uiState.update { it.copy(isSaving = false, saveSuccess = true) }
            } catch (e: Exception) {
                _uiState.update { it.copy(isSaving = false, saveSuccess = false) }
            }
        }
    }

    fun updateAiModel(model: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isSaving = true) }
            try {
                preferences.setAiModel(model)
                _uiState.update { it.copy(isSaving = false, saveSuccess = true) }
            } catch (e: Exception) {
                _uiState.update { it.copy(isSaving = false, saveSuccess = false) }
            }
        }
    }

    fun updateLanguagePreference(language: String) {
        viewModelScope.launch {
            _uiState.update { it.copy(isSaving = true) }
            try {
                preferences.setLanguagePreference(language)
                _uiState.update { it.copy(isSaving = false, saveSuccess = true) }
            } catch (e: Exception) {
                _uiState.update { it.copy(isSaving = false, saveSuccess = false) }
            }
        }
    }

    fun clearCache() {
        viewModelScope.launch {
            _uiState.update { it.copy(isSaving = true) }
            try {
                database.processingHistoryDao().clearHistory()
                _uiState.update { state ->
                    state.copy(isSaving = false, cacheSize = 0, saveSuccess = true)
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(isSaving = false, saveSuccess = false) }
            }
        }
    }

    fun checkApiStatus() {
        viewModelScope.launch {
            try {
                // TODO: Implement actual API status check
                _uiState.update { it.copy(apiStatusConnected = true) }
            } catch (e: Exception) {
                _uiState.update { it.copy(apiStatusConnected = false) }
            }
        }
    }

    fun getAvailableModels(): List<String> = availableModels
}
