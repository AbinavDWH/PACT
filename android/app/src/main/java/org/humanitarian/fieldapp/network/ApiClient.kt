package org.humanitarian.fieldapp.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.humanitarian.fieldapp.models.FieldReport
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

sealed class ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>()
    data class Error(val message: String) : ApiResult<Nothing>()
}

object ApiClient {

    private const val BASE_URL = "http://10.0.2.2:8000"

    suspend fun postNeed(report: FieldReport): ApiResult<String> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null

            try {
                val url = URL("$BASE_URL/api/v1/needs")

                connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 8000
                connection.readTimeout = 8000
                connection.setRequestProperty("Content-Type", "application/json")
                connection.doOutput = true

                val payload = JSONObject()
                    .put("type", "need")
                    .put("organization_id", report.organizationId)
                    .put("location_code", report.locationCode)
                    .put("location_name", locationName(report.locationCode))
                    .put("location", locationName(report.locationCode))
                    .put("resource", resourceName(report.resourceCode))
                    .put("resource_code", report.resourceCode)
                    .put("quantity", report.quantity)
                    .put("urgency", urgencyName(report.urgencyCode))
                    .put("urgency_code", report.urgencyCode)
                    .put("notes", report.notes)
                    .put("source", "android")

                connection.outputStream.use { outputStream ->
                    outputStream.write(payload.toString().toByteArray())
                    outputStream.flush()
                }

                val responseCode = connection.responseCode

                val responseBody = if (responseCode in 200..299) {
                    connection.inputStream.bufferedReader().use { reader ->
                        reader.readText()
                    }
                } else {
                    connection.errorStream?.bufferedReader()?.use { reader ->
                        reader.readText()
                    } ?: ""
                }

                if (responseCode in 200..299) {
                    ApiResult.Success(responseBody.ifBlank { "HTTP $responseCode" })
                } else {
                    ApiResult.Error("HTTP $responseCode: ${responseBody.take(200)}")
                }
            } catch (exception: Exception) {
                ApiResult.Error(exception.message ?: "Network request failed")
            } finally {
                connection?.disconnect()
            }
        }
    }

    private fun resourceName(code: String): String {
        return when (code) {
            "F" -> "food_kits"
            "W" -> "water_kits"
            "M" -> "medical_kits"
            "T" -> "tents"
            "B" -> "blankets"
            "H" -> "hygiene_kits"
            "D" -> "medical_teams"
            else -> "unknown"
        }
    }

    private fun urgencyName(code: String): String {
        return when (code) {
            "L" -> "low"
            "M" -> "medium"
            "H" -> "high"
            "C" -> "critical"
            else -> "unknown"
        }
    }

    private fun locationName(code: String): String {
        return when (code) {
            "RA" -> "Region A"
            "RB" -> "Region B"
            "RC" -> "Region C"
            "D1" -> "District North"
            "D2" -> "District South"
            else -> code
        }
    }
}