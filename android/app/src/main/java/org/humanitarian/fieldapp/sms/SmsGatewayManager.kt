package org.humanitarian.fieldapp.sms

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.telephony.SmsManager
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.humanitarian.fieldapp.models.GatewayLogEntry
import org.humanitarian.fieldapp.models.GatewayStats
import org.humanitarian.fieldapp.models.OutboundSmsMessage
import org.humanitarian.fieldapp.models.RelayDirection
import org.humanitarian.fieldapp.models.RelayStatus
import org.humanitarian.fieldapp.network.ApiClient
import org.humanitarian.fieldapp.network.ApiResult
import org.json.JSONObject
import java.util.UUID

object SmsGatewayManager {

    private val gatewayScope = CoroutineScope(Dispatchers.IO)
    private var pollerJob: Job? = null

    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning.asStateFlow()

    private val _logs = MutableStateFlow<List<GatewayLogEntry>>(emptyList())
    val logs: StateFlow<List<GatewayLogEntry>> = _logs.asStateFlow()

    private val _stats = MutableStateFlow(GatewayStats())
    val stats: StateFlow<GatewayStats> = _stats.asStateFlow()

    private val _outboundQueue = MutableStateFlow<List<OutboundSmsMessage>>(emptyList())
    val outboundQueue: StateFlow<List<OutboundSmsMessage>> = _outboundQueue.asStateFlow()

    private var inboundCount = 0
    private var outboundCount = 0
    private var failedCount = 0

    // ──────────────────────── START / STOP GATEWAY ────────────────────────

    fun startGateway(context: Context) {
        if (_isRunning.value) return
        _isRunning.value = true
        updateStats()

        addLog(
            direction = RelayDirection.INBOUND,
            fromTo = "System",
            message = "Mobile SMS Gateway started. Listening for incoming SMS and polling backend outbox...",
            status = RelayStatus.RECEIVED,
            details = "Gateway active"
        )

        val appContext = context.applicationContext

        // Start background polling loop for outbound SMS from server
        pollerJob?.cancel()
        pollerJob = gatewayScope.launch {
            while (isActive && _isRunning.value) {
                try {
                    pollAndSendOutboundSms(appContext)
                } catch (t: Throwable) {
                    t.printStackTrace()
                }
                delay(4000) // Poll every 4 seconds
            }
        }
    }

    fun stopGateway() {
        _isRunning.value = false
        pollerJob?.cancel()
        pollerJob = null
        updateStats()

        addLog(
            direction = RelayDirection.OUTBOUND,
            fromTo = "System",
            message = "Mobile SMS Gateway paused by administrator.",
            status = RelayStatus.PENDING,
            details = "Gateway stopped"
        )
    }

    fun toggleGateway(context: Context) {
        if (_isRunning.value) stopGateway() else startGateway(context)
    }

    // ──────────────────────── INBOUND RELAY (Phone -> Server) ────────────────────────

    suspend fun processInboundSms(context: Context, fromNumber: String, messageText: String): Boolean {
        return try {
            val trimmed = messageText.trim()
            if (trimmed.isEmpty()) return false

            addLog(
                direction = RelayDirection.INBOUND,
                fromTo = fromNumber,
                message = trimmed,
                status = RelayStatus.RECEIVED,
                details = "Received via Mobile SIM"
            )

            inboundCount++
            updateStats()

            // Forward to backend SMS webhook
            when (val result = ApiClient.postSmsWebhook(trimmed, fromNumber)) {
                is ApiResult.Success -> {
                    val respText = result.data
                    val hubId = try {
                        val json = JSONObject(respText)
                        val accepted = json.optBoolean("accepted", true)
                        val id = json.optString("hub_request_id", "")
                        if (accepted && id.isNotBlank()) {
                            org.humanitarian.fieldapp.offline.LocalRequestStore.markAccepted(context.applicationContext, "", id)
                        } else if (!accepted) {
                            val reason = json.optString("auto_reject_reason", "Validation failed")
                            org.humanitarian.fieldapp.offline.LocalRequestStore.markRejected(context.applicationContext, "", id, reason)
                        }
                        id
                    } catch (e: Exception) { "" }

                    addLog(
                        direction = RelayDirection.INBOUND,
                        fromTo = fromNumber,
                        message = trimmed,
                        status = RelayStatus.FORWARDED_TO_SERVER,
                        details = if (hubId.isNotBlank()) "Relayed to server -> $hubId" else "Relayed to server successfully"
                    )
                    true
                }
                is ApiResult.Error -> {
                    failedCount++
                    updateStats()
                    addLog(
                        direction = RelayDirection.INBOUND,
                        fromTo = fromNumber,
                        message = trimmed,
                        status = RelayStatus.FAILED,
                        details = "Forward failed: ${result.message}"
                    )
                    false
                }
            }
        } catch (t: Throwable) {
            t.printStackTrace()
            false
        }
    }

    // ──────────────────────── OUTBOUND RELAY (Server -> Mobile -> GSM SMS) ────────────────────────

