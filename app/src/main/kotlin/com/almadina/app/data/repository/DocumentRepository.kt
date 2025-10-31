package com.almadina.app.data.repository

import com.almadina.app.data.local.database.AlMadinaDatabase
import com.almadina.app.data.local.database.ProcessingHistoryEntity
import com.almadina.app.data.local.preferences.AppPreferences
import com.almadina.app.data.remote.api.AlMadinaApiService
import com.almadina.app.data.remote.model.DocumentType
import com.almadina.app.data.remote.model.ExplainRequest
import com.almadina.app.data.remote.model.ProcessingResult
import com.almadina.app.data.remote.model.SummarizeRequest
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

class DocumentRepository(
    private val apiService: AlMadinaApiService,
    private val database: AlMadinaDatabase,
    private val preferences: AppPreferences
) {
    suspend fun summarizeDocument(
        content: String,
        documentType: DocumentType,
        style: String? = null
    ): Result<ProcessingResult> = try {
        val model = preferences.aiModel.map { it }.collect { model ->
            val request = SummarizeRequest(
                documentType = documentType.toString().lowercase(),
                content = content,
                model = model,
                style = style
            )
            val response = apiService.summarizeDocument(request)

            if (response.status == "success") {
                val result = ProcessingResult(
                    documentContent = content.take(100), // Store first 100 chars for reference
                    operationType = "summarize",
                    result = response.result,
                    createdAt = System.currentTimeMillis(),
                    processingTimeMs = response.processingTimeMs
                )

                // Save to local database
                val entity = ProcessingHistoryEntity(
                    documentContent = result.documentContent,
                    operationType = result.operationType,
                    result = result.result,
                    createdAt = result.createdAt,
                    processingTimeMs = result.processingTimeMs
                )
                val id = database.processingHistoryDao().insertHistory(entity)

                Result.success(result.copy(id = id))
            } else {
                Result.failure(Exception(response.error ?: "Unknown error"))
            }
        }
        model
    } catch (e: Exception) {
        Result.failure(e)
    }

    suspend fun explainContent(
        content: String,
        documentType: DocumentType,
        persona: String? = null,
        language: String? = null
    ): Result<ProcessingResult> = try {
        val currentLanguage = language ?: preferences.languagePreference.map { it }.collect { it }
        val model = preferences.aiModel.map { it }.collect { model ->
            val request = ExplainRequest(
                documentType = documentType.toString().lowercase(),
                content = content,
                model = model,
                persona = persona,
                language = currentLanguage
            )
            val response = apiService.explainContent(request)

            if (response.status == "success") {
                val result = ProcessingResult(
                    documentContent = content.take(100),
                    operationType = "explain",
                    result = response.result,
                    createdAt = System.currentTimeMillis(),
                    processingTimeMs = response.processingTimeMs
                )

                // Save to local database
                val entity = ProcessingHistoryEntity(
                    documentContent = result.documentContent,
                    operationType = result.operationType,
                    result = result.result,
                    createdAt = result.createdAt,
                    processingTimeMs = result.processingTimeMs
                )
                val id = database.processingHistoryDao().insertHistory(entity)

                Result.success(result.copy(id = id))
            } else {
                Result.failure(Exception(response.error ?: "Unknown error"))
            }
        }
        model
    } catch (e: Exception) {
        Result.failure(e)
    }

    fun getProcessingHistory(): Flow<List<ProcessingResult>> {
        return database.processingHistoryDao().getAllHistory().map { entities ->
            entities.map { entity ->
                ProcessingResult(
                    id = entity.id,
                    documentContent = entity.documentContent,
                    operationType = entity.operationType,
                    result = entity.result,
                    createdAt = entity.createdAt,
                    processingTimeMs = entity.processingTimeMs,
                    isCached = true
                )
            }
        }
    }

    suspend fun clearHistory() {
        database.processingHistoryDao().clearHistory()
    }

    suspend fun deleteHistoryItem(id: Long) {
        val item = database.processingHistoryDao().getHistoryById(id)
        if (item != null) {
            database.processingHistoryDao().deleteHistory(item)
        }
    }
}
