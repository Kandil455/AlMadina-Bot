package com.almadina.app.presentation.viewmodel

import com.almadina.app.data.local.database.AlMadinaDatabase
import com.almadina.app.data.local.preferences.AppPreferences
import io.mockk.coEvery
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

@OptIn(ExperimentalCoroutinesApi::class)
class SettingsViewModelTest {
    private lateinit var viewModel: SettingsViewModel
    private val mockPreferences: AppPreferences = mockk()
    private val mockDatabase: AlMadinaDatabase = mockk()
    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        coEvery { mockPreferences.apiBaseUrl } returns flowOf("http://api.almadina.local")
        coEvery { mockPreferences.aiModel } returns flowOf("gemini-2.0-flash")
        coEvery { mockPreferences.languagePreference } returns flowOf("en")
        coEvery { mockDatabase.processingHistoryDao().getHistoryCount() } returns 0

        viewModel = SettingsViewModel(mockPreferences, mockDatabase)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun testGetAvailableModels() {
        val models = viewModel.getAvailableModels()
        assertEquals(3, models.size)
        assert(models.contains("gemini-2.0-flash"))
        assert(models.contains("gemini-1.5-flash"))
        assert(models.contains("gemini-1.5-pro"))
    }

    @Test
    fun testUpdateApiBaseUrl() = runTest {
        coEvery { mockPreferences.setApiBaseUrl(any()) } returns Unit

        viewModel.updateApiBaseUrl("http://new-api.almadina.local")

        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(false, state.isSaving)
    }

    @Test
    fun testUpdateAiModel() = runTest {
        coEvery { mockPreferences.setAiModel(any()) } returns Unit

        viewModel.updateAiModel("gemini-1.5-pro")

        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(false, state.isSaving)
    }

    @Test
    fun testUpdateLanguagePreference() = runTest {
        coEvery { mockPreferences.setLanguagePreference(any()) } returns Unit

        viewModel.updateLanguagePreference("ar")

        testDispatcher.scheduler.advanceUntilIdle()

        val state = viewModel.uiState.value
        assertEquals(false, state.isSaving)
    }
}
