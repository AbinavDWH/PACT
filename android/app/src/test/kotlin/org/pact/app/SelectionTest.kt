package org.pact.app

import org.pact.codec.PactCodec
import org.pact.codec.Tables
import java.io.File
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

/**
 * The app's encoding contract, tested on the JVM.
 *
 * A plain unit test, not an instrumented one, so it runs with no device and no
 * emulator. That matters: without it the first proof that the chip screen
 * produces a payload the backend accepts would be a phone in someone's hand at
 * a demo, and the failure would look like "the app doesn't work".
 *
 * What this actually guards is the seam between [Selection.toCodecMap] and
 * `Payload.encode`. Both sides are individually correct; the risk is that the
 * UI passes display labels where the codec wants keys, or codes where it wants
 * labels, and the two disagree silently until the server rejects a real
 * emergency.
 */
class SelectionTest {

    // Bhopal, the coordinates used throughout the protocol docs.
    private val lat = 23.2599
    private val lon = 77.4126

    @BeforeTest
    fun loadTables() {
        // The same file the backend reads and the parity test checks. Not a
        // copy: if this path is wrong the test fails rather than passing
        // against stale tables.
        val shared = File("../../shared/codec/pact_tables.v1.json")
        assertTrue(shared.exists(), "shared tables not found at ${shared.absolutePath}")
        Tables.loadFromText(shared.readText())
    }

    private fun full() = Selection(
        situation = "5",          // building_collapse
        people = "2",             // 3-4
        injury = "2",             // serious_stable
        mobility = "3",           // trapped_in_debris
        urgency = "C",
        needs = setOf("water_kits", "medical_kits", "rescue_team"),
        vulnerabilities = setOf("child_under_5"),
    )

    // -----------------------------------------------------------------------
    // The seam
    // -----------------------------------------------------------------------

    @Test
    fun `a complete selection encodes to a frame the codec can read back`() {
        val sms = PactCodec.encodeRequest(full().toCodecMap(), lat, lon, "7F3K", 101)
        val decoded = PactCodec.decode(sms)

        assertEquals("accepted", decoded["status"], "decode rejected the app's own output: $decoded")
        @Suppress("UNCHECKED_CAST")
        val d = decoded["decoded"] as Map<String, Any?>
        assertEquals("seeker_request", d["type"])
        assertEquals("building_collapse", d["situation"])
        assertEquals("serious_stable", d["injury"])
        assertEquals("trapped_in_debris", d["mobility"])
        assertEquals("critical", d["urgency"])
    }

    @Test
    fun `needs survive the round trip as keys, not as display labels`() {
        val sms = PactCodec.encodeRequest(full().toCodecMap(), lat, lon, "7F3K", 101)
        @Suppress("UNCHECKED_CAST")
        val d = PactCodec.decode(sms)["decoded"] as Map<String, Any?>
        @Suppress("UNCHECKED_CAST")
        val needs = (d["needs"] as List<String>).toSet()
        assertEquals(setOf("water_kits", "medical_kits", "rescue_team"), needs)
    }

    @Test
    fun `vulnerabilities survive the round trip`() {
        val sms = PactCodec.encodeRequest(full().toCodecMap(), lat, lon, "7F3K", 101)
        @Suppress("UNCHECKED_CAST")
        val d = PactCodec.decode(sms)["decoded"] as Map<String, Any?>
        @Suppress("UNCHECKED_CAST")
        val v = (d["vulnerability"] as List<String>).toSet()
        assertEquals(setOf("child_under_5"), v)
    }

    @Test
    fun `position round trips to within GPS error`() {
        val sms = PactCodec.encodeRequest(full().toCodecMap(), lat, lon, "7F3K", 101)
        @Suppress("UNCHECKED_CAST")
        val d = PactCodec.decode(sms)["decoded"] as Map<String, Any?>
        val rlat = d["latitude"] as Double
        val rlon = d["longitude"] as Double
        // PACK10 resolves to ~1.1 m, well below civilian GPS error.
        assertTrue(kotlin.math.abs(rlat - lat) < 0.0001, "lat drifted: $rlat")
        assertTrue(kotlin.math.abs(rlon - lon) < 0.0001, "lon drifted: $rlon")
    }

    @Test
    fun `latitude and longitude are not transposed`() {
        val sms = PactCodec.encodeRequest(full().toCodecMap(), lat, lon, "7F3K", 101)
        @Suppress("UNCHECKED_CAST")
        val d = PactCodec.decode(sms)["decoded"] as Map<String, Any?>
        // Bhopal: longitude 77 is greater than latitude 23. A transposition
        // would still decode cleanly and put the request 6000 km away.
        assertTrue((d["longitude"] as Double) > (d["latitude"] as Double))
    }

