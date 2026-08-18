package org.humanitarian.fieldapp.sms

import android.content.Context
import org.humanitarian.fieldapp.models.FieldReport

object SmsEncoder {

    private const val PREFS_NAME = "pact_sms"

    fun nextSequence(
        context: Context,
        organizationId: String
    ): String {
        val safeOrganizationId = organizationId
            .trim()
            .uppercase()
            .ifBlank { "UNKNOWN" }

        val prefs = context.getSharedPreferences(
            PREFS_NAME,
            Context.MODE_PRIVATE
        )

        val key = "sms_seq_$safeOrganizationId"
        val current = prefs.getInt(key, 1)

        val formatted = current.toString().padStart(3, '0')

        val next = if (current >= 999) {
            1
        } else {
            current + 1
        }

        prefs.edit()
            .putInt(key, next)
            .apply()

        return formatted
    }

    fun encodeNeed(
        report: FieldReport,
        seq: String
    ): String {
        val organization = report.organizationId
            .trim()
            .uppercase()
            .replace("|", "")
            .ifBlank { "NGO01" }

        val location = locationCode(report.locationCode)
        val resource = resourceCode(report.resourceCode)
        val urgency = urgencyCode(report.urgencyCode)

        val body = listOf(
            "N",
            seq,
            organization,
            location,
            resource,
            report.quantity.toString(),
            urgency
        ).joinToString("|")

        val checksum = xorChecksum(body)

        return "$body|$checksum"
    }
}