package org.humanitarian.fieldapp.sms

private val validLocationCodes = setOf(
    "RA",
    "RB",
    "RC",
    "D1",
    "D2"
)

private val validResourceCodes = setOf(
    "F",
    "W",
    "M",
    "T",
    "B",
    "H",
    "D",
    "U"
)

private val validUrgencyCodes = setOf(
    "L",
    "M",
    "H",
    "C"
)

fun locationCode(value: String): String {
    val cleaned = value.trim().uppercase()

    return when {
        cleaned in validLocationCodes -> cleaned
        cleaned == "REGION A" -> "RA"
        cleaned == "REGION B" -> "RB"
        cleaned == "REGION C" -> "RC"
        cleaned == "DISTRICT NORTH" -> "D1"
        cleaned == "DISTRICT SOUTH" -> "D2"
        else -> cleaned.take(8).ifBlank { "RA" }
    }
}

fun resourceCode(value: String): String {
    val cleaned = value.trim().uppercase()

    return when {
        cleaned in validResourceCodes -> cleaned
        cleaned == "FOOD" -> "F"
        cleaned == "FOOD KITS" -> "F"
        cleaned == "FOOD_KITS" -> "F"
        cleaned == "WATER" -> "W"
        cleaned == "WATER KITS" -> "W"
        cleaned == "WATER_KITS" -> "W"
        cleaned == "MEDICAL" -> "M"
        cleaned == "MEDICAL KITS" -> "M"
        cleaned == "MEDICAL_KITS" -> "M"
        cleaned == "TENTS" -> "T"
        cleaned == "TENT" -> "T"
        cleaned == "BLANKETS" -> "B"
        cleaned == "BLANKET" -> "B"
        cleaned == "HYGIENE" -> "H"
        cleaned == "HYGIENE KITS" -> "H"
        cleaned == "HYGIENE_KITS" -> "H"
        cleaned == "MEDICAL TEAMS" -> "D"
        cleaned == "MEDICAL_TEAMS" -> "D"
        cleaned == "UNKNOWN" -> "U"
        else -> "U"
    }
}

fun urgencyCode(value: String): String {
    val cleaned = value.trim().uppercase()

    return when {
        cleaned in validUrgencyCodes -> cleaned
        cleaned == "LOW" -> "L"
        cleaned == "MEDIUM" -> "M"
        cleaned == "HIGH" -> "H"
        cleaned == "CRITICAL" -> "C"
        else -> "M"
    }
}