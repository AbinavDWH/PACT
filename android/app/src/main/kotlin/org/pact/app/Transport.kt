package org.pact.app

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.telephony.SmsManager
import android.util.Log
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

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
        if (online()) {
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
                sendSms(payload)
                outbox.mark(id, "sent_sms", transport = "sms")
                return Outcome(Result.SENT_SMS, "No data. Sent as an SMS.")
            } catch (e: Exception) {
                Log.w(TAG, "sms send failed", e)
                outbox.mark(id, "pending", transport = null, note = "sms failed")
                return Outcome(Result.QUEUED, "Saved. Will retry when there is signal.")
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

    private suspend fun sendSms(payload: String) = withContext(Dispatchers.IO) {
        val sms = context.getSystemService(SmsManager::class.java)
            ?: throw IllegalStateException("no SmsManager on this device")
        // The codec is sized so a request fits one segment, but divide anyway:
        // a multipart send that silently truncates would corrupt the checksum
        // and the backend would reject a real emergency as BAD_CRC.
        val parts = sms.divideMessage(payload)
        if (parts.size == 1) {
            sms.sendTextMessage(BuildConfig.SMS_TO, null, payload, null, null)
        } else {
            sms.sendMultipartTextMessage(BuildConfig.SMS_TO, null, parts, null, null)
        }
    }

    companion object { private const val TAG = "PactTransport" }
}
