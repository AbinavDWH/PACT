package org.humanitarian.fieldapp.sms

import org.json.JSONObject
import java.util.LinkedHashMap

object SmsDecoder {

    data class DecodedSms(
        val valid: Boolean,
        val typeLabel: String,
        val typeCode: String,
        val message: String,                       // Human-readable sentence
        val fields: LinkedHashMap<String, String>,
        val json: String,
        val checksumValid: Boolean,
        val error: String
    )

    // ---- JSON / code maps (used for structured output) ----
    private val locationNames = mapOf(
        "RA" to "Region A", "RB" to "Region B", "RC" to "Region C",
        "D1" to "District North", "D2" to "District South"
    )
    private val resourceNames = mapOf(
        "F" to "food_kits", "W" to "water_kits", "M" to "medical_kits",
        "T" to "tents", "B" to "blankets", "H" to "hygiene_kits",
        "D" to "medical_teams", "U" to "unknown"
    )
    private val urgencyNames = mapOf("L" to "low", "M" to "medium", "H" to "high", "C" to "critical")
    private val statusNames = mapOf(
        "0" to "assigned", "1" to "dispatched", "2" to "in_transit",
        "3" to "delivered", "4" to "blocked", "5" to "cancelled"
    )
    private val availabilityNames = mapOf("A" to "available", "L" to "limited", "U" to "unavailable")
    private val markerTypeNames = mapOf(
        "CR" to "crisis", "ND" to "need_reported", "RS" to "resource_point",
        "DL" to "delivery_location", "BL" to "blocked_route", "SH" to "shelter", "MD" to "medical_point"
    )
    private val legacyResourceMap = mapOf(
        "food" to "F", "water" to "W", "medical" to "M", "medicine" to "M",
        "tents" to "T", "tent" to "T", "blankets" to "B", "blanket" to "B"
    )

    // ---- Human-readable display maps (used for the decoded message) ----
    private val resourceDisplay = mapOf(
        "F" to "food kits", "W" to "water kits", "M" to "medical kits",
        "T" to "tents", "B" to "blankets", "H" to "hygiene kits",
        "D" to "medical teams", "U" to "unknown supplies"
    )
    private val urgencyDisplay = mapOf("L" to "Low", "M" to "Medium", "H" to "High", "C" to "Critical")
    private val statusDisplay = mapOf(
        "0" to "Assigned", "1" to "Dispatched", "2" to "In transit",
        "3" to "Delivered", "4" to "Blocked", "5" to "Cancelled"
    )
    private val availabilityDisplay = mapOf("A" to "available", "L" to "limited", "U" to "unavailable")
    private val markerTypeDisplay = mapOf(
        "CR" to "Crisis zone", "ND" to "Need reported", "RS" to "Resource point",
        "DL" to "Delivery location", "BL" to "Blocked route", "SH" to "Shelter", "MD" to "Medical point"
    )

    fun decode(raw: String): DecodedSms {
        val message = raw.trim()
        if (message.isEmpty()) return errorResult("Empty message")
        val parts = message.split("|")
        if (parts.size < 2) return errorResult("Invalid format: too few fields")
        return when (parts[0].trim().uppercase()) {
            "N" -> decodeNeed(parts, message)
            "R" -> decodeResource(parts, message)
            "A" -> decodeAllocation(parts, message)
            "S" -> decodeStatus(parts, message)
            "M" -> decodeMarker(parts, message)
            else -> errorResult("Unknown message type: ${parts[0]}")
        }
    }

    private fun xorChecksum(text: String): String {
        var value = 0
        for (ch in text) value = value xor ch.code
        return "%02X".format(value)
    }

    private fun checksumOk(fullMessage: String, providedCrc: String): Boolean {
        val body = fullMessage.substringBeforeLast("|")
        return xorChecksum(body).equals(providedCrc.trim(), ignoreCase = true)
    }

    private fun pretty(json: JSONObject): String = json.toString(2)

