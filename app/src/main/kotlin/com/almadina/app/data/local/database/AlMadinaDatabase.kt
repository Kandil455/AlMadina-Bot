package com.almadina.app.data.local.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase

@Database(
    entities = [ProcessingHistoryEntity::class],
    version = 1,
    exportSchema = false
)
abstract class AlMadinaDatabase : RoomDatabase() {
    abstract fun processingHistoryDao(): ProcessingHistoryDao

    companion object {
        private var INSTANCE: AlMadinaDatabase? = null
        private const val DATABASE_NAME = "almadina_database"

        fun getDatabase(context: Context): AlMadinaDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AlMadinaDatabase::class.java,
                    DATABASE_NAME
                ).build()
                INSTANCE = instance
                instance
            }
        }
    }
}
