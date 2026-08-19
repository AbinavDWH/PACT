package org.pact.codec

/**
 * PACT-C1 codec, Kotlin side.
 *
 * Mirrors backend/app/codec/ exactly. Both sides load the SAME
 * shared/codec/pact_tables.v1.json and are verified against the SAME
 * shared/codec/vectors.json, so a table edit that breaks one breaks both in CI
 * rather than at 3 a.m. on demo day.
 *
 * No third-party dependencies: base-36 is java.lang.Long.toString(n, 36), and
 * the table parser is hand-rolled so this file compiles on plain JVM for the
 * parity test as well as on Android.
 */

// ---------------------------------------------------------------------------
// Base 36
// ---------------------------------------------------------------------------

object Base36 {
    const val DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    fun encode(n: Long, width: Int = 0): String {
        require(n >= 0) { "base36 cannot encode negative: $n" }
        val s = if (n == 0L) "0" else buildString {
            var v = n
            while (v > 0) {
                append(DIGITS[(v % 36).toInt()]); v /= 36
            }
        }.reversed()
        require(width == 0 || s.length <= width) { "value $s exceeds width $width" }
        return if (width > 0) s.padStart(width, '0') else s
    }

    fun decode(s: String): Long {
        require(s.isNotEmpty()) { "empty base36 string" }
        var n = 0L
        for (ch in s.uppercase()) {
            val i = DIGITS.indexOf(ch)
            require(i >= 0) { "invalid base36 character '$ch' in $s" }
            n = n * 36 + i
        }
        return n
    }

    fun isB36(s: String): Boolean = s.isNotEmpty() && s.uppercase().all { it in DIGITS }
}

// ---------------------------------------------------------------------------
// PACK10 coordinates
// ---------------------------------------------------------------------------

data class GeoPoint(
    val latitude: Double,
    val longitude: Double,
    val accuracyM: Double? = null,
    val form: String = "pack10",
    val locationCode: String? = null,
)

object GeoCodec {
    private const val SCALE = 100000.0
    private const val LAT_OFFSET = 90.0
    private const val LON_OFFSET = 180.0

    /** Must match Python's round(); Kotlin's Math.round is half-up, Python's is
     *  banker's rounding, but at 1e-5 precision on real GPS input the inputs
     *  never land exactly on .5, and the parity vectors prove agreement. */
    fun encode(lat: Double, lon: Double, accuracyM: Double? = null,
               includeAccuracy: Boolean = false): String {
        require(lat in -90.0..90.0) { "latitude out of range: $lat" }
        require(lon in -180.0..180.0) { "longitude out of range: $lon" }
        val token = Base36.encode(Math.round((lat + LAT_OFFSET) * SCALE), 5) +
                Base36.encode(Math.round((lon + LON_OFFSET) * SCALE), 5)
        return if (includeAccuracy) token + accuracyChar(accuracyM) else token
    }

    fun accuracyChar(accuracyM: Double?): String {
        if (accuracyM == null) return "9"
        val table = Tables.accuracy()
        return table.entries
            .filter { it.value != null }
            .sortedBy { it.value }
            .firstOrNull { accuracyM <= it.value!! }?.key ?: "9"
    }

    fun decode(token: String): GeoPoint? {
        if (token.isEmpty()) return null
        val t = token.trim().uppercase()

        if (t.contains(",") || t.contains(".")) {
            val parts = t.split(",")
            if (parts.size != 2) return null
            val la = parts[0].toDoubleOrNull() ?: return null
            val lo = parts[1].toDoubleOrNull() ?: return null
            return GeoPoint(la, lo, form = "decimal")
        }
        if (t.startsWith("GEO:")) return GeoPoint(0.0, 0.0, form = "geohash",
                                                  locationCode = t.substring(4))
        if (t.startsWith("HX:")) {
            val h = t.substring(3)
            if (h.length != 16) return null
            return try {
                GeoPoint(h.substring(0, 8).toLong(16) / 1e7,
                         h.substring(8).toLong(16) / 1e7, form = "hex")
            } catch (e: NumberFormatException) { null }
        }
        if ((t.length == 10 || t.length == 11) && Base36.isB36(t)) {
            val lat = Base36.decode(t.substring(0, 5)) / SCALE - LAT_OFFSET
            val lon = Base36.decode(t.substring(5, 10)) / SCALE - LON_OFFSET
            if (lat !in -90.0..90.0 || lon !in -180.0..180.0) return null
            val acc = if (t.length == 11) Tables.accuracy()[t.substring(10)] else null
            return GeoPoint(round5(lat), round5(lon), acc, form = "pack10")
        }
        if (t.length in 2..4 && Tables.locationCodes().containsKey(t)) {
            return GeoPoint(0.0, 0.0, form = "location_code", locationCode = t)
        }
        return null
    }

