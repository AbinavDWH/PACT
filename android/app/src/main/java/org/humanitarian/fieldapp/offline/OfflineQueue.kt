package org.humanitarian.fieldapp.offline

import android.content.Context
import android.content.SharedPreferences
import org.humanitarian.fieldapp.models.FieldReport
import org.json.JSONArray
import org.json.JSONObject

object OfflineQueue {
    private const val PREFS_NAME = "pact_offline_queue"
    private const val KEY_REPORTS = "pending_reports"

    private fun getPrefs(context: Context): SharedPreferences {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun addReport(context: Context, report: FieldReport) {
        val prefs = getPrefs(context)
        val jsonArray = JSONArray(prefs.getString(KEY_REPORTS, "[]"))
        
        val jsonObj = JSONObject()
            .put("organizationId", report.organizationId)
            .put("locationCode", report.locationCode)
            .put("resourceCode", report.resourceCode)
            .put("quantity", report.quantity)
            .put("urgencyCode", report.urgencyCode)
            .put("notes", report.notes)
            
        jsonArray.put(jsonObj)
        prefs.edit().putString(KEY_REPORTS, jsonArray.toString()).apply()
    }

    fun getPendingReports(context: Context): List<FieldReport> {
        val prefs = getPrefs(context)
        val jsonArray = JSONArray(prefs.getString(KEY_REPORTS, "[]"))
        val reports = mutableListOf<FieldReport>()
        
        for (i in 0 until jsonArray.length()) {
            val obj = jsonArray.getJSONObject(i)
            reports.add(
                FieldReport(
                    organizationId = obj.getString("organizationId"),
                    locationCode = obj.getString("locationCode"),
                    resourceCode = obj.getString("resourceCode"),
                    quantity = obj.getInt("quantity"),
                    urgencyCode = obj.getString("urgencyCode"),
                    notes = obj.optString("notes", "")
                )
            )
        }
        return reports
    }

    fun clearQueue(context: Context) {
        getPrefs(context).edit().remove(KEY_REPORTS).apply()
    }
    
    fun getQueueSize(context: Context): Int {
        return getPendingReports(context).size
    }
}