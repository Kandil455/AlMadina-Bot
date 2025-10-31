package com.almadina.app.data.repository

import com.almadina.app.data.local.database.AlMadinaDatabase
import com.almadina.app.data.local.database.ProcessingHistoryEntity
import com.almadina.app.data.local.preferences.AppPreferences
import com.almadina.app.data.remote.api.AlMadinaApiService
import com.almadina.app.data.remote.model.ApiResponse
import com.almadina.app.data.remote.model.DocumentType
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Before
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class DocumentRepositoryTest {
    private lateinit var repository: DocumentRepository
    private val mockApiService: AlMadinaApiService = mockk()
    private val mockDatabase: AlMadinaDatabase = mockk()
    private val mockPreferences: AppPreferences = mockk()

    @Before
    fun setUp() {
        coEvery { mockPreferences.aiModel } returns flowOf("gemini-2.0-flash")
        coEvery { mockPreferences.languagePreference } returns flowOf("en")
        repository = DocumentRepository(mockApiService, mockDatabase, mockPreferences)
    }

    @Test
    fun testSummarizeDocument_Success() = runTest {
        val mockResponse = ApiResponse(
            status = "success",
            result = "<h1>Summary</h1>",
            tokensUsed = 1000,
            processingTimeMs = 2000
        )

        coEvery {
            mockApiService.summarizeDocument(any())
        } returns mockResponse

        coEvery {
            mockDatabase.processingHistoryDao().insertHistory(any())
        } returns 1L

        val result = repository.summarizeDocument(
            content = "test content",
            documentType = DocumentType.TEXT
        )

        assertTrue(result.isSuccess)
        assertNotNull(result.getOrNull())
    }

    @Test
    fun testSummarizeDocument_Error() = runTest {
        val mockResponse = ApiResponse(
            status = "error",
            result = "",
            error = "Processing failed"
        )

        coEvery {
            mockApiService.summarizeDocument(any())
        } returns mockResponse

        val result = repository.summarizeDocument(
            content = "test content",
            documentType = DocumentType.TEXT
        )

        assertTrue(result.isFailure)
    }

    @Test
    fun testGetProcessingHistory() = runTest {
        val mockEntity = ProcessingHistoryEntity(
            id = 1L,
            documentContent = "test",
            operationType = "summarize",
            result = "<h1>Summary</h1>",
            createdAt = System.currentTimeMillis()
        )

        coEvery {
            mockDatabase.processingHistoryDao().getAllHistory()
        } returns flowOf(listOf(mockEntity))

        val history = repository.getProcessingHistory()
        history.collect { results ->
            assertEquals(1, results.size)
            assertEquals(1L, results[0].id)
        }
    }

    @Test
    fun testClearHistory() = runTest {
        coEvery {
            mockDatabase.processingHistoryDao().clearHistory()
        } returns Unit

        repository.clearHistory()

        coVerify { mockDatabase.processingHistoryDao().clearHistory() }
    }
}