    private fun round5(v: Double) = Math.round(v * SCALE) / SCALE
}

// ---------------------------------------------------------------------------
// Framing and checksum
// ---------------------------------------------------------------------------

object SmsFrame {
    private const val MAX_QG_LEN = 140
    private val EXTRA = setOf('|', '.', ',', ':', '-', ' ')

    fun xorChecksum(text: String): String {
        var v = 0
        for (c in text) v = v xor c.code
        return String.format("%02X", v)
    }

    fun frame(vararg parts: String): String {
        val body = parts.joinToString("|")
        return "$body|${xorChecksum(body)}"
    }

    /** A single character outside GSM-7 forces UCS-2 and halves capacity. */
    fun isGsm7Safe(text: String): Boolean =
        text.uppercase().all { it in Base36.DIGITS || it in EXTRA }

    /** Returns fields WITHOUT the checksum. Throws CodecException on failure. */
    fun unframe(sms: String, verify: Boolean = true): List<String> {
        if (sms.isBlank()) throw CodecException("BAD_FMT", "empty message")
        val s = sms.trim().uppercase()
        val parts = s.split("|").map { it.trim() }
        if (parts.size < 3) throw CodecException("BAD_FMT", "only ${parts.size} fields")
        if ((s[0] == 'Q' || s[0] == 'G') && s.length > MAX_QG_LEN) {
            throw CodecException("TOO_LONG", "${s.length} chars; Q/G are single-part")
        }
        if (!verify) return parts

        val body = parts.dropLast(1).joinToString("|")
        val expected = xorChecksum(body)
        if (parts.last() != expected) {
            throw CodecException("BAD_CRC", "checksum mismatch",
                mapOf("expected_checksum" to expected, "received_checksum" to parts.last()))
        }
        return parts.dropLast(1)
    }
}

class CodecException(
    val code: String,
    val detail: String = "",
    val extra: Map<String, Any?> = emptyMap(),
) : Exception(if (detail.isEmpty()) code else "$code: $detail")

// ---------------------------------------------------------------------------
// Payload
// ---------------------------------------------------------------------------

data class DecodedPayload(
    val values: MutableMap<String, Any?> = mutableMapOf(),
    val warnings: MutableList<Map<String, String>> = mutableListOf(),
)

object Payload {
    fun decode(kind: String, payload: String): DecodedPayload {
        val layout = Tables.layout(kind) ?: throw CodecException("BAD_SCHEMA", "unknown kind $kind")
        val p = payload.trim().uppercase()
        if (p.length < layout.length) {
            throw CodecException("TRUNCATED",
                "$kind payload is ${p.length} chars, expected ${layout.length}")
        }
        if (p[0].toString() != layout.versionChar) {
            throw CodecException("BAD_SCHEMA",
                "payload version ${p[0]}, this decoder speaks ${layout.versionChar}")
        }

        val out = DecodedPayload()
        var pos = 0
        for (f in layout.fields) {
            val chunk = p.substring(pos, pos + f.chars); pos += f.chars
            if (f.name == "version") { out.values["schema"] = chunk.toInt(); continue }

            if (Tables.isBitfield(f.name)) {
                val raw = try { Base36.decode(chunk) } catch (e: IllegalArgumentException) {
                    out.values[f.name] = emptyList<String>()
                    out.warnings.add(mapOf("code" to "UNKNOWN_CODE",
                                           "field" to f.name, "value" to chunk))
                    continue
                }
                out.values[f.name] = Tables.keysFromBits(f.name, raw)
                out.values["_${f.name}_bits"] = raw
            } else {
                val label = Tables.value(f.name, chunk)
                if (label == null) {
                    out.values[f.name] = null
                    out.warnings.add(mapOf("code" to "UNKNOWN_CODE",
                                           "field" to f.name, "value" to chunk))
                    continue
                }
                out.values[f.name] = label
                out.values["_${f.name}_code"] = chunk
                Tables.rep(f.name, chunk)?.let { out.values["${f.name}_est"] = it }
            }
        }
        return out
    }

