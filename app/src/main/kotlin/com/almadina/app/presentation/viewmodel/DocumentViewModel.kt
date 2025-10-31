package com.almadina.app.presentation.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.almadina.app.data.remote.model.DocumentType
import com.almadina.app.data.remote.model.ProcessingResult
import com.almadina.app.data.repository.DocumentRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import javax.inject.Inject

data class DocumentUiState(
    val isLoading: Boolean = false,
    val currentResult: ProcessingResult? = null,
    val processingHistory: List<ProcessingResult> = emptyList(),
    val error: String? = null,
    val processingTimeMs: Long? = null
)

@HiltViewModel
class DocumentViewModel @Inject constructor(
    private val documentRepository: DocumentRepository
) : ViewModel() {

    private val _uiState = MutableStateFlow(DocumentUiState())
    val uiState: StateFlow<DocumentUiState> = _uiState.asStateFlow()

    init {
        loadProcessingHistory()
    }

    private fun loadProcessingHistory() {
        viewModelScope.launch {
            documentRepository.getProcessingHistory().collect { results ->
                _uiState.update { state ->
                    state.copy(processingHistory = results)
                }
            }
        }
    }

    fun summarizeDocument(
        content: String,
        documentType: DocumentType,
        style: String? = null
    ) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            try {
                val result = documentRepository.summarizeDocument(content, documentType, style)
                result.onSuccess { processingResult ->
                    _uiState.update { state ->
                        state.copy(
                            isLoading = false,
                            currentResult = processingResult,
                            processingTimeMs = processingResult.processingTimeMs
                        )
                    }
                }.onFailure { exception ->
                    _uiState.update { state ->
                        state.copy(
                            isLoading = false,
                            error = exception.message ?: "Summarization failed"
                        )
                    }
                }
            } catch (e: Exception) {
                _uiState.update { state ->
                    state.copy(
                        isLoading = false,
                        error = e.message ?: "An error occurred"
                    )
                }
            }
        }
    }

    fun explainContent(
        content: String,
        documentType: DocumentType,
        persona: String? = null,
        language: String? = null
    ) {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            try {
                val result = documentRepository.explainContent(content, documentType, persona, language)
                result.onSuccess { processingResult ->
                    _uiState.update { state ->
                        state.copy(
                            isLoading = false,
                            currentResult = processingResult,
                            processingTimeMs = processingResult.processingTimeMs
                        )
                    }
                }.onFailure { exception ->
                    _uiState.update { state ->
                        state.copy(
                            isLoading = false,
                            error = exception.message ?: "Explanation failed"
                        )
                    }
                }
            } catch (e: Exception) {
                _uiState.update { state ->
                    state.copy(
                        isLoading = false,
                        error = e.message ?: "An error occurred"
                    )
                }
            }
        }
    }

    fun clearHistory() {
        viewModelScope.launch {
            documentRepository.clearHistory()
        }
    }

    fun deleteHistoryItem(id: Long) {
        viewModelScope.launch {
            documentRepository.deleteHistoryItem(id)
        }
    }

    fun clearError() {
        _uiState.update { it.copy(error = null) }
    }
}
