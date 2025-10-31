package com.almadina.app.utils

import android.content.Context
import android.os.Environment
import com.itextpdf.html2pdf.HtmlConverter
import com.itextpdf.kernel.pdf.PdfWriter
import java.io.File
import java.io.FileOutputStream
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class PdfGenerator(private val context: Context) {
    fun generatePdfFromHtml(
        htmlContent: String,
        fileName: String = generateFileName()
    ): Result<File> = try {
        val downloadsDir = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS)
        if (!downloadsDir.exists()) {
            downloadsDir.mkdirs()
        }

        val pdfFile = File(downloadsDir, fileName)
        val outputStream = FileOutputStream(pdfFile)

        val writer = PdfWriter(outputStream)
        val document = com.itextpdf.kernel.pdf.PdfDocument(writer)

        // Convert HTML to PDF
        HtmlConverter.convertToDocument(htmlContent, document)
        document.close()

        Result.success(pdfFile)
    } catch (e: Exception) {
        Result.failure(e)
    }

    private fun generateFileName(): String {
        val timestamp = SimpleDateFormat("yyyy-MM-dd_HH-mm", Locale.getDefault()).format(Date())
        return "almadina_$timestamp.pdf"
    }
}