    private fun errorResult(msg: String): DecodedSms {
        return DecodedSms(false, "Error", "", "", LinkedHashMap(), "", false, msg)
    }

    // Turn marker DATA like "F300;W150" into "300 food kits, 150 water kits"
    private fun markerDataToText(data: String): String {
        if (data.isBlank()) return ""
        return data.split(";").mapNotNull { item ->
            val t = item.trim()
            if (t.length < 2) return@mapNotNull null
            val code = t[0].uppercaseChar().toString()
            val qty = t.substring(1)
            val name = resourceDisplay[code] ?: code
            "$qty $name"
        }.joinToString(", ")
    }

    // N|SEQ|ORG|LOC|RES|QTY|URG|CRC  (canonical, 8) or N|ORG|Loc|res|QTY|URG (legacy, 6)
    private fun decodeNeed(parts: List<String>, message: String): DecodedSms {
        val fields = LinkedHashMap<String, String>()
        val json = JSONObject()
        json.put("type", "need"); json.put("source", "sms")

        if (parts.size == 8) {
            if (!checksumOk(message, parts[7])) {
                return errorResult("Checksum failed (expected ${xorChecksum(message.substringBeforeLast("|"))}, got ${parts[7]})")
            }
            val seq = parts[1]; val org = parts[2]; val loc = parts[3].trim()
            val res = parts[4].uppercase(); val qty = parts[5]; val urg = parts[6].uppercase()
            fields["Sequence"] = seq; fields["Organization"] = org

            val locationDisplay = if (loc.contains(",")) {
                fields["Coordinates"] = loc
                val coords = loc.split(",")
                json.put("latitude", coords.getOrNull(0)?.toDoubleOrNull() ?: 0.0)
                json.put("longitude", coords.getOrNull(1)?.toDoubleOrNull() ?: 0.0)
                "coordinates $loc"
            } else {
                val locUpper = loc.uppercase()
                fields["Location Code"] = locUpper; fields["Location Name"] = locationNames[locUpper] ?: locUpper
                json.put("location_code", locUpper); json.put("location_name", locationNames[locUpper] ?: locUpper)
                locationNames[locUpper] ?: locUpper
            }

            fields["Resource"] = resourceNames[res] ?: res; fields["Quantity"] = qty
            fields["Urgency"] = urgencyNames[urg] ?: urg; fields["Checksum"] = parts[7]
            json.put("seq", seq); json.put("organization_id", org)
            json.put("resource", resourceNames[res] ?: res)
            json.put("quantity", qty.toIntOrNull() ?: 0)
            json.put("urgency", urgencyNames[urg] ?: urg); json.put("checksum", parts[7])

            val human = "$org needs $qty ${resourceDisplay[res] ?: res} at $locationDisplay. " +
                "Urgency: ${urgencyDisplay[urg] ?: urg}."
            return DecodedSms(true, "Need Request", "N", human, fields, pretty(json), true, "")
        } else if (parts.size == 6) {
            val org = parts[1]; val locName = parts[2]; val resWord = parts[3].lowercase()
            val qty = parts[4]; val urg = parts[5].uppercase()
            val resCode = legacyResourceMap[resWord] ?: resWord.uppercase()
            fields["Organization"] = org; fields["Location"] = locName
            fields["Resource"] = resourceNames[resCode] ?: resWord; fields["Quantity"] = qty
            fields["Urgency"] = urgencyNames[urg] ?: urg; fields["Mode"] = "legacy"
            json.put("organization_id", org); json.put("location_name", locName)
            json.put("resource", resourceNames[resCode] ?: resWord)
            json.put("quantity", qty.toIntOrNull() ?: 0)
            json.put("urgency", urgencyNames[urg] ?: urg); json.put("mode", "legacy")

            val human = "$org needs $qty ${resourceDisplay[resCode] ?: resWord} in $locName. " +
                "Urgency: ${urgencyDisplay[urg] ?: urg}."
            return DecodedSms(true, "Need Request (Legacy)", "N", human, fields, pretty(json), true, "")
        }
        return errorResult("Need message must have 8 (canonical) or 6 (legacy) fields, got ${parts.size}")
    }

