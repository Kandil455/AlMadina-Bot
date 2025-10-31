package com.almadina.app.data.remote.api

import com.almadina.app.data.remote.model.ApiResponse
import com.almadina.app.data.remote.model.ExplainRequest
import com.almadina.app.data.remote.model.SummarizeRequest
import retrofit2.http.Body
import retrofit2.http.POST

interface AlMadinaApiService {
    @POST("/api/v1/summarize")
    suspend fun summarizeDocument(
        @Body request: SummarizeRequest
    ): ApiResponse

    @POST("/api/v1/explain")
    suspend fun explainContent(
        @Body request: ExplainRequest
    ): ApiResponse
}
