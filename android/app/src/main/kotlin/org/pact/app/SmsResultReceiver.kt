package org.pact.app

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.util.Log
import kotlinx.coroutines.CompletableDeferred
import java.util.concurrent.ConcurrentHashMap

/**
 * Receives the telephony stack's verdict on a sent SMS.
 *
 * Declared in the manifest and targeted by an **explicit** Intent, rather than
 * registered dynamically and targeted by action.
 *
 * That distinction is the bug this class exists to fix. The previous version
 * built `PendingIntent.getBroadcast(ctx, code, Intent(action), FLAG_IMMUTABLE)`
 * -- an implicit intent, with no component. Android 14 restricted implicit
 * intents inside PendingIntents, and on Android 16 supplying one appears to
 * abort the send outright rather than merely losing the callback: the message
 * left no trace in `content://sms/{queued,outbox,failed}`, never reached the
 * recipient, and threw nothing. An earlier build passing `null` PendingIntents
 * delivered the same payload to the same SIM successfully, which is what
 * points at the PendingIntent rather than at the radio.
 *
 * An explicit component removes the ambiguity entirely.
 */
class SmsResultReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        val id = intent.getStringExtra(EXTRA_ID) ?: return
        Log.i(TAG, "sms result id=$id code=$resultCode")
        pending.remove(id)?.complete(resultCode)
    }

    companion object {
        private const val TAG = "PactSmsResult"

        const val ACTION = "org.pact.app.SMS_SENT"
        const val EXTRA_ID = "pact_send_id"

        /**
         * In-flight sends, keyed by a per-message id carried in the intent.
         *
         * A companion-object map rather than a captured lambda because the
         * receiver is instantiated by the system, not by us: there is no other
         * way to hand the result back to the coroutine that is waiting.
         * Entries are removed on completion, and the sender removes its own on
         * timeout, so nothing accumulates.
         */
        val pending = ConcurrentHashMap<String, CompletableDeferred<Int>>()

        fun awaitResult(id: String): CompletableDeferred<Int> {
            val d = CompletableDeferred<Int>()
            pending[id] = d
            return d
        }

        fun forget(id: String) {
            pending.remove(id)
        }

        /** Human-readable meaning of a telephony result code. */
        fun describe(code: Int): String = when (code) {
            android.app.Activity.RESULT_OK -> "delivered to the network"
            android.telephony.SmsManager.RESULT_ERROR_NO_SERVICE -> "no cellular service"
            android.telephony.SmsManager.RESULT_ERROR_RADIO_OFF ->
                "radio off (airplane mode disables SMS too)"
            android.telephony.SmsManager.RESULT_ERROR_NULL_PDU -> "null PDU"
            android.telephony.SmsManager.RESULT_ERROR_LIMIT_EXCEEDED ->
                "carrier rate limit exceeded"
            // Deliberately no exhaustive table beyond this: the numeric code is
            // printed for anything else, which is more useful than a wrong name.
            else -> "radio error code $code"
        }
    }
}
