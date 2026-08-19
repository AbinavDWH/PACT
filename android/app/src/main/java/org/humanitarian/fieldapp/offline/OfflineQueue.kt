package org.humanitarian.fieldapp.offline

import android.content.Context
import android.content.SharedPreferences
import org.humanitarian.fieldapp.models.FieldReport
import org.json.JSONArray
import org.json.JSONObject

data class QueuedReport(
    val report: FieldReport,
    val smsPayload: String
)

object OfflineQueue {
    private const val PREFS_NAME = "pact_offline_queue"
    private const val KEY_REPORTS = "pending_reports"

    private fun getPrefs(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun addReport(context: Context, report: FieldReport, smsPayload: String) {
        val prefs = getPrefs(context)
        val jsonArray = JSONArray(prefs.getString(KEY_REPORTS, "[]"))

        val jsonObj = JSONObject()
            .put("organizationId", report.organizationId)
            .put("locationCode", report.locationCode)
            .put("resourceCode", report.resourceCode)
            .put("quantity", report.quantity)
            .put("urgencyCode", report.urgencyCode)
            .put("notes", report.notes)
            .put("smsPayload", smsPayload)

        jsonArray.put(jsonObj)
        prefs.edit().putString(KEY_REPORTS, jsonArray.toString()).apply()
    }

    fun getQueuedReports(context: Context): List<QueuedReport> {
        val prefs = getPrefs(context)
        val jsonArray = JSONArray(prefs.getString(KEY_REPORTS, "[]"))
        val reports = mutableListOf<QueuedReport>()

        for (i in 0 until jsonArray.length()) {
            val obj = jsonArray.getJSONObject(i)
            val report = FieldReport(
                organizationId = obj.getString("organizationId"),
                locationCode = obj.getString("locationCode"),
                resourceCode = obj.getString("resourceCode"),
                quantity = obj.getInt("quantity"),
                urgencyCode = obj.getString("urgencyCode"),
                notes = obj.optString("notes", "")
            )
            val payload = obj.optString("smsPayload", "")
            reports.add(QueuedReport(report, payload))
        }
        return reports
    }

    // Rewrites the queue with only the given reports (used after partial sync)
    fun replaceQueue(context: Context, reports: List<QueuedReport>) {
        val prefs = getPrefs(context)
        val jsonArray = JSONArray()
        for (item in reports) {
            val jsonObj = JSONObject()
                .put("organizationId", item.report.organizationId)
                .put("locationCode", item.report.locationCode)
                .put("resourceCode", item.report.resourceCode)
                .put("quantity", item.report.quantity)
                .put("urgencyCode", item.report.urgencyCode)
                .put("notes", item.report.notes)
                .put("smsPayload", item.smsPayload)
            jsonArray.put(jsonObj)
        }
        prefs.edit().putString(KEY_REPORTS, jsonArray.toString()).apply()
    }

    fun clearQueue(context: Context) {
        getPrefs(context).edit().remove(KEY_REPORTS).apply()
    }

    fun getQueueSize(context: Context): Int {
        return getQueuedReports(context).size
    }
}