package org.pact.app

import android.Manifest
import android.app.Activity
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.telephony.SmsManager
import android.telephony.SubscriptionManager
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/**
 * One wire format, two transports.
 *
 * The string handed to [send] is the same string either way -- it is not
 * re-encoded, re-shaped or trimmed for SMS. That identity is the claim the
 * whole design rests on, so this class deliberately has no "sms variant" of a
 * payload anywhere in it.
 *
 * Order of attempts:
 *
 *   1. If the OS reports a validated internet connection, try HTTP.
 *   2. On any failure -- no connection, timeout, 5xx -- fall back to SMS.
 *   3. If SMS is unavailable too, the entry stays pending in the outbox and is
 *      retried later. Nothing is ever silently dropped.
 *
 * Step 2 is why the backend dedupes on (uid, seq): a request that timed out on
 * HTTP may well have been received, and the SMS retry must not create a second
 * request for the same emergency.
 */
class Transport(
    private val context: Context,
    private val api: Api,
    private val outbox: Outbox,
) {

    enum class Result { SENT_HTTP, SENT_SMS, QUEUED }

    data class Outcome(val result: Result, val detail: String, val traceId: String? = null)

    /** Has the OS validated an actual internet path, not merely an associated
     *  wifi network? A captive portal reports connected and routes nothing. */
    fun online(): Boolean {
        val cm = context.getSystemService(ConnectivityManager::class.java) ?: return false
        val caps = cm.getNetworkCapabilities(cm.activeNetwork) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) &&
            caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_VALIDATED)
    }

    fun canSendSms(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.SEND_SMS) ==
            PackageManager.PERMISSION_GRANTED

    /**
     * Queue then send. The outbox write happens BEFORE the first attempt, so a
     * process death between "user pressed send" and "network replied" leaves a
     * pending entry rather than nothing at all.
     */
    suspend fun send(id: String, payload: String): Outcome {
        outbox.add(id, payload)
        return attempt(id, payload)
    }

    suspend fun attempt(id: String, payload: String): Outcome {
        if (online() && !BuildConfig.FORCE_SMS) {
            try {
                val res = api.ingest(payload)
                val status = res.optString("status")
                if (status == "accepted") {
                    val trace = res.optString("trace_id").ifBlank { null }
                    outbox.mark(id, "sent_http", transport = "http", note = trace)
                    return Outcome(Result.SENT_HTTP, "Sent over data.", trace)
                }
                // A rejected payload is a bug in this app, not a network
                // problem. Retrying it over SMS would only waste a message.
                val err = res.optString("error").ifBlank { "REJECTED" }
                outbox.mark(id, "failed", transport = "http", note = err)
                return Outcome(Result.QUEUED, "Server rejected the request: $err")
            } catch (e: Exception) {
                Log.w(TAG, "http send failed, falling back to SMS", e)
            }
        }

        if (canSendSms()) {
            try {
                val detail = sendSms(payload)
                outbox.mark(id, "sent_sms", transport = "sms", note = detail)
                return Outcome(Result.SENT_SMS, "No data. Sent as an SMS.")
            } catch (e: Exception) {
                // The real reason, recorded. "sms failed" told nobody anything
                // and made the outbox useless for diagnosis.
                Log.w(TAG, "sms send failed", e)
                outbox.mark(id, "pending", transport = null,
                            note = "sms failed: ${e.message}")
                return Outcome(Result.QUEUED,
                               "Could not send by SMS: ${e.message}. Saved and will retry.")
            }
        }

        outbox.mark(id, "pending", note = "no data, no SMS permission")
        return Outcome(Result.QUEUED,
            "Saved. Grant SMS permission or reconnect and it will send itself.")
    }

    /** Retries everything still pending. Called on app start and whenever the
     *  status screen is opened. */
    suspend fun drain(): Int {
        var sent = 0
        for (e in outbox.pending()) {
            if (e.payload.isBlank()) continue
            val r = attempt(e.id, e.payload)
            if (r.result != Result.QUEUED) sent++
        }
        return sent
    }

    /**
     * Send, and wait for the radio to say what happened.
     *
     * `sendTextMessage` returns as soon as the message is handed to the
     * telephony stack. It throws only on bad arguments, so passing null
     * PendingIntents -- which this did -- means the app learns nothing about
     * whether the message was actually transmitted. The outbox then reported
     * "Sent as SMS" when all it knew was "the call did not throw", which is
     * precisely the kind of unearned confidence this project keeps removing.
     *
     * It also cost a debugging session: the app insisted it had sent while the
     * receiving handset showed nothing, and there was no evidence either way.
     *
     * The result intent gives the real answer -- RESULT_OK, or a specific
     * failure like no service, radio off, or a null PDU.
     */
    private suspend fun sendSms(payload: String): String = withContext(Dispatchers.IO) {
        // Bind to the subscription the user actually sends SMS on. This phone
        // is dual-SIM with slot 1 empty, and an SmsManager not bound to a
        // subscription can resolve to the absent slot and no-op silently.
        val base = context.getSystemService(SmsManager::class.java)
            ?: throw IllegalStateException("no SmsManager on this device")
        val subId = SubscriptionManager.getDefaultSmsSubscriptionId()
        val sms = if (subId != SubscriptionManager.INVALID_SUBSCRIPTION_ID) {
            runCatching { base.createForSubscriptionId(subId) }.getOrDefault(base)
        } else base
        Log.i(TAG, "sending to ${BuildConfig.SMS_TO} on subId=$subId")

        val sendId = java.util.UUID.randomUUID().toString()
        val result = SmsResultReceiver.awaitResult(sendId)

        // EXPLICIT: names the receiver class outright. An implicit
        // Intent(action) here is what broke the send on Android 16 -- see
        // SmsResultReceiver's comment. The unique requestCode stops
        // FLAG_UPDATE_CURRENT from overwriting a concurrent send's intent.
        val intent = Intent(context, SmsResultReceiver::class.java)
            .setAction(SmsResultReceiver.ACTION)
            .putExtra(SmsResultReceiver.EXTRA_ID, sendId)
        val pi = PendingIntent.getBroadcast(
            context, sendId.hashCode(), intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

        try {
            // The codec is sized so a request fits one segment, but divide
            // anyway: a multipart send that silently truncates would corrupt
            // the checksum and the backend would reject a real emergency as
            // BAD_CRC.
            // TEMPORARY DIAGNOSTIC: isolate whether the modem is rejecting the
            // message CONTENT (pipes are GSM-7 extension characters) or the
            // send path itself. Remove once answered.
            val body = if (BuildConfig.SMS_PLAIN_TEST) "PACTTEST123" else payload
            Log.i(TAG, "body=[$body] len=${body.length}")

            val parts = sms.divideMessage(body)
            if (parts.size == 1) {
                sms.sendTextMessage(BuildConfig.SMS_TO, null, body, pi, null)
            } else {
                sms.sendMultipartTextMessage(
                    BuildConfig.SMS_TO, null, parts,
                    ArrayList(List(parts.size) { pi }), null)
            }

            // Bounded: a radio that never answers must not hang the send
            // forever, and an unknown outcome is reported as unknown rather
            // than as success.
            val code = withTimeoutOrNull(30_000) { result.await() }
            when {
                code == null -> throw SmsFailure("no confirmation from the radio after 30 s")
                code == Activity.RESULT_OK -> SmsResultReceiver.describe(code)
                else -> throw SmsFailure(SmsResultReceiver.describe(code))
            }
        } finally {
            SmsResultReceiver.forget(sendId)
        }
    }

    class SmsFailure(message: String) : Exception(message)

    companion object { private const val TAG = "PactTransport" }
}
