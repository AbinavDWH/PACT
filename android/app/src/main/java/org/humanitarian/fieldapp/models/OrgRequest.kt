package org.humanitarian.fieldapp.models

data class OrgRequest(
    val id: String,
    val type: String,
    val resource: String,
    val quantity: Int,
    val status: String,
    val latitude: Double?,
    val longitude: Double?,
    val createdAt: String
)