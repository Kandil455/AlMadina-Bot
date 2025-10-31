package com.almadina.app.data.remote.model

import com.google.gson.annotations.SerializedName

// Request models
data class SummarizeRequest(
    @SerializedName("document_type")
    val documentType: String,
    @SerializedName("content")
    val content: String,
    @SerializedName("model")
    val model: String,
    @SerializedName("style")
    val style: String? = null
)

data class ExplainRequest(
    @SerializedName("document_type")
    val documentType: String,
    @SerializedName("content")
    val content: String,
    @SerializedName("model")
    val model: String,
    @SerializedName("persona")
    val persona: String? = null,
    @SerializedName("language")
    val language: String? = null
)

// Response models
data class ApiResponse(
    @SerializedName("status")
    val status: String,
    @SerializedName("result")
    val result: String,
    @SerializedName("tokens_used")
    val tokensUsed: Int? = null,
    @SerializedName("processing_time_ms")
    val processingTimeMs: Long? = null,
    @SerializedName("error")
    val error: String? = null
)

// Document types
enum class DocumentType {
    PDF,
    IMAGE,
    TEXT
}

// Processing result domain model
data class ProcessingResult(
    val id: Long = 0,
    val documentContent: String,
    val operationType: String,
    val result: String,
    val createdAt: Long,
    val processingTimeMs: Long? = null,
    val isCached: Boolean = false
)
