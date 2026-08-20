package org.humanitarian.fieldapp.models

data class OrgMatch(
    val organizationId: String,
    val quantity: Int,
    val etaHours: Int
)

data class OrgRequest(
    val id: String,
    val type: String,
    val resource: String,
    val quantity: Int,
    val status: String,
    val latitude: Double?,
    val longitude: Double?,
    val locationCode: String? = null,
    val createdAt: String,
    // NEW: allocation result fields
    val planId: String? = null,
    val totalMatched: Int? = null,
    val matches: List<OrgMatch> = emptyList()
)