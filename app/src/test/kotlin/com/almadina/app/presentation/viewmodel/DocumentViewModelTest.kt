package com.almadina.app.presentation.viewmodel

import com.almadina.app.data.remote.model.DocumentType
import com.almadina.app.data.remote.model.ProcessingResult
import com.almadina.app.data.repository.DocumentRepository
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Before
import org.junit.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class DocumentViewModelTest {
    private lateinit var viewModel: DocumentViewModel
    private val mockRepository: DocumentRepository = mockk()
    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        coEvery { mockRepository.getProcessingHistory() } returns flowOf(emptyList())
        viewModel = DocumentViewModel(mockRepository)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testSummarizeDocument_Success() = runTest {
        val mockResult = ProcessingResult(
            id = 1L,
            documentContent = "test content",
            operationType = "summarize",
            result = "<h1>Summary</h1><p>Test summary</p>",
            createdAt = System.currentTimeMillis(),
            processingTimeMs = 2000L
        )

        coEvery {
            mockRepository.summarizeDocument(any(), any(), any())
        } returns Result.success(mockResult)

        viewModel.summarizeDocument(
            content = "test content",
            documentType = DocumentType.TEXT
        )

        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(mockResult, state.currentResult)
        assertNull(state.error)
    }

    @Test
    fun testSummarizeDocument_Failure() = runTest {
        val exception = Exception("API Error")

        coEvery {
            mockRepository.summarizeDocument(any(), any(), any())
        } returns Result.failure(exception)

        viewModel.summarizeDocument(
            content = "test content",
            documentType = DocumentType.TEXT
        )

        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertNull(state.currentResult)
        assertEquals("API Error", state.error)
    }

    @Test
    fun testExplainContent_Success() = runTest {
        val mockResult = ProcessingResult(
            id = 2L,
            documentContent = "test content",
            operationType = "explain",
            result = "<h1>Explanation</h1><p>Detailed explanation</p>",
            createdAt = System.currentTimeMillis(),
            processingTimeMs = 3000L
        )

        coEvery {
            mockRepository.explainContent(any(), any(), any(), any())
        } returns Result.success(mockResult)

        viewModel.explainContent(
            content = "test content",
            documentType = DocumentType.TEXT,
            persona = "professor",
            language = "en"
        )

        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(mockResult, state.currentResult)
        assertNull(state.error)
    }

    @Test
    fun testClearHistory() = runTest {
        coEvery { mockRepository.clearHistory() } returns Unit

        viewModel.clearHistory()

        testDispatcher.scheduler.advanceUntilIdle()

        coVerify { mockRepository.clearHistory() }
    }

    @Test
    fun testClearError() {
        val initialState = viewModel.uiState.value.copy(error = "Some error")

        viewModel.clearError()

        assertTrue(viewModel.uiState.value.error == null)
    }
}
