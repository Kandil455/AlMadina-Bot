package com.almadina.app.presentation.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.almadina.app.R
import com.almadina.app.presentation.viewmodel.SettingsViewModel

@Composable
fun SettingsScreen(
    viewModel: SettingsViewModel,
    onBackClick: () -> Unit
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    var apiUrlInput by remember { mutableStateOf(uiState.apiBaseUrl) }
    var selectedModel by remember { mutableStateOf(uiState.aiModel) }
    var selectedLanguage by remember { mutableStateOf(uiState.languagePreference) }
    var showModelDropdown by remember { mutableStateOf(false) }
    var showLanguageDropdown by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(stringResource(R.string.settings)) },
                navigationIcon = {
                    IconButton(onClick = onBackClick) {
                        Icon(
                            imageVector = Icons.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.back)
                        )
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp)
        ) {
            // API Base URL Section
            Text(
                text = stringResource(R.string.api_endpoint),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            OutlinedTextField(
                value = apiUrlInput,
                onValueChange = { apiUrlInput = it },
                label = { Text("URL") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 16.dp)
            )
            Button(
                onClick = { viewModel.updateApiBaseUrl(apiUrlInput) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 24.dp)
            ) {
                Text(stringResource(android.R.string.ok))
            }

            // AI Model Selection
            Text(
                text = stringResource(R.string.ai_model),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            OutlinedTextField(
                value = selectedModel,
                onValueChange = {},
                label = { Text("Model") },
                readOnly = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 16.dp)
            )
            DropdownMenu(
                expanded = showModelDropdown,
                onDismissRequest = { showModelDropdown = false }
            ) {
                viewModel.getAvailableModels().forEach { model ->
                    DropdownMenuItem(
                        text = { Text(model) },
                        onClick = {
                            selectedModel = model
                            viewModel.updateAiModel(model)
                            showModelDropdown = false
                        }
                    )
                }
            }
            Button(
                onClick = { showModelDropdown = true },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 24.dp)
            ) {
                Text("Select Model")
            }

            // Language Preference
            Text(
                text = stringResource(R.string.language_preference),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            OutlinedTextField(
                value = selectedLanguage,
                onValueChange = {},
                label = { Text("Language") },
                readOnly = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 16.dp)
            )
            DropdownMenu(
                expanded = showLanguageDropdown,
                onDismissRequest = { showLanguageDropdown = false }
            ) {
                listOf("en", "ar", "bilingual").forEach { lang ->
                    DropdownMenuItem(
                        text = { Text(lang) },
                        onClick = {
                            selectedLanguage = lang
                            viewModel.updateLanguagePreference(lang)
                            showLanguageDropdown = false
                        }
                    )
                }
            }
            Button(
                onClick = { showLanguageDropdown = true },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 24.dp)
            ) {
                Text("Select Language")
            }

            // Cache Management
            Text(
                text = stringResource(R.string.cache_management),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            Text(
                text = stringResource(R.string.cache_size, (uiState.cacheSize / 1024 / 1024).toString()),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            Button(
                onClick = { viewModel.clearCache() },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text(stringResource(R.string.clear_cache))
            }

            // About & Support
            Text(
                text = stringResource(R.string.about),
                style = MaterialTheme.typography.titleMedium,
                modifier = Modifier.padding(top = 24.dp, bottom = 8.dp)
            )
            Text(
                text = stringResource(R.string.app_version, "1.0.0"),
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(bottom = 8.dp)
            )
            Text(
                text = "API Status: ${if (uiState.apiStatusConnected) stringResource(R.string.connected) else stringResource(R.string.disconnected)}",
                style = MaterialTheme.typography.bodyMedium
            )
        }
    }
}
