package org.humanitarian.fieldapp.models

data class FieldReport(
    val organizationId: String,
    val locationCode: String,
    val resourceCode: String,
    val quantity: Int,
    val urgencyCode: String,
    val notes: String = "",
    val latitude: Double? = null,
    val longitude: Double? = null
)