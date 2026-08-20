package org.humanitarian.fieldapp.sms

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

class SmsBroadcastReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Telephony.Sms.Intents.SMS_RECEIVED_ACTION) {
            try {
                val messages = Telephony.Sms.Intents.getMessagesFromIntent(intent)
                if (!messages.isNullOrEmpty()) {
                    val fullBody = StringBuilder()
                    var sender = ""

                    for (sms in messages) {
                        if (sms != null) {
                            if (sender.isEmpty()) {
                                sender = sms.displayOriginatingAddress
                                    ?: sms.originatingAddress
                                    ?: "Unknown-SIM"
                            }
                            fullBody.append(sms.displayMessageBody ?: sms.messageBody ?: "")
                        }
                    }

                    val rawText = fullBody.toString().trim()
                    if (rawText.isNotEmpty()) {
                        val appContext = context.applicationContext

                        // Extract PACT payload if prefix exists
                        val index = listOf("C|", "A|", "S|", "X|", "N|", "R|", "M|")
                            .map { rawText.indexOf(it) }
                            .filter { it >= 0 }
                            .minOrNull() ?: 0
                        val messageText = rawText.substring(index).trim()

                        // 1. Check if incoming SMS is a response/update to our local requests
                        val parts = messageText.split("|")
                        if (parts.size >= 4) {
                            val type = parts[0].uppercase()
                            var toastMsg: String? = null

                            when (type) {
                                "C" -> {
                                    // Confirmation: C|SEQ|REQ_ID|STATUS|CRC (or C|SEQ|REQ_ID|REJECTED|REASON|CRC)
                                    val seq = parts.getOrNull(1) ?: ""
                                    val reqId = parts.getOrNull(2) ?: ""
                                    val status = parts.getOrNull(3)?.uppercase() ?: "OK"
                                    if (status == "REJECTED") {
                                        val reason = parts.getOrNull(4) ?: "Rejected by coordinator"
                                        org.humanitarian.fieldapp.offline.LocalRequestStore.markRejected(appContext, seq, reqId, reason)
                                        toastMsg = "Request REJECTED: $reason"
                                    } else {
                                        org.humanitarian.fieldapp.offline.LocalRequestStore.markAccepted(appContext, seq, reqId)
                                        toastMsg = "Request ACCEPTED by Gateway"
                                    }
                                }
                                "X" -> {
                                    // Rejection SMS: X|SEQ|REQ_ID|REASON|CRC
                                    val seq = parts.getOrNull(1) ?: ""
                                    val reqId = parts.getOrNull(2) ?: ""
                                    val reason = parts.getOrNull(3) ?: "Rejected by coordinator"
                                    org.humanitarian.fieldapp.offline.LocalRequestStore.markRejected(appContext, seq, reqId, reason)
                                    toastMsg = "Request REJECTED: $reason"
                                }
                                "A" -> {
                                    // Allocation: A|SEQ|PLAN_ID|ORG|RESOURCE|QTY|LOC|ETA|CRC
                                    val seq = parts.getOrNull(1) ?: ""
                                    val planId = parts.getOrNull(2) ?: ""
                                    val orgId = parts.getOrNull(3) ?: ""
                                    val resource = parts.getOrNull(4) ?: ""
                                    val qty = parts.getOrNull(5)?.toIntOrNull() ?: 0
                                    val eta = parts.getOrNull(7)?.toIntOrNull() ?: 4
                                    org.humanitarian.fieldapp.offline.LocalRequestStore.markAllocated(
                                        context = appContext,
                                        seq = seq,
                                        planId = planId,
                                        allocatedOrg = orgId,
                                        resourceCode = resource,
                                        allocatedQty = qty,
                                        etaHours = eta
                                    )
                                    toastMsg = "Request ALLOCATED ($planId from $orgId)"
                                }
                                "S" -> {
                                    // Status: S|SEQ|PLAN_ID|STATUS_CODE|CRC
                                    val planId = parts.getOrNull(2) ?: ""
                                    val statusCode = parts.getOrNull(3) ?: ""
                                    org.humanitarian.fieldapp.offline.LocalRequestStore.markStatus(appContext, planId, statusCode)
                                    toastMsg = "Plan $planId updated"
                                }
                            }

                            if (toastMsg != null) {
                                CoroutineScope(Dispatchers.Main).launch {
                                    try {
                                        android.widget.Toast.makeText(appContext, "PACT SMS: $toastMsg", android.widget.Toast.LENGTH_LONG).show()
                                    } catch (t: Throwable) {
                                        t.printStackTrace()
                                    }
                                }
                            }
                        }

                        // 2. Forward automatically to Mobile Gateway engine
                        CoroutineScope(Dispatchers.IO).launch {
                            SmsGatewayManager.processInboundSms(context, sender, messageText)
                        }
                    }
                }
            } catch (e: Exception) {
                e.printStackTrace()
            }
        }
    }
}
