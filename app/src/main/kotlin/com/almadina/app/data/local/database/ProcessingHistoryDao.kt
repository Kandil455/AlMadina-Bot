package com.almadina.app.data.local.database

import androidx.room.Dao
import androidx.room.Delete
import androidx.room.Insert
import androidx.room.Query
import kotlinx.coroutines.flow.Flow

@Dao
interface ProcessingHistoryDao {
    @Insert
    suspend fun insertHistory(history: ProcessingHistoryEntity): Long

    @Query("SELECT * FROM processing_history ORDER BY createdAt DESC")
    fun getAllHistory(): Flow<List<ProcessingHistoryEntity>>

    @Query("SELECT * FROM processing_history WHERE id = :id")
    suspend fun getHistoryById(id: Long): ProcessingHistoryEntity?

    @Query("DELETE FROM processing_history")
    suspend fun clearHistory()

    @Delete
    suspend fun deleteHistory(history: ProcessingHistoryEntity)

    @Query("SELECT COUNT(*) FROM processing_history")
    suspend fun getHistoryCount(): Int
}