    // -----------------------------------------------------------------------
    // Frame shape
    // -----------------------------------------------------------------------

    @Test
    fun `the frame is a Q message with the expected field count`() {
        val sms = PactCodec.encodeRequest(full().toCodecMap(), lat, lon, "7F3K", 101)
        val parts = sms.split("|")
        assertEquals(6, parts.size, "unexpected frame shape: $sms")
        assertEquals("Q", parts[0])
        assertEquals("101", parts[1])
        assertEquals("7F3K", parts[2])
        assertEquals(10, parts[3].length, "Q payload must be 10 chars")
        assertEquals(10, parts[4].length, "PACK10 geo token must be 10 chars")
    }

    @Test
    fun `the whole request fits one SMS segment`() {
        val sms = PactCodec.encodeRequest(full().toCodecMap(), lat, lon, "7F3K", 101)
        // The premise of the SMS fallback: one message, one segment, no
        // multipart reassembly on a flaky network.
        assertTrue(sms.length <= 160, "payload is ${sms.length} chars: $sms")
        assertTrue(org.pact.codec.SmsFrame.isGsm7Safe(sms), "payload is not GSM-7 safe: $sms")
    }

    @Test
    fun `a corrupted checksum is rejected rather than silently accepted`() {
        val sms = PactCodec.encodeRequest(full().toCodecMap(), lat, lon, "7F3K", 101)
        val broken = sms.dropLast(2) + "ZZ"
        assertEquals("error", PactCodec.decode(broken)["status"])
    }

    // -----------------------------------------------------------------------
    // Completeness gate
    // -----------------------------------------------------------------------

    @Test
    fun `an incomplete selection cannot be sent`() {
        assertTrue(!Selection().complete)
        assertTrue(!full().copy(needs = emptySet()).complete, "needs are required")
        assertTrue(!full().copy(situation = null).complete)
        assertTrue(!full().copy(injury = null).complete)
        assertTrue(full().complete)
    }

    @Test
    fun `vulnerabilities are optional`() {
        assertTrue(full().copy(vulnerabilities = emptySet()).complete)
    }

    @Test
    fun `encoding an incomplete selection fails loudly rather than sending rubbish`() {
        // The UI gates on `complete`, but a bug that got past it must throw
        // rather than emit a frame with a zero in a field that means something.
        assertFailsWith<Exception> {
            PactCodec.encodeRequest(Selection().toCodecMap(), lat, lon, "7F3K", 1)
        }
    }

    // -----------------------------------------------------------------------
    // Every chip the UI can offer is encodable
    // -----------------------------------------------------------------------

    @Test
    fun `every option the UI offers encodes successfully`() {
        // The chips are generated from the tables, so this is really asserting
        // that the generator and the encoder agree across the whole taxonomy
        // rather than only on the one example above.
        val base = full()
        for (s in Tables.codes("situation")) {
            PactCodec.encodeRequest(base.copy(situation = s.first).toCodecMap(),
                                    lat, lon, "7F3K", 1)
        }
        for (i in Tables.codes("injury")) {
            PactCodec.encodeRequest(base.copy(injury = i.first).toCodecMap(),
                                    lat, lon, "7F3K", 1)
        }
        for (m in Tables.codes("mobility")) {
            PactCodec.encodeRequest(base.copy(mobility = m.first).toCodecMap(),
                                    lat, lon, "7F3K", 1)
        }
        for (p in Tables.codes("people")) {
            PactCodec.encodeRequest(base.copy(people = p.first).toCodecMap(),
                                    lat, lon, "7F3K", 1)
        }
        for (u in Tables.codes("urgency")) {
            PactCodec.encodeRequest(base.copy(urgency = u.first).toCodecMap(),
                                    lat, lon, "7F3K", 1)
        }
        for (n in Tables.bitKeys("needs")) {
            PactCodec.encodeRequest(base.copy(needs = setOf(n.first)).toCodecMap(),
                                    lat, lon, "7F3K", 1)
        }
        for (v in Tables.bitKeys("vulnerability")) {
            PactCodec.encodeRequest(base.copy(vulnerabilities = setOf(v.first)).toCodecMap(),
                                    lat, lon, "7F3K", 1)
        }
    }

    @Test
    fun `selecting every need at once still fits one segment`() {
        val all = Tables.bitKeys("needs").map { it.first }.toSet()
        val sms = PactCodec.encodeRequest(full().copy(needs = all).toCodecMap(),
                                          lat, lon, "7F3K", 999)
        assertTrue(sms.length <= 160, "worst case is ${sms.length} chars: $sms")
        assertEquals("accepted", PactCodec.decode(sms)["status"])
    }
}