    // R|SEQ|ORG|LOC|RES|QTY|STATUS|CRC (8)
    private fun decodeResource(parts: List<String>, message: String): DecodedSms {
        if (parts.size != 8) return errorResult("Resource message must have 8 fields, got ${parts.size}")
        if (!checksumOk(message, parts[7])) return errorResult("Checksum failed")
        val fields = LinkedHashMap<String, String>()
        val json = JSONObject()
        json.put("type", "resource"); json.put("source", "sms")
        val seq = parts[1]; val org = parts[2]; val loc = parts[3].uppercase()
        val res = parts[4].uppercase(); val qty = parts[5]; val status = parts[6].uppercase()
        fields["Sequence"] = seq; fields["Organization"] = org
        fields["Location Code"] = loc; fields["Location Name"] = locationNames[loc] ?: loc
        fields["Resource"] = resourceNames[res] ?: res; fields["Quantity"] = qty
        fields["Status"] = availabilityNames[status] ?: status; fields["Checksum"] = parts[7]
        json.put("seq", seq); json.put("organization_id", org)
        json.put("location_code", loc); json.put("location_name", locationNames[loc] ?: loc)
        json.put("resource", resourceNames[res] ?: res)
        json.put("quantity", qty.toIntOrNull() ?: 0)
        json.put("status", availabilityNames[status] ?: status); json.put("checksum", parts[7])

        val human = "$org reports $qty ${resourceDisplay[res] ?: res} " +
            "${availabilityDisplay[status] ?: status} in ${locationNames[loc] ?: loc}."
        return DecodedSms(true, "Resource Availability", "R", human, fields, pretty(json), true, "")
    }

    // A|SEQ|PLAN|ORG|RES|QTY|LOC|ETA|CRC (9)
    private fun decodeAllocation(parts: List<String>, message: String): DecodedSms {
        if (parts.size != 9) return errorResult("Allocation message must have 9 fields, got ${parts.size}")
        if (!checksumOk(message, parts[8])) return errorResult("Checksum failed")
        val fields = LinkedHashMap<String, String>()
        val json = JSONObject()
        json.put("type", "allocation"); json.put("source", "sms")
        val seq = parts[1]; val plan = parts[2]; val org = parts[3]
        val res = parts[4].uppercase(); val qty = parts[5]; val loc = parts[6].uppercase(); val eta = parts[7]
        fields["Sequence"] = seq; fields["Plan ID"] = plan; fields["Organization"] = org
        fields["Resource"] = resourceNames[res] ?: res; fields["Quantity"] = qty
        fields["Destination Code"] = loc; fields["Destination Name"] = locationNames[loc] ?: loc
        fields["ETA (hours)"] = eta; fields["Checksum"] = parts[8]
        json.put("seq", seq); json.put("plan_id", plan); json.put("organization_id", org)
        json.put("resource", resourceNames[res] ?: res)
        json.put("quantity", qty.toIntOrNull() ?: 0)
        json.put("destination_code", loc); json.put("destination_name", locationNames[loc] ?: loc)
        json.put("eta_hours", eta.toIntOrNull() ?: 0); json.put("checksum", parts[8])

        val human = "Plan $plan assigns $org to deliver $qty ${resourceDisplay[res] ?: res} " +
            "to ${locationNames[loc] ?: loc}. ETA: $eta hours."
        return DecodedSms(true, "Allocation / Plan Assignment", "A", human, fields, pretty(json), true, "")
    }

