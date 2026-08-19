package org.humanitarian.fieldapp.sms

import android.content.Context

object StatusSmsBuilder {

    private const val PREFS_NAME = "pact_status_seq"

    // Status codes from sms.md section 8
    val statusOptions = listOf(
        "0" to "Assigned",
        "1" to "Dispatched",
        "2" to "In transit",
        "3" to "Delivered",
        "4" to "Blocked",
        "5" to "Cancelled"
    )

    // XOR checksum (matches sms.md section 24 and the decoder)
    private fun xorChecksum(text: String): String {
        var value = 0
        for (ch in text) {
            value = value xor ch.code
        }
        return "%02X".format(value)
    }

    // Per-organization sequence counter to avoid duplicates
    fun nextSequence(context: Context, organizationId: String): Int {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val key = "seq_${organizationId.uppercase()}"
        val next = prefs.getInt(key, 0) + 1
        prefs.edit().putInt(key, next).apply()
        return next
    }

    // Canonical status SMS: S|SEQ|PLAN|STATUS|CRC
    fun encodeStatus(seq: Int, planId: String, statusCode: String): String {
        val seqText = seq.toString().padStart(3, '0')
        val body = "S|$seqText|${planId.trim().uppercase()}|${statusCode.trim()}"
        val crc = xorChecksum(body)
        return "$body|$crc"
    }

    // Human-readable preview (matches decoder output style)
    fun humanMessage(planId: String, statusCode: String): String {
        val statusName = statusOptions.firstOrNull { it.first == statusCode }?.second ?: statusCode
        return "Plan ${planId.trim().uppercase()} status updated to: $statusName."
    }
}