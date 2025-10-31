package com.almadina.app.utils

import android.content.Context
import com.almadina.app.R
import retrofit2.HttpException
import java.io.IOException
import java.net.SocketTimeoutException

object ErrorHandler {
    fun getErrorMessage(context: Context, throwable: Throwable): String {
        return when (throwable) {
            is HttpException -> {
                when (throwable.code()) {
                    400 -> context.getString(R.string.invalid_input)
                    401 -> context.getString(R.string.unauthorized)
                    429 -> context.getString(R.string.rate_limit)
                    500, 502, 503, 504 -> context.getString(R.string.server_error)
                    else -> "HTTP Error ${throwable.code()}: ${throwable.message()}"
                }
            }
            is SocketTimeoutException -> context.getString(R.string.timeout_error)
            is IOException -> context.getString(R.string.network_error)
            else -> throwable.message ?: context.getString(android.R.string.unknownLabel)
        }
    }

    fun getErrorTitle(context: Context, throwable: Throwable): String {
        return when (throwable) {
            is HttpException -> when (throwable.code()) {
                400 -> "Bad Request"
                401 -> "Unauthorized"
                429 -> "Rate Limited"
                500, 502, 503, 504 -> "Server Error"
                else -> "HTTP Error"
            }
            is SocketTimeoutException -> "Request Timeout"
            is IOException -> "Network Error"
            else -> "Error"
        }
    }
}
