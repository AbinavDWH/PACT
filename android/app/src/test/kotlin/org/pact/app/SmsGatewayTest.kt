package org.pact.app

import org.pact.codec.PactCodec
import org.pact.codec.Tables
import java.io.File
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * The gateway's message filter.
 *
 * A phone acting as the SMS gateway still receives everything else that phone
 * receives: banking OTPs, delivery codes, private messages from family. This
 * filter is the only thing standing between those and an HTTP POST to a
 * server, so most of these tests assert **refusal** rather than acceptance.
 *
 * The asymmetry is deliberate. Wrongly ignoring a real request costs one retry
 * from an app that already retries. Wrongly forwarding someone's OTP is
 * irreversible, and would be a worse privacy failure than anything this
 * project defends against.
 */
class SmsGatewayTest {

    @BeforeTest
    fun loadTables() {
        val shared = File("../../shared/codec/pact_tables.v1.json")
        assertTrue(shared.exists(), "shared tables not found at ${shared.absolutePath}")
        Tables.loadFromText(shared.readText())
    }

    private fun realFrame(): String = PactCodec.encodeRequest(
        Selection(
            situation = "5", people = "2", injury = "2", mobility = "3",
            urgency = "C", needs = setOf("water_kits"), vulnerabilities = emptySet(),
        ).toCodecMap(),
        13.008, 80.006, "7F3K", 101,
    )

    // -----------------------------------------------------------------------
    // Accepts what it must
    // -----------------------------------------------------------------------

    @Test
    fun `a real encoded request is forwarded`() {
        assertTrue(SmsGateway.looksLikePact(realFrame()))
    }

    @Test
    fun `surrounding whitespace does not stop a real frame`() {
        assertTrue(SmsGateway.looksLikePact("  ${realFrame()}\n"))
    }

    @Test
    fun `every frame type the protocol defines is forwarded`() {
        // sms.md: Q request, G offer, C ack, S status.
        assertTrue(SmsGateway.looksLikePact("Q|101|7F3K|15223C03Q0|6QR6VFBQ33|7E"))
        assertTrue(SmsGateway.looksLikePact("G|002|N001|1A2B3C|6QR6VFBQ33|1F"))
        assertTrue(SmsGateway.looksLikePact("C|003|7F3K|REQ123|1|2"))
        assertTrue(SmsGateway.looksLikePact("S|004|7F3K|REQ123|3"))
    }

    // -----------------------------------------------------------------------
    // Refuses everything else -- the part that matters
    // -----------------------------------------------------------------------

    @Test
    fun `a banking OTP is never forwarded`() {
        assertFalse(SmsGateway.looksLikePact(
            "Your OTP is 419281. Do not share it with anyone. -HDFC Bank"))
    }

    @Test
    fun `a personal message is never forwarded`() {
        assertFalse(SmsGateway.looksLikePact("are you coming home for dinner?"))
    }

    @Test
    fun `marketing spam with pipes is not mistaken for a frame`() {
        assertFalse(SmsGateway.looksLikePact(
            "MEGA SALE | 70% OFF | ends today | shop now bit.ly/x"))
    }

    @Test
    fun `a message merely starting with a frame letter is not enough`() {
        // "Quick question | see you | later" begins with Q and has pipes.
        assertFalse(SmsGateway.looksLikePact("Quick question | see you | later"))
    }

    @Test
    fun `a frame type with too few fields is refused`() {
        assertFalse(SmsGateway.looksLikePact("Q|hello"))
        assertFalse(SmsGateway.looksLikePact("Q|101|7F3K"))
    }

    @Test
    fun `an empty or blank message is refused`() {
        assertFalse(SmsGateway.looksLikePact(""))
        assertFalse(SmsGateway.looksLikePact("   "))
    }

    @Test
    fun `an unknown frame letter is refused`() {
        assertFalse(SmsGateway.looksLikePact("X|101|7F3K|payload|geo|7E"))
        assertFalse(SmsGateway.looksLikePact("A|1|2|3|4|5"))
    }

    @Test
    fun `lowercase is refused because the protocol is uppercase on the wire`() {
        assertFalse(SmsGateway.looksLikePact("q|101|7f3k|15223c03q0|6qr6vfbq33|7e"))
    }

    @Test
    fun `a long OTP-style message containing digits and pipes stays refused`() {
        assertFalse(SmsGateway.looksLikePact(
            "TXN|4429|DEBIT|Rs.2,500.00|A/c XX1234|Bal Rs.18,220.10"))
    }
}