    suspend fun pollAndSendOutboundSms(context: Context): Int {
        return try {
            when (val result = ApiClient.getPendingOutboundSms()) {
                is ApiResult.Success -> {
                    val pendingList = result.data
                    _outboundQueue.value = pendingList

                    if (pendingList.isEmpty()) return 0

                    var sentCount = 0
                    for (item in pendingList) {
                        val success = sendRealGsmSms(context, item.toNumber, item.message)
                        if (success) {
                            sentCount++
                            outboundCount++
                            updateStats()

                            // Acknowledge with backend
                            try { ApiClient.ackOutboundSms(item.id, "sent") } catch (t: Throwable) { t.printStackTrace() }

                            addLog(
                                direction = RelayDirection.OUTBOUND,
                                fromTo = item.toNumber,
                                message = item.message,
                                status = RelayStatus.SENT_VIA_GSM,
                                details = "Dispatched via Mobile SIM (${item.type})"
                            )
                        } else {
                            failedCount++
                            updateStats()

                            try { ApiClient.ackOutboundSms(item.id, "failed", "GSM transmission error") } catch (t: Throwable) { t.printStackTrace() }

                            addLog(
                                direction = RelayDirection.OUTBOUND,
                                fromTo = item.toNumber,
                                message = item.message,
                                status = RelayStatus.FAILED,
                                details = "GSM send failure (check permissions / SIM)"
                            )
                        }
                    }
                    sentCount
                }
                is ApiResult.Error -> {
                    0
                }
            }
        } catch (t: Throwable) {
            t.printStackTrace()
            0
        }
    }

    // ──────────────────────── REAL GSM SMS TRANSMISSION ────────────────────────

    fun sendRealGsmSms(context: Context, toNumber: String, messageText: String): Boolean {
        val cleanNumber = toNumber.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").trim()
        if (cleanNumber.isBlank() || messageText.isBlank()) return false

        // Check SEND_SMS runtime permission first
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            return false
        }

        return try {
            val smsManager: SmsManager? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                try {
                    context.getSystemService(SmsManager::class.java)
                } catch (t: Throwable) {
                    @Suppress("DEPRECATION")
                    SmsManager.getDefault()
                }
            } else {
                @Suppress("DEPRECATION")
                SmsManager.getDefault()
            }

            if (smsManager == null) return false

            val parts = smsManager.divideMessage(messageText)
            if (parts != null && parts.size > 1) {
                smsManager.sendMultipartTextMessage(cleanNumber, null, parts, null, null)
            } else {
                smsManager.sendTextMessage(cleanNumber, null, messageText, null, null)
            }
            true
        } catch (t: Throwable) {
            t.printStackTrace()
            false
        }
    }

    // ──────────────────────── MANUAL TEST ACTIONS ────────────────────────

    fun sendManualOutboundSms(context: Context, toNumber: String, messageText: String, onResult: (Boolean, String) -> Unit) {
        val appContext = context.applicationContext
        gatewayScope.launch {
            val success = sendRealGsmSms(appContext, toNumber, messageText)
            if (success) {
                outboundCount++
                updateStats()
                addLog(
                    direction = RelayDirection.OUTBOUND,
                    fromTo = toNumber,
                    message = messageText,
                    status = RelayStatus.SENT_VIA_GSM,
                    details = "Manual test sent via SIM"
                )
                try { ApiClient.queueOutboundSms(toNumber, messageText, "manual_test") } catch (t: Throwable) { t.printStackTrace() }
                withContext(Dispatchers.Main) {
                    onResult(true, "SMS successfully transmitted via device SIM!")
                }
            } else {
                failedCount++
                updateStats()
                addLog(
                    direction = RelayDirection.OUTBOUND,
                    fromTo = toNumber,
                    message = messageText,
                    status = RelayStatus.FAILED,
                    details = "Manual test failed (check SIM / permissions)"
                )
                withContext(Dispatchers.Main) {
                    onResult(false, "Failed to transmit SMS. Verify SIM card & SMS permissions.")
                }
            }
        }
    }

    fun simulateInboundSms(context: Context, fromNumber: String, payload: String, onResult: (Boolean, String) -> Unit) {
        val appContext = context.applicationContext
        gatewayScope.launch {
            val success = processInboundSms(appContext, fromNumber, payload)
            withContext(Dispatchers.Main) {
                if (success) {
                    onResult(true, "Simulated SMS received & forwarded to server successfully!")
                } else {
                    onResult(false, "Failed to forward simulated SMS to backend server.")
                }
            }
        }
    }

    fun clearLogs() {
        _logs.value = emptyList()
        inboundCount = 0
        outboundCount = 0
        failedCount = 0
        updateStats()
    }

    private fun addLog(direction: RelayDirection, fromTo: String, message: String, status: RelayStatus, details: String) {
        val entry = GatewayLogEntry(
            id = UUID.randomUUID().toString().take(8),
            timestamp = System.currentTimeMillis(),
            direction = direction,
            fromTo = fromTo,
            message = message,
            status = status,
            details = details
        )
        _logs.value = listOf(entry) + _logs.value.take(199)
    }

    private fun updateStats() {
        _stats.value = GatewayStats(
            inboundCount = inboundCount,
            outboundCount = outboundCount,
            failedCount = failedCount,
            isRunning = _isRunning.value
        )
    }
}
