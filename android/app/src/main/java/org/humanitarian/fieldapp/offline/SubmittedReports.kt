package org.humanitarian.fieldapp.offline

import android.content.Context
import android.content.SharedPreferences
import org.humanitarian.fieldapp.models.FieldReport
import org.json.JSONArray
import org.json.JSONObject

data class SubmittedReport(
    val report: FieldReport,
    val needId: String,
    val submittedAt: Long
)

object SubmittedReports {
    private const val PREFS_NAME = "pact_submitted_reports"
    private const val KEY = "submitted_reports"
    private const val MAX_RECENT = 50

    private fun prefs(context: Context): SharedPreferences =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun add(context: Context, report: FieldReport, needId: String) {
        val arr = JSONArray(prefs(context).getString(KEY, "[]"))
        val obj = JSONObject()
            .put("organizationId", report.organizationId)
            .put("locationCode", report.locationCode)
            .put("resourceCode", report.resourceCode)
            .put("quantity", report.quantity)
            .put("urgencyCode", report.urgencyCode)
            .put("notes", report.notes)
            .put("needId", needId)
            .put("submittedAt", System.currentTimeMillis())
        arr.put(obj)
        // Keep only the most recent MAX_RECENT
        val trimmed = JSONArray()
        val start = (arr.length() - MAX_RECENT).coerceAtLeast(0)
        for (i in start until arr.length()) trimmed.put(arr.get(i))
        prefs(context).edit().putString(KEY, trimmed.toString()).apply()
    }

    fun list(context: Context): List<SubmittedReport> {
        val arr = JSONArray(prefs(context).getString(KEY, "[]"))
        val out = mutableListOf<SubmittedReport>()
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            out.add(
                SubmittedReport(
                    report = FieldReport(
                        organizationId = o.getString("organizationId"),
                        locationCode = o.getString("locationCode"),
                        resourceCode = o.getString("resourceCode"),
                        quantity = o.getInt("quantity"),
                        urgencyCode = o.getString("urgencyCode"),
                        notes = o.optString("notes", "")
                    ),
                    needId = o.getString("needId"),
                    submittedAt = o.getLong("submittedAt")
                )
            )
        }
        return out.sortedByDescending { it.submittedAt }
    }

    fun clear(context: Context) {
        prefs(context).edit().remove(KEY).apply()
    }
}