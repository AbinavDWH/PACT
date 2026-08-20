package org.humanitarian.fieldapp.offline

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import org.humanitarian.fieldapp.models.FieldReport
import org.json.JSONArray
import org.json.JSONObject

data class LocalRequestItem(
    val id: String,
    val seq: String,
    val organizationId: String,
    val locationCode: String,
    val resource: String,
    val resourceCode: String,
    val quantity: Int,
    val urgency: String,
    val rawPayload: String,
    val channel: String,
    val status: String, // "WAITING FOR RESPONSE", "ACCEPTED", "ALLOCATED", "REJECTED", "DELIVERED"
    val planId: String? = null,
    val allocatedOrg: String? = null,
    val allocatedQty: Int? = null,
    val etaHours: Int? = null,
    val rejectReason: String? = null,
    val createdAt: Long = System.currentTimeMillis(),
    val updatedAt: Long = System.currentTimeMillis()
)

object LocalRequestStore {

    private const val PREFS_NAME = "pact_local_requests"
    private const val KEY_REQUESTS = "requests_list"

    private val _requestsFlow = MutableStateFlow<List<LocalRequestItem>>(emptyList())
    val requestsFlow: StateFlow<List<LocalRequestItem>> = _requestsFlow.asStateFlow()

    private fun getPrefs(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    private val resourceNameMap = mapOf(
        "F" to "Food kits",
        "W" to "Water kits",
        "M" to "Medical kits",
        "T" to "Tents",
        "B" to "Blankets",
        "H" to "Hygiene kits",
        "D" to "Medical teams",
        "U" to "Relief supplies"
    )

    private val urgencyNameMap = mapOf(
        "L" to "Low",
        "M" to "Medium",
        "H" to "High",
        "C" to "Critical"
    )

    fun init(context: Context) {
        try {
            _requestsFlow.value = list(context)
        } catch (t: Throwable) {
            t.printStackTrace()
            _requestsFlow.value = emptyList()
        }
    }

    fun addOrUpdateNeed(
        context: Context,
        report: FieldReport,
        seq: String,
        smsPayload: String,
        channel: String = "SMS",
        initialStatus: String = "WAITING FOR RESPONSE"
    ): LocalRequestItem {
        try {
            val currentList = list(context).toMutableList()
            val generatedId = "SMS-REQ-$seq"

            // Check if item with this seq already exists
            val existingIndex = currentList.indexOfFirst { it.seq == seq || it.id == generatedId }
            val resName = resourceNameMap[report.resourceCode.uppercase()] ?: report.resourceCode
            val urgName = urgencyNameMap[report.urgencyCode.uppercase()] ?: report.urgencyCode

            val item = LocalRequestItem(
                id = generatedId,
                seq = seq,
                organizationId = report.organizationId.uppercase(),
                locationCode = if (report.latitude != null && report.longitude != null && report.latitude != 0.0) {
                    "${report.latitude},${report.longitude}"
                } else {
                    report.locationCode
                },
                resource = resName,
                resourceCode = report.resourceCode.uppercase(),
                quantity = report.quantity,
                urgency = urgName,
                rawPayload = smsPayload,
                channel = channel,
                status = initialStatus,
                createdAt = System.currentTimeMillis(),
                updatedAt = System.currentTimeMillis()
            )

            if (existingIndex >= 0) {
                currentList[existingIndex] = item
            } else {
                currentList.add(0, item)
            }

            saveList(context, currentList)
            return item
        } catch (t: Throwable) {
            t.printStackTrace()
            return LocalRequestItem(
                id = "SMS-REQ-$seq",
                seq = seq,
                organizationId = report.organizationId,
                locationCode = report.locationCode,
                resource = report.resourceCode,
                resourceCode = report.resourceCode,
                quantity = report.quantity,
                urgency = report.urgencyCode,
                rawPayload = smsPayload,
                channel = channel,
                status = initialStatus
            )
        }
    }

    fun markAccepted(context: Context, seq: String, serverReqId: String) {
        try {
            val currentList = list(context).toMutableList()
            if (currentList.isEmpty()) return

            val cleanSeq = seq.filter { it.isDigit() }
            val cleanReqId = serverReqId.filter { it.isDigit() }

            // 1. Try exact match or numeric ID match
            var targetIndex = currentList.indexOfFirst { item ->
                val itemNum = item.id.filter { it.isDigit() }
                item.seq == seq || item.id.equals(serverReqId, ignoreCase = true) ||
                (cleanSeq.isNotEmpty() && itemNum == cleanSeq) ||
                (cleanReqId.isNotEmpty() && itemNum == cleanReqId)
            }

            // 2. If no exact match, fallback to the most recent WAITING request
            if (targetIndex < 0) {
                targetIndex = currentList.indexOfFirst { it.status.contains("WAITING") }
            }

            if (targetIndex >= 0) {
                val item = currentList[targetIndex]
                currentList[targetIndex] = item.copy(
                    id = if (serverReqId.isNotBlank()) serverReqId else item.id,
                    status = "ACCEPTED",
                    updatedAt = System.currentTimeMillis()
                )
                saveList(context, currentList)
            }
        } catch (t: Throwable) {
            t.printStackTrace()
        }
    }

    fun markAllocated(
        context: Context,
        seq: String,
        planId: String,
        allocatedOrg: String,
        resourceCode: String,
        allocatedQty: Int,
        etaHours: Int
    ) {
        try {
            val currentList = list(context).toMutableList()
            if (currentList.isEmpty()) return

            val cleanSeq = seq.filter { it.isDigit() }
            val targetRes = resourceCode.uppercase()

            // 1. Try exact match by planId, seq, or resource with WAITING/ACCEPTED state
            var targetIndex = currentList.indexOfFirst { item ->
                item.planId == planId ||
                (item.seq == seq && item.status != "ALLOCATED" && item.status != "DELIVERED") ||
                (cleanSeq.isNotEmpty() && item.id.filter { it.isDigit() } == cleanSeq && item.status != "ALLOCATED")
            }

            // 2. Try matching by resource type among pending requests
            if (targetIndex < 0 && targetRes.isNotBlank()) {
                targetIndex = currentList.indexOfFirst { item ->
                    item.resourceCode == targetRes &&
                    (item.status.contains("WAITING") || item.status == "ACCEPTED")
                }
            }

            // 3. Fallback to most recent waiting or accepted request
            if (targetIndex < 0) {
                targetIndex = currentList.indexOfFirst {
                    it.status.contains("WAITING") || it.status == "ACCEPTED"
                }
            }

            if (targetIndex >= 0) {
                val item = currentList[targetIndex]
                currentList[targetIndex] = item.copy(
                    status = "ALLOCATED",
                    planId = if (planId.isNotBlank()) planId else (item.planId ?: "PLAN-101"),
                    allocatedOrg = if (allocatedOrg.isNotBlank()) allocatedOrg else "Provider",
                    allocatedQty = if (allocatedQty > 0) allocatedQty else item.quantity,
                    etaHours = if (etaHours > 0) etaHours else 4,
                    updatedAt = System.currentTimeMillis()
                )
                saveList(context, currentList)
            }
        } catch (t: Throwable) {
            t.printStackTrace()
        }
    }

    fun markRejected(context: Context, seq: String, serverReqId: String, reason: String = "Rejected by coordinator") {
        try {
            val currentList = list(context).toMutableList()
            if (currentList.isEmpty()) return

            val cleanSeq = seq.filter { it.isDigit() }
            val cleanReqId = serverReqId.filter { it.isDigit() }

            // 1. Try exact match or numeric match
            var targetIndex = currentList.indexOfFirst { item ->
                val itemNum = item.id.filter { it.isDigit() }
                item.seq == seq || item.id.equals(serverReqId, ignoreCase = true) ||
                (cleanSeq.isNotEmpty() && itemNum == cleanSeq) ||
                (cleanReqId.isNotEmpty() && itemNum == cleanReqId)
            }

            // 2. Fallback to first waiting request
            if (targetIndex < 0) {
                targetIndex = currentList.indexOfFirst { it.status.contains("WAITING") }
            }

            if (targetIndex >= 0) {
                val item = currentList[targetIndex]
                currentList[targetIndex] = item.copy(
                    id = if (serverReqId.isNotBlank()) serverReqId else item.id,
                    status = "REJECTED",
                    rejectReason = reason,
                    updatedAt = System.currentTimeMillis()
                )
                saveList(context, currentList)
            }
        } catch (t: Throwable) {
            t.printStackTrace()
        }
    }

    fun markStatus(context: Context, planId: String, statusCode: String) {
        try {
            val currentList = list(context).toMutableList()
            val statusLabel = when (statusCode) {
                "1" -> "ACCEPTED"
                "2" -> "EN ROUTE"
                "3" -> "DELIVERED"
                "4" -> "CANCELLED"
                else -> "COMPLETED"
            }

            var updated = false
            for (i in currentList.indices) {
                val item = currentList[i]
                if (item.planId == planId) {
                    currentList[i] = item.copy(
                        status = statusLabel,
                        updatedAt = System.currentTimeMillis()
                    )
                    updated = true
                    break
                }
            }

            if (updated) {
                saveList(context, currentList)
            }
        } catch (t: Throwable) {
            t.printStackTrace()
        }
    }

    fun list(context: Context): List<LocalRequestItem> {
        return try {
            val prefs = getPrefs(context)
            val jsonStr = prefs.getString(KEY_REQUESTS, "[]") ?: "[]"
            val arr = JSONArray(jsonStr)
            val result = mutableListOf<LocalRequestItem>()

            for (i in 0 until arr.length()) {
                val obj = arr.getJSONObject(i)
                result.add(
                    LocalRequestItem(
                        id = obj.optString("id", "SMS-REQ-000"),
                        seq = obj.optString("seq", "000"),
                        organizationId = obj.optString("organizationId", "NGO01"),
                        locationCode = obj.optString("locationCode", "RA"),
                        resource = obj.optString("resource", "Relief Supplies"),
                        resourceCode = obj.optString("resourceCode", "F"),
                        quantity = obj.optInt("quantity", 0),
                        urgency = obj.optString("urgency", "High"),
                        rawPayload = obj.optString("rawPayload", ""),
                        channel = obj.optString("channel", "SMS"),
                        status = obj.optString("status", "WAITING FOR RESPONSE"),
                        planId = if (obj.has("planId") && !obj.isNull("planId")) obj.optString("planId", "") else null,
                        allocatedOrg = if (obj.has("allocatedOrg") && !obj.isNull("allocatedOrg")) obj.optString("allocatedOrg", "") else null,
                        allocatedQty = if (obj.has("allocatedQty") && !obj.isNull("allocatedQty")) obj.optInt("allocatedQty", 0) else null,
                        etaHours = if (obj.has("etaHours") && !obj.isNull("etaHours")) obj.optInt("etaHours", 4) else null,
                        rejectReason = if (obj.has("rejectReason") && !obj.isNull("rejectReason")) obj.optString("rejectReason", "") else null,
                        createdAt = obj.optLong("createdAt", System.currentTimeMillis()),
                        updatedAt = obj.optLong("updatedAt", System.currentTimeMillis())
                    )
                )
            }

            result.sortedByDescending { it.createdAt }
        } catch (t: Throwable) {
            t.printStackTrace()
            emptyList()
        }
    }

    private fun saveList(context: Context, items: List<LocalRequestItem>) {
        try {
            val arr = JSONArray()
            for (item in items) {
                val obj = JSONObject()
                    .put("id", item.id)
                    .put("seq", item.seq)
                    .put("organizationId", item.organizationId)
                    .put("locationCode", item.locationCode)
                    .put("resource", item.resource)
                    .put("resourceCode", item.resourceCode)
                    .put("quantity", item.quantity)
                    .put("urgency", item.urgency)
                    .put("rawPayload", item.rawPayload)
                    .put("channel", item.channel)
                    .put("status", item.status)
                    .put("planId", item.planId ?: JSONObject.NULL)
                    .put("allocatedOrg", item.allocatedOrg ?: JSONObject.NULL)
                    .put("allocatedQty", item.allocatedQty ?: JSONObject.NULL)
                    .put("etaHours", item.etaHours ?: JSONObject.NULL)
                    .put("rejectReason", item.rejectReason ?: JSONObject.NULL)
                    .put("createdAt", item.createdAt)
                    .put("updatedAt", item.updatedAt)
                arr.put(obj)
            }

            getPrefs(context).edit().putString(KEY_REQUESTS, arr.toString()).apply()
            _requestsFlow.value = items.sortedByDescending { it.createdAt }
        } catch (t: Throwable) {
            t.printStackTrace()
        }
    }
}
