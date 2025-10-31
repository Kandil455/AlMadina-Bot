package com.almadina.app.presentation.navigation

sealed class Screen(val route: String) {
    object Dashboard : Screen("dashboard")
    object Summarize : Screen("summarize")
    object Explain : Screen("explain")
    object Upload : Screen("upload/{operationType}") {
        fun createRoute(operationType: String) = "upload/$operationType"
    }
    object Processing : Screen("processing/{operationType}") {
        fun createRoute(operationType: String) = "processing/$operationType"
    }
    object Results : Screen("results/{resultId}") {
        fun createRoute(resultId: Long) = "results/$resultId"
    }
    object Settings : Screen("settings")
}