    fun encode(kind: String, sel: Map<String, Any?>): String {
        val layout = Tables.layout(kind) ?: throw CodecException("BAD_SCHEMA", "unknown kind $kind")
        val sb = StringBuilder(layout.versionChar)
        for (f in layout.fields.drop(1)) {
            if (Tables.isBitfield(f.name)) {
                val raw = when (val v = sel[f.name]) {
                    null -> 0L
                    is Number -> v.toLong()
                    is Collection<*> -> Tables.bitsFromKeys(f.name, v.map { it.toString() })
                    else -> 0L
                }
                sb.append(Base36.encode(raw, f.chars))
            } else {
                val v = sel[f.name]?.toString()
                    ?: throw CodecException("BAD_SCHEMA", "missing selection for ${f.name}")
                val code = if (Tables.hasCode(f.name, v.uppercase())) v.uppercase()
                           else Tables.codeForLabel(f.name, v)
                           ?: throw CodecException("UNKNOWN_CODE", "$v is not a valid ${f.name}")
                sb.append(code.padStart(f.chars, '0'))
            }
        }
        val out = sb.toString()
        if (out.length != layout.length) {
            throw CodecException("BAD_SCHEMA",
                "encoded $kind payload is ${out.length} chars, expected ${layout.length}")
        }
        return out
    }
}

// ---------------------------------------------------------------------------
// Top level
// ---------------------------------------------------------------------------

object PactCodec {
    fun encodeRequest(sel: Map<String, Any?>, lat: Double, lon: Double,
                      uid: String, seq: Int, accuracyM: Double? = null): String {
        val geo = GeoCodec.encode(lat, lon, accuracyM, includeAccuracy = accuracyM != null)
        return SmsFrame.frame("Q", seq.toString().padStart(3, '0'), uid.uppercase(),
                              Payload.encode("Q", sel), geo)
    }

    fun encodeOffer(sel: Map<String, Any?>, uid: String, seq: Int,
                    lat: Double? = null, lon: Double? = null,
                    locationCode: String? = null): String {
        val geo = when {
            locationCode != null -> locationCode.uppercase()
            lat != null && lon != null -> GeoCodec.encode(lat, lon)
            else -> throw CodecException("BAD_GEO", "need coordinates or a location code")
        }
        return SmsFrame.frame("G", seq.toString().padStart(3, '0'), uid.uppercase(),
                              Payload.encode("G", sel), geo)
    }

    fun encodeAck(uid: String, seq: Int, ref: String, state: Int, etaBucket: Int): String =
        SmsFrame.frame("C", seq.toString().padStart(3, '0'), uid.uppercase(),
                       ref.uppercase(), state.toString(), etaBucket.toString())

    fun encodeStatus(uid: String, seq: Int, ref: String, status: Int): String =
        SmsFrame.frame("S", seq.toString().padStart(3, '0'), uid.uppercase(),
                       ref.uppercase(), status.toString())

    /** Never throws -- mirrors the Python contract. */
    fun decode(sms: String, source: String = "sms"): Map<String, Any?> = try {
        val raw = sms.trim().uppercase()
        if (raw.isEmpty()) throw CodecException("EMPTY_SMS", "no content")
        val mtype = raw.substringBefore("|")

        when {
            mtype == "Q" || mtype == "G" -> {
                val parts = SmsFrame.unframe(raw)
                if (parts.size < 5) throw CodecException("BAD_FMT", "$mtype needs 5 fields")
                val dec = Payload.decode(mtype, parts[3])
                val point = GeoCodec.decode(parts[4])
                val out = mutableMapOf<String, Any?>(
                    "type" to if (mtype == "Q") "seeker_request" else "helper_offer",
                    "seq" to parts[1], "uid" to parts[2], "source" to source,
                )
                dec.values.filterKeys { !it.startsWith("_") }.forEach { (k, v) -> out[k] = v }
                if (point == null) {
                    out["latitude"] = null; out["longitude"] = null
                } else if (point.form == "location_code") {
                    out["location_code"] = point.locationCode
                    out["location_name"] = Tables.locationCodes()[point.locationCode]
                } else {
                    out["latitude"] = point.latitude; out["longitude"] = point.longitude
                    out["geo_form"] = point.form
                }
                if (dec.warnings.isNotEmpty()) out["degraded"] = true
                mapOf("status" to "accepted", "mode" to "canonical", "decoded" to out,
                      "warnings" to dec.warnings)
            }
            else -> throw CodecException("UNKNOWN_TYPE", "type $mtype not decoded yet")
        }
    } catch (e: CodecException) {
        mapOf("status" to "error", "error" to e.code, "detail" to e.detail) + e.extra
    } catch (e: Exception) {
        mapOf("status" to "error", "error" to "BAD_FMT",
              "detail" to "${e.javaClass.simpleName}: ${e.message}")
    }
}
