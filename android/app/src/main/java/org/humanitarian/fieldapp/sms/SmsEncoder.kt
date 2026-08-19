package org.humanitarian.fieldapp.sms

import android.content.Context
import org.humanitarian.fieldapp.models.FieldReport
import java.util.Locale

object SmsEncoder {

    private const val PREFS_NAME = "pact_sms_seq"
    private const val KEY_SEQ = "next_sequence"

    /** Persistent sequence number (001, 002, ...) — sms.md section 25 */
    fun nextSequence(context: Context, organizationId: String): String {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val seq = prefs.getInt(KEY_SEQ, 1)
        prefs.edit().putInt(KEY_SEQ, seq + 1).apply()
        return String.format(Locale.US, "%03d", seq)
    }

    /**
     * Canonical need SMS — sms.md section 11:
     * N|SEQ|ORG|LOC|RESOURCE|QTY|URGENCY|CRC
     *
     * LOC = real GPS coordinates ("lat,lng", 4 decimals) when the device
     * has a GPS lock — otherwise falls back to the location code.
     */
    fun encodeNeed(report: FieldReport, seq: String): String {
        val loc = if (hasRealGps(report)) {
            // sms.md section 10: decimal coordinates, max 4 places, lat first
            String.format(Locale.US, "%.4f,%.4f", report.latitude!!, report.longitude!!)
        } else {
            report.locationCode
        }

        val body = listOf(
            "N",
            seq,
            report.organizationId,
            loc,
            report.resourceCode,
            report.quantity.toString(),
            report.urgencyCode
        ).joinToString("|")

        return "$body|${xorChecksum(body)}"
    }

    /** True only when the device has a real GPS lock (not 0,0) */
    private fun hasRealGps(report: FieldReport): Boolean {
        val lat = report.latitude
        val lng = report.longitude
        return lat != null && lng != null && (lat != 0.0 || lng != 0.0)
    }

    /** XOR checksum — sms.md section 24 */
    private fun xorChecksum(text: String): String {
        var value = 0
        for (c in text) value = value xor c.code
        return String.format(Locale.US, "%02X", value)
    }
}