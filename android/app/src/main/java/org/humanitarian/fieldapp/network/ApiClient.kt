package org.humanitarian.fieldapp.network

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.humanitarian.fieldapp.models.FieldReport
import org.humanitarian.fieldapp.models.OrgMatch
import org.humanitarian.fieldapp.models.OrgRequest
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL

sealed class ApiResult<out T> {
    data class Success<T>(val data: T) : ApiResult<T>()
    data class Error(val message: String) : ApiResult<Nothing>()
}

object ApiClient {

    // ═══════════════════════════════════════════════════════
    // CHANNEL 1: NORMAL INTERNET API
    // Used when internet is available (Field Report direct send, M10 sync)
    // ═══════════════════════════════════════════════════════
    private const val INTERNET_API_URL = "http://10.142.1.84:8000"

    // ═══════════════════════════════════════════════════════
    // CHANNEL 2: SMS GATEWAY (SIMULATED)
    // Used for SMS fallback: sending SMS payloads + polling inbox
    // Can be a DIFFERENT IP/port to simulate a separate telecom gateway
    // ═══════════════════════════════════════════════════════
    private const val SMS_GATEWAY_URL = "http://10.142.1.84:8000"

    // ───────────── INTERNET CHANNEL ─────────────

    suspend fun postNeed(report: FieldReport): ApiResult<String> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL("$INTERNET_API_URL/api/v1/needs")
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
                    .put("latitude", report.latitude ?: 0.0)
                    .put("longitude", report.longitude ?: 0.0)

                connection.outputStream.use { outputStream ->
                    outputStream.write(payload.toString().toByteArray())
                    outputStream.flush()
                }

                val responseCode = connection.responseCode
                val responseBody = if (responseCode in 200..299) {
                    connection.inputStream.bufferedReader().use { it.readText() }
                } else {
                    connection.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                }

