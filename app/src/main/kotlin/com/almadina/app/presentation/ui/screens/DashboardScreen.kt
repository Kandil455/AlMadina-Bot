package com.almadina.app.presentation.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.almadina.app.R
import com.almadina.app.presentation.ui.components.FeatureCard

@Composable
fun DashboardScreen(
    onSummarizeClick: () -> Unit,
    onExplainClick: () -> Unit,
    onLibraryClick: () -> Unit,
    onSettingsClick: () -> Unit
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = stringResource(R.string.dashboard_title),
                        style = MaterialTheme.typography.headlineLarge
                    )
                },
                actions = {
                    IconButton(onClick = onSettingsClick) {
                        Icon(
                            imageVector = Icons.Filled.Settings,
                            contentDescription = stringResource(R.string.settings)
                        )
                    }
                }
            )
        }
    ) { padding ->
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentAlignment = Alignment.Center
        ) {
            Column(
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(24.dp),
                modifier = Modifier
                    .padding(24.dp)
                    .fillMaxWidth()
            ) {
                // First row of cards
                Row(
                    horizontalArrangement = Arrangement.spacedBy(16.dp),
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    FeatureCard(
                        title = stringResource(R.string.summarize_feature),
                        description = stringResource(R.string.summarize_desc),
                        icon = Icons.Default.Info,
                        gradientStart = Color(0xFF2196F3),
                        gradientEnd = Color(0xFF1976D2),
                        onClick = onSummarizeClick,
                        modifier = Modifier.weight(1f)
                    )

                    FeatureCard(
                        title = stringResource(R.string.explain_feature),
                        description = stringResource(R.string.explain_desc),
                        icon = Icons.Default.Info,
                        gradientStart = Color(0xFF4CAF50),
                        gradientEnd = Color(0xFF388E3C),
                        onClick = onExplainClick,
                        modifier = Modifier.weight(1f)
                    )
                }

                // Second row - Library card (disabled for now)
                FeatureCard(
                    title = stringResource(R.string.library_feature),
                    description = stringResource(R.string.library_desc),
                    icon = Icons.Default.Info,
                    gradientStart = Color(0xFF9C27B0),
                    gradientEnd = Color(0xFF7B1FA2),
                    enabled = false,
                    onClick = onLibraryClick
                )
            }
        }
    }
}
