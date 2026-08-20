package org.humanitarian.fieldapp.models

enum class RelayDirection {
    INBOUND,
    OUTBOUND
}

enum class RelayStatus {
    PENDING,
    FORWARDED_TO_SERVER,
    SENT_VIA_GSM,
    RECEIVED,
    FAILED
}

data class GatewayLogEntry(
    val id: String,
    val timestamp: Long = System.currentTimeMillis(),
    val direction: RelayDirection,
    val fromTo: String,
    val message: String,
    val status: RelayStatus,
    val details: String = ""
)

data class OutboundSmsMessage(
    val id: String,
    val toNumber: String,
    val message: String,
    val type: String,
    val planId: String? = null,
    val status: String,
    val createdAt: String
)

data class InboundSmsRecord(
    val id: String,
    val fromNumber: String,
    val message: String,
    val timestamp: Long
)

data class GatewayStats(
    val inboundCount: Int = 0,
    val outboundCount: Int = 0,
    val failedCount: Int = 0,
    val isRunning: Boolean = false
)