                if (responseCode in 200..299) ApiResult.Success(responseBody.ifBlank { "HTTP $responseCode" })
                else ApiResult.Error("HTTP $responseCode: ${responseBody.take(200)}")
            } catch (exception: Exception) {
                ApiResult.Error(exception.message ?: "Network request failed")
            } finally {
                connection?.disconnect()
            }
        }
    }

    // ───────────── SMS GATEWAY CHANNEL ─────────────

    suspend fun postSmsWebhook(smsPayload: String): ApiResult<String> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL("$SMS_GATEWAY_URL/api/v1/sms/webhook")
                connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 8000
                connection.readTimeout = 8000
                connection.setRequestProperty("Content-Type", "application/json")
                connection.doOutput = true

                val payload = JSONObject().put("sms", smsPayload)

                connection.outputStream.use { outputStream ->
                    outputStream.write(payload.toString().toByteArray())
                    outputStream.flush()
                }

                val responseCode = connection.responseCode
                val responseBody = if (responseCode in 200..299) {
                    connection.inputStream.bufferedReader().use { it.readText() }
                } else {
                    connection.errorStream?.bufferedReader()?.use { it.readText() } ?: ""
                }

                if (responseCode in 200..299) ApiResult.Success(responseBody)
                else ApiResult.Error("HTTP $responseCode: ${responseBody.take(200)}")
            } catch (exception: Exception) {
                ApiResult.Error(exception.message ?: "SMS gateway unreachable")
            } finally {
                connection?.disconnect()
            }
        }
    }

    suspend fun getSmsInbox(): ApiResult<List<String>> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL("$SMS_GATEWAY_URL/api/v1/sms/inbox")
                connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.connectTimeout = 5000
                connection.readTimeout = 5000

                val responseCode = connection.responseCode
                if (responseCode in 200..299) {
                    val body = connection.inputStream.bufferedReader().use { it.readText() }
                    val json = JSONObject(body)
                    val messagesArray = json.getJSONArray("messages")
                    val messages = mutableListOf<String>()
                    for (i in 0 until messagesArray.length()) {
                        messages.add(messagesArray.getString(i))
                    }
                    ApiResult.Success(messages)
                } else {
                    ApiResult.Error("HTTP $responseCode")
                }
            } catch (e: Exception) {
                ApiResult.Error(e.message ?: "Inbox fetch failed")
            } finally {
                connection?.disconnect()
            }
        }
    }

    suspend fun clearInbox(): ApiResult<String> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL("$SMS_GATEWAY_URL/api/v1/sms/clear")
                connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 5000
                connection.readTimeout = 5000
                connection.responseCode
                ApiResult.Success("cleared")
            } catch (e: Exception) {
                ApiResult.Error(e.message ?: "Clear failed")
            } finally {
                connection?.disconnect()
            }
        }
    }

    // ───────────── REAL-TIME LOCATION + STATUS POLLING ─────────────

    // Send live GPS to backend every 10 seconds
    suspend fun postLocationUpdate(organizationId: String, lat: Double, lng: Double): ApiResult<String> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL("$INTERNET_API_URL/api/v1/location/update")
                connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.connectTimeout = 5000
                connection.readTimeout = 5000
                connection.setRequestProperty("Content-Type", "application/json")
                connection.doOutput = true

                val payload = JSONObject()
                    .put("organization_id", organizationId)
                    .put("latitude", lat)
                    .put("longitude", lng)

                connection.outputStream.use { it.write(payload.toString().toByteArray()); it.flush() }

                val code = connection.responseCode
                if (code in 200..299) ApiResult.Success("ok")
                else ApiResult.Error("HTTP $code")
            } catch (e: Exception) {
                ApiResult.Error(e.message ?: "Location update failed")
            } finally {
                connection?.disconnect()
            }
        }
    }

    // Poll approval status of this org's requests
        // Poll approval + allocation status of this org's requests
    suspend fun getRequestsByOrg(organizationId: String): ApiResult<List<OrgRequest>> {
        return withContext(Dispatchers.IO) {
            var connection: HttpURLConnection? = null
            try {
                val url = URL("$INTERNET_API_URL/api/v1/requests/by-org/$organizationId")
                connection = url.openConnection() as HttpURLConnection
                connection.requestMethod = "GET"
                connection.connectTimeout = 5000
                connection.readTimeout = 5000

                val code = connection.responseCode
                if (code in 200..299) {
                    val body = connection.inputStream.bufferedReader().use { it.readText() }
                    val arr = JSONObject(body).getJSONArray("requests")
                    val list = mutableListOf<OrgRequest>()
                    for (i in 0 until arr.length()) {
                        val o = arr.getJSONObject(i)

                        // NEW: parse matched providers (present after "matched" status)
                        val matches = mutableListOf<OrgMatch>()
                        val matchesArr = o.optJSONArray("matches")
                        if (matchesArr != null) {
                            for (j in 0 until matchesArr.length()) {
                                val m = matchesArr.getJSONObject(j)
                                matches.add(
                                    OrgMatch(
                                        organizationId = m.optString("organization_id", ""),
                                        quantity = m.optInt("quantity", 0),
                                        etaHours = m.optInt("eta_hours", 0)
                                    )
                                )
                            }
                        }

                        list.add(
                            OrgRequest(
                                id = o.optString("id", ""),
                                type = o.optString("type", ""),
                                resource = o.optString("resource", ""),
                                quantity = o.optInt("quantity", 0),
                                status = o.optString("status", "pending"),
                                latitude = if (o.isNull("latitude")) null else o.optDouble("latitude"),
                                longitude = if (o.isNull("longitude")) null else o.optDouble("longitude"),
                                createdAt = o.optString("created_at", ""),
                                planId = if (o.isNull("plan_id")) null else o.optString("plan_id"),
                                totalMatched = if (o.isNull("total_matched")) null else o.optInt("total_matched"),
                                matches = matches
                            )
                        )
                    }
                    ApiResult.Success(list)
                } else {
                    ApiResult.Error("HTTP $code")
                }
            } catch (e: Exception) {
                ApiResult.Error(e.message ?: "Status fetch failed")
            } finally {
                connection?.disconnect()
            }
        }
    }

    // ───────────── MAPPINGS ─────────────

    private fun resourceName(code: String): String {
        return when (code) {
            "F" -> "food_kits"; "W" -> "water_kits"; "M" -> "medical_kits"
            "T" -> "tents"; "B" -> "blankets"; "H" -> "hygiene_kits"
            "D" -> "medical_teams"; else -> "unknown"
        }
    }

    private fun urgencyName(code: String): String {
        return when (code) {
            "L" -> "low"; "M" -> "medium"; "H" -> "high"; "C" -> "critical"; else -> "unknown"
        }
    }

    private fun locationName(code: String): String {
        return when (code) {
            "RA" -> "Region A"; "RB" -> "Region B"; "RC" -> "Region C"
            "D1" -> "District North"; "D2" -> "District South"; else -> code
        }
    }
}