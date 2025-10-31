package com.almadina.app.di

import android.content.Context
import com.almadina.app.data.local.database.AlMadinaDatabase
import com.almadina.app.data.local.preferences.AppPreferences
import com.almadina.app.data.remote.api.AlMadinaApiService
import com.almadina.app.data.repository.DocumentRepository
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Singleton
    @Provides
    fun provideAppPreferences(
        @ApplicationContext context: Context
    ): AppPreferences = AppPreferences(context)

    @Singleton
    @Provides
    fun provideAlMadinaDatabase(
        @ApplicationContext context: Context
    ): AlMadinaDatabase = AlMadinaDatabase.getDatabase(context)

    @Singleton
    @Provides
    fun provideOkHttpClient(): OkHttpClient {
        val loggingInterceptor = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        return OkHttpClient.Builder()
            .addInterceptor(loggingInterceptor)
            .connectTimeout(60, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .build()
    }

    @Singleton
    @Provides
    fun provideAlMadinaApiService(
        okHttpClient: OkHttpClient,
        preferences: AppPreferences
    ): AlMadinaApiService {
        return Retrofit.Builder()
            .baseUrl("http://api.almadina.local") // Will be overridden by preferences
            .addConverterFactory(GsonConverterFactory.create())
            .client(okHttpClient)
            .build()
            .create(AlMadinaApiService::class.java)
    }

    @Singleton
    @Provides
    fun provideDocumentRepository(
        apiService: AlMadinaApiService,
        database: AlMadinaDatabase,
        preferences: AppPreferences
    ): DocumentRepository = DocumentRepository(apiService, database, preferences)
}
