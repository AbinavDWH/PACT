package org.humanitarian.fieldapp.models

data class MapMarker(
    val id: String,
    val type: String,
    val latitude: Double,
    val longitude: Double,
    val severity: Int,
    val data: String
)