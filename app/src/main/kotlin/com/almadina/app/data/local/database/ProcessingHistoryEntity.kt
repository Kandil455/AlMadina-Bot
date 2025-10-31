package com.almadina.app.data.local.database

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "processing_history")
data class ProcessingHistoryEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val documentContent: String,
    val operationType: String, // "summarize" or "explain"
    val result: String,
    val createdAt: Long,
    val processingTimeMs: Long? = null,
    val filePath: String? = null
)
