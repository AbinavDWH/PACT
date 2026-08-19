package org.pact.codec

import java.io.File
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Cross-language parity.
 *
 * Reads the SAME shared/codec/vectors.json the Python pytest suite reads. If a
 * table edit or a rounding difference makes Kotlin disagree with Python by one
 * character, this fails immediately instead of producing an SMS the backend
 * rejects during the demo.
 */
class ParityTest {

    private val repoRoot = File(System.getProperty("user.dir")).let {
        generateSequence(it) { d -> d.parentFile }
            .first { d -> File(d, "shared/codec/vectors.json").exists() }
    }

    private val vectors: List<Json.Obj> by lazy {
        Tables.loadFrom(File(repoRoot, "shared/codec/pact_tables.v1.json").path)
        val root = Json.parse(File(repoRoot, "shared/codec/vectors.json").readText()) as Json.Obj
        (root["vectors"] as Json.Arr).items.map { it as Json.Obj }
    }

    @Suppress("UNCHECKED_CAST")
    private fun selection(v: Json.Obj): Map<String, Any?> =
        (v["selection"] as Json.Obj).map.mapValues { (_, x) ->
            when (x) {
                is Json.Arr -> x.items.map { it as String }
                is Double -> x.toLong()
                else -> x
            }
        }

    private fun encode(v: Json.Obj): String = when (v["kind"] as String) {
        "Q" -> PactCodec.encodeRequest(
            selection(v), v["lat"] as Double, v["lon"] as Double,
            v["uid"] as String, (v["seq"] as Double).toInt(),
            (v["accuracy_m"] as? Double))
        "G" -> PactCodec.encodeOffer(
            selection(v), v["uid"] as String, (v["seq"] as Double).toInt(),
            v["lat"] as? Double, v["lon"] as? Double, v["location_code"] as? String)
        "C" -> PactCodec.encodeAck(
            v["uid"] as String, (v["seq"] as Double).toInt(), v["ref"] as String,
            (v["state"] as Double).toInt(), (v["eta_bucket"] as Double).toInt())
        "S" -> PactCodec.encodeStatus(
            v["uid"] as String, (v["seq"] as Double).toInt(), v["ref"] as String,
            (v["status"] as Double).toInt())
        else -> error("unknown vector kind")
    }

    @Test
    fun `kotlin encodes every vector byte-identically to python`() {
        var checked = 0
        for (v in vectors) {
            val expected = v["expected_sms"] as String
            assertEquals(expected, encode(v), "vector ${v["name"]}")
            checked++
        }
        assertTrue(checked >= 11, "expected the full vector set, got $checked")
        println("parity OK: $checked vectors")
    }

    @Test
    fun `every vector is single-part and gsm7 safe`() {
        for (v in vectors) {
            val sms = v["expected_sms"] as String
            assertTrue(SmsFrame.isGsm7Safe(sms), "${v["name"]} would force UCS-2")
            assertTrue(sms.length <= 40, "${v["name"]} is ${sms.length} chars")
        }
    }

    @Test
    fun `Q vectors round-trip their coordinates`() {
        for (v in vectors.filter { it["kind"] == "Q" }) {
            @Suppress("UNCHECKED_CAST")
            val d = (PactCodec.decode(v["expected_sms"] as String)["decoded"]
                    as Map<String, Any?>)
            assertEquals(v["lat"] as Double, d["latitude"] as Double, 1e-5)
            assertEquals(v["lon"] as Double, d["longitude"] as Double, 1e-5)
        }
    }

    @Test
    fun `checksum matches the documented value`() {
        assertEquals("16", SmsFrame.xorChecksum("N|001|NGO01|RA|F|300|H"))
        assertEquals("7F", SmsFrame.xorChecksum("Q|001|7F3K|15223C03Q0|6QR6VFBQ33"))
    }

    @Test
    fun `bad checksum is rejected`() {
        val r = PactCodec.decode("Q|001|7F3K|15223C03Q0|6QR6VFBQ33|XX")
        assertEquals("error", r["status"])
        assertEquals("BAD_CRC", r["error"])
    }

    @Test
    fun `unknown selection char decodes partially and is still accepted`() {
        val body = "Q|001|7F3K|1Y223C03Q0|6QR6VFBQ33"
        val r = PactCodec.decode("$body|${SmsFrame.xorChecksum(body)}")
        assertEquals("accepted", r["status"])
        @Suppress("UNCHECKED_CAST")
        val d = r["decoded"] as Map<String, Any?>
        assertEquals(null, d["situation"])
        assertEquals(true, d["degraded"])
        assertEquals("critical", d["urgency"])
    }

    @Test
    fun `pack10 round trips at the coordinate extremes`() {
        for (pair in listOf(0.0 to 0.0, 23.25991 to 77.41263,
                            -89.99999 to -179.99999, 89.99999 to 179.99999)) {
            val p = GeoCodec.decode(GeoCodec.encode(pair.first, pair.second))!!
            assertEquals(pair.first, p.latitude, 1e-5)
            assertEquals(pair.second, p.longitude, 1e-5)
        }
    }
}
