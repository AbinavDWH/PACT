package org.pact.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import android.util.Log
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * The SMS gateway. This is what makes the offline path real rather than
 * simulated.
 *
 * Until now the seeker phone sent a genuine SMS with `SmsManager` and nothing
 * received it. `/api/v1/sms/webhook` existed with no caller, so the only way a
 * codec string ever reached the backend "over SMS" was a human pasting it into
 * the simulator panel. The message left one handset and vanished.
 *
 * A second handset running this receiver closes the loop. It catches the real
 * inbound SMS off the cellular network and POSTs the body to the webhook that
 * was already written and waiting. No vendor, no cost, and nothing to
 * pre-register.
 *
 * That last point is not a convenience. Outbound A2P SMS in India requires DLT
 * registration with TRAI -- entity, header and template approval, taking days
 * to weeks -- and inbound SMS on an Indian virtual number is not sold to
 * unregistered entities at all. A vendor integration cannot be made to work
 * today at any price. Two ordinary SIMs can, and the traffic is the same real
 * cellular SMS either way.
 *
 * The gateway forwards only what looks like a PACT frame. A phone used as a
 * gateway still receives bank OTPs and personal messages, and forwarding those
 * to a server would be a far worse privacy failure than anything this project
 * is defending against.
 */
class SmsGateway : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return

        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        if (!prefs.getBoolean(KEY_ENABLED, false)) return

        // A long message arrives as several PDUs; concatenate before matching,
        // or a frame split across two parts is silently dropped.
        val body = Telephony.Sms.Intents.getMessagesFromIntent(intent)
            ?.joinToString("") { it.messageBody ?: "" }
            ?.trim()
            .orEmpty()

        if (body.isEmpty()) return

        if (!looksLikePact(body)) {
            // Deliberately not logged in full. A gateway handset receives OTPs
            // and private messages, and writing them to logcat would leak them
            // just as effectively as forwarding them.
            Log.d(TAG, "ignoring a non-PACT message (${body.length} chars)")
            return
        }

        val sender = Telephony.Sms.Intents.getMessagesFromIntent(intent)
            ?.firstOrNull()?.originatingAddress

        // onReceive must return promptly or the system kills the process, so
        // the network call goes to a scope rather than blocking here. A
        // goAsync() PendingResult keeps the process alive for the round trip.
        val pending = goAsync()
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val ok = forward(context, body, sender)
                record(context, body, sender, ok)
            } catch (e: Exception) {
                Log.w(TAG, "forward failed", e)
                record(context, body, sender, false)
            } finally {
                pending.finish()
            }
        }
    }

    private fun forward(context: Context, body: String, sender: String?): Boolean {
        val base = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .getString(KEY_BASE, null) ?: BuildConfig.API_BASE

        val conn = (URL("$base/api/v1/sms/webhook").openConnection() as HttpURLConnection).apply {
            requestMethod = "POST"
            connectTimeout = 8000
            readTimeout = 10000
            doOutput = true
            setRequestProperty("Content-Type", "application/json")
        }
        return try {
            val payload = JSONObject()
                .put("sms", body)
                // The number is what lets the backend match an inbound SMS to a
                // known account; it is hashed server-side and never stored raw.
                .put("from_number", sender ?: "")
                .toString()
            conn.outputStream.use { it.write(payload.toByteArray()) }
            val code = conn.responseCode
            val text = (if (code in 200..299) conn.inputStream else conn.errorStream)
                ?.bufferedReader()?.use(BufferedReader::readText).orEmpty()
            Log.i(TAG, "forwarded -> HTTP $code ${text.take(120)}")
            code in 200..299
        } finally {
            conn.disconnect()
        }
    }

    /** A visible log, so the gateway phone can be shown working rather than
     *  taken on trust. */
    private fun record(context: Context, body: String, sender: String?, ok: Boolean) {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val log = JSONObject()
            .put("body", body)
            .put("from", sender?.takeLast(4)?.let { "…$it" } ?: "unknown")
            .put("ok", ok)
            .put("at", System.currentTimeMillis())
            .toString()
        val existing = prefs.getStringSet(KEY_LOG, emptySet())!!.toMutableList()
        existing.add(0, log)
        prefs.edit().putStringSet(KEY_LOG, existing.take(30).toSet()).apply()
    }

    companion object {
        private const val TAG = "PactSmsGateway"
        const val PREFS = "pact.gateway"
        const val KEY_ENABLED = "enabled"
        const val KEY_BASE = "api_base"
        const val KEY_LOG = "log"

        /** Frame types from sms.md: request, offer, ack, status. */
        private val FRAME_TYPES = setOf("Q", "G", "C", "S")

        /**
         * Does this message look like a PACT frame?
         *
         * `<TYPE>|<seq>|<uid>|<payload>|<geo>|<crc>` with a type the protocol
         * defines. Deliberately strict, and asymmetric on purpose: the cost of
         * ignoring a real request is one retry by an app that already retries,
         * while the cost of forwarding someone's banking OTP to a server is
         * unacceptable and irreversible.
         *
         * In the companion object rather than the receiver so it can be tested
         * on the JVM. A privacy control with no test is a privacy claim.
         */
        fun looksLikePact(body: String): Boolean {
            val trimmed = body.trim()
            val head = trimmed.substringBefore("|", "")
            if (head !in FRAME_TYPES) return false
            // A bare "Q|hello" is not a frame. Every real type carries at
            // least four fields, so at least three separators.
            return trimmed.count { it == '|' } >= 3
        }

        fun isEnabled(context: Context): Boolean =
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getBoolean(KEY_ENABLED, false)

        fun setEnabled(context: Context, on: Boolean) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit().putBoolean(KEY_ENABLED, on).apply()
        }

        fun entries(context: Context): List<JSONObject> =
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getStringSet(KEY_LOG, emptySet())!!
                .mapNotNull { runCatching { JSONObject(it) }.getOrNull() }
                .sortedByDescending { it.optLong("at") }
    }
}