    // S|SEQ|PLAN|STATUS|CRC (5) or S|SEQ|LOC|RES|QTY|STATUS|CRC (7)
    private fun decodeStatus(parts: List<String>, message: String): DecodedSms {
        if (!checksumOk(message, parts[parts.size - 1])) return errorResult("Checksum failed")
        val fields = LinkedHashMap<String, String>()
        val json = JSONObject()
        json.put("type", "status"); json.put("source", "sms")
        val human: String
        when (parts.size) {
            5 -> {
                val seq = parts[1]; val plan = parts[2]; val status = parts[3]
                fields["Sequence"] = seq; fields["Plan ID"] = plan
                fields["Status"] = statusNames[status] ?: status; fields["Checksum"] = parts[4]
                json.put("seq", seq); json.put("plan_id", plan)
                json.put("status", statusNames[status] ?: status); json.put("checksum", parts[4])
                human = "Plan $plan is now: ${statusDisplay[status] ?: status}."
            }
            7 -> {
                val seq = parts[1]; val loc = parts[2].uppercase(); val res = parts[3].uppercase()
                val qty = parts[4]; val status = parts[5]
                fields["Sequence"] = seq; fields["Location Code"] = loc
                fields["Location Name"] = locationNames[loc] ?: loc
                fields["Resource"] = resourceNames[res] ?: res; fields["Quantity"] = qty
                fields["Status"] = statusNames[status] ?: status; fields["Checksum"] = parts[6]
                json.put("seq", seq); json.put("location_code", loc)
                json.put("location_name", locationNames[loc] ?: loc)
                json.put("resource", resourceNames[res] ?: res)
                json.put("quantity", qty.toIntOrNull() ?: 0)
                json.put("status", statusNames[status] ?: status); json.put("checksum", parts[6])
                human = "Delivery in ${locationNames[loc] ?: loc}: $qty ${resourceDisplay[res] ?: res} " +
                    "is ${statusDisplay[status] ?: status}."
            }
            else -> return errorResult("Status message must have 5 or 7 fields, got ${parts.size}")
        }
        return DecodedSms(true, "Status Update", "S", human, fields, pretty(json), true, "")
    }

    // M|SEQ|LOC|MARKER_TYPE|SEVERITY|DATA|CRC (7)
    private fun decodeMarker(parts: List<String>, message: String): DecodedSms {
        if (parts.size != 7) return errorResult("Marker message must have 7 fields, got ${parts.size}")
        if (!checksumOk(message, parts[6])) return errorResult("Checksum failed")
        val fields = LinkedHashMap<String, String>()
        val json = JSONObject()
        json.put("type", "marker"); json.put("source", "sms")
        val seq = parts[1]; val loc = parts[2]; val mtype = parts[3].uppercase()
        val sev = parts[4]; val data = parts[5]
        fields["Sequence"] = seq

        val locUpper = loc.uppercase()
        val locationDescription: String
        if (locationNames.containsKey(locUpper)) {
            locationDescription = locationNames[locUpper]!!
            fields["Location Code"] = locUpper; fields["Location Name"] = locationNames[locUpper]!!
            json.put("location_code", locUpper); json.put("location_name", locationNames[locUpper])
        } else if (loc.contains(",")) {
            locationDescription = "coordinates $loc"
            val coords = loc.split(",")
            fields["Coordinates"] = loc
            json.put("latitude", coords.getOrNull(0)?.toDoubleOrNull() ?: 0.0)
            json.put("longitude", coords.getOrNull(1)?.toDoubleOrNull() ?: 0.0)
        } else {
            locationDescription = loc
            fields["Location"] = loc; json.put("location", loc)
        }

        fields["Marker Type"] = markerTypeNames[mtype] ?: mtype
        fields["Severity"] = sev; fields["Data"] = data; fields["Checksum"] = parts[6]
        json.put("seq", seq); json.put("marker_type", markerTypeNames[mtype] ?: mtype)
        json.put("severity", sev.toIntOrNull() ?: 0); json.put("data", data)
        json.put("checksum", parts[6])

        val supplyText = markerDataToText(data)
        val human = buildString {
            append("${markerTypeDisplay[mtype] ?: mtype} reported in $locationDescription. Severity $sev.")
            if (supplyText.isNotBlank()) append(" Supplies: $supplyText.")
        }
        return DecodedSms(true, "Map Marker", "M", human, fields, pretty(json), true, "")
    }
}