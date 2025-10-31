package com.almadina.app

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.os.Bundle
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.almadina.app.presentation.navigation.Screen
import com.almadina.app.presentation.ui.screens.DashboardScreen
import com.almadina.app.presentation.ui.screens.ProcessingScreen
import com.almadina.app.presentation.ui.screens.ResultsScreen
import com.almadina.app.presentation.ui.screens.SettingsScreen
import com.almadina.app.presentation.ui.screens.UploadScreen
import com.almadina.app.presentation.ui.theme.AlMadinaTheme
import com.almadina.app.presentation.viewmodel.DocumentViewModel
import com.almadina.app.presentation.viewmodel.SettingsViewModel
import com.almadina.app.utils.PdfGenerator
import dagger.hilt.android.AndroidEntryPoint

@AndroidEntryPoint
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            AlMadinaTheme {
                val navController = rememberNavController()
                val documentViewModel: DocumentViewModel = hiltViewModel()
                val settingsViewModel: SettingsViewModel = hiltViewModel()

                NavHost(
                    navController = navController,
                    startDestination = Screen.Dashboard.route
                ) {
                    composable(Screen.Dashboard.route) {
                        DashboardScreen(
                            onSummarizeClick = {
                                navController.navigate(Screen.Upload.createRoute("summarize"))
                            },
                            onExplainClick = {
                                navController.navigate(Screen.Upload.createRoute("explain"))
                            },
                            onLibraryClick = {
                                // Future: Navigate to library
                            },
                            onSettingsClick = {
                                navController.navigate(Screen.Settings.route)
                            }
                        )
                    }

                    composable(
                        route = Screen.Upload.route,
                        arguments = listOf(
                            navArgument("operationType") {
                                type = NavType.StringType
                            }
                        )
                    ) { backStackEntry ->
                        val operationType = backStackEntry.arguments?.getString("operationType") ?: "summarize"
                        UploadScreen(
                            operationType = operationType,
                            onBackClick = { navController.popBackStack() },
                            onUpload = { content, _ ->
                                // Start processing
                                navController.navigate(Screen.Processing.createRoute(operationType)) {
                                    launchSingleTop = true
                                }

                                // Process document
                                when (operationType) {
                                    "summarize" -> {
                                        documentViewModel.summarizeDocument(
                                            content = content,
                                            documentType = com.almadina.app.data.remote.model.DocumentType.TEXT
                                        )
                                    }
                                    "explain" -> {
                                        documentViewModel.explainContent(
                                            content = content,
                                            documentType = com.almadina.app.data.remote.model.DocumentType.TEXT
                                        )
                                    }
                                }
                            }
                        )
                    }

                    composable(
                        route = Screen.Processing.route,
                        arguments = listOf(
                            navArgument("operationType") {
                                type = NavType.StringType
                            }
                        )
                    ) { backStackEntry ->
                        val operationType = backStackEntry.arguments?.getString("operationType") ?: "summarize"
                        ProcessingScreen(
                            operationType = operationType,
                            onCancel = { navController.popBackStack() }
                        )
                    }

                    composable(
                        route = Screen.Results.route,
                        arguments = listOf(
                            navArgument("resultId") {
                                type = NavType.LongType
                            }
                        )
                    ) { backStackEntry ->
                        val resultId = backStackEntry.arguments?.getLong("resultId") ?: 0L
                        val result = documentViewModel.uiState.value.processingHistory.find { it.id == resultId }
                        ResultsScreen(
                            result = result,
                            onBackClick = { navController.popBackStack() },
                            onDownloadPdf = {
                                result?.let { r ->
                                    val pdfGenerator = PdfGenerator(this@MainActivity)
                                    val pdfResult = pdfGenerator.generatePdfFromHtml(r.result)
                                    pdfResult.onSuccess {
                                        Toast.makeText(
                                            this@MainActivity,
                                            getString(R.string.pdf_downloaded),
                                            Toast.LENGTH_SHORT
                                        ).show()
                                    }.onFailure {
                                        Toast.makeText(
                                            this@MainActivity,
                                            getString(R.string.pdf_generation_failed),
                                            Toast.LENGTH_SHORT
                                        ).show()
                                    }
                                }
                            },
                            onShare = {
                                result?.let { r ->
                                    val sendIntent = android.content.Intent().apply {
                                        action = android.content.Intent.ACTION_SEND
                                        putExtra(android.content.Intent.EXTRA_TEXT, r.result)
                                        type = "text/plain"
                                    }
                                    val shareIntent = android.content.Intent.createChooser(
                                        sendIntent,
                                        "Share Result"
                                    )
                                    startActivity(shareIntent)
                                }
                            },
                            onCopyText = {
                                result?.let { r ->
                                    val clipboard =
                                        getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                    val clip =
                                        ClipData.newPlainText("Summarized Content", r.result)
                                    clipboard.setPrimaryClip(clip)
                                    Toast.makeText(
                                        this@MainActivity,
                                        getString(R.string.text_copied),
                                        Toast.LENGTH_SHORT
                                    ).show()
                                }
                            }
                        )
                    }

                    composable(Screen.Settings.route) {
                        SettingsScreen(
                            viewModel = settingsViewModel,
                            onBackClick = { navController.popBackStack() }
                        )
                    }
                }
            }
        }
    }
}
