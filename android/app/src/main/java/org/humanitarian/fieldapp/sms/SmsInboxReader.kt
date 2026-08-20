package org.humanitarian.fieldapp.sms

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Telephony
import androidx.core.content.ContextCompat
import org.humanitarian.fieldapp.models.InboundSmsRecord

object SmsInboxReader {

    fun readRecentSms(context: Context, limit: Int = 25): List<InboundSmsRecord> {
        val list = mutableListOf<InboundSmsRecord>()
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_SMS) != PackageManager.PERMISSION_GRANTED) {
            return list
        }

        try {
            val uri: Uri = Telephony.Sms.Inbox.CONTENT_URI
            val projection = arrayOf(
                Telephony.Sms._ID,
                Telephony.Sms.ADDRESS,
                Telephony.Sms.BODY,
                Telephony.Sms.DATE
            )
            val cursor = context.contentResolver.query(
                uri,
                projection,
                null,
                null,
                "${Telephony.Sms.DATE} DESC LIMIT $limit"
            )
            cursor?.use {
                val idIdx = it.getColumnIndex(Telephony.Sms._ID)
                val addressIdx = it.getColumnIndex(Telephony.Sms.ADDRESS)
                val bodyIdx = it.getColumnIndex(Telephony.Sms.BODY)
                val dateIdx = it.getColumnIndex(Telephony.Sms.DATE)

                while (it.moveToNext()) {
                    val id = if (idIdx != -1) it.getString(idIdx) ?: "" else ""
                    val address = if (addressIdx != -1) it.getString(addressIdx) ?: "Unknown" else "Unknown"
                    val body = if (bodyIdx != -1) it.getString(bodyIdx) ?: "" else ""
                    val date = if (dateIdx != -1) it.getLong(dateIdx) else System.currentTimeMillis()

                    if (body.isNotBlank()) {
                        list.add(
                            InboundSmsRecord(
                                id = id,
                                fromNumber = address,
                                message = body,
                                timestamp = date
                            )
                        )
                    }
                }
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        return list
    }
}
