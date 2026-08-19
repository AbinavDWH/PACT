package org.pact.app

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.util.Log
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * Real push. Replaces the outbox row that used to stand in for a delivered
 * notification.
 *
 * The registration token is per install and rotates, so it is re-sent to the
 * backend on every sign-in and whenever Firebase issues a new one. A token
 * captured once at sign-up and never refreshed is the usual reason push
 * "works in testing and not in the field".
 */
object Push {

    const val CHANNEL_ID = "pact_assignments"
    private const val TAG = "PactPush"

    fun ensureChannel(context: Context) {
        val mgr = context.getSystemService(NotificationManager::class.java) ?: return
        // Importance HIGH: an assignment is time-critical and must be able to
        // interrupt. This is not marketing.
        val channel = NotificationChannel(
            CHANNEL_ID, "Assignments", NotificationManager.IMPORTANCE_HIGH,
        ).apply { description = "Deliveries and rescues assigned to you" }
        mgr.createNotificationChannel(channel)
    }

    /** Fetches the current token and registers it. Safe to call repeatedly. */
    fun register(context: Context, session: Session) {
        if (!BuildConfig.HAS_FCM) return
        val uid = session.uid ?: return
        FirebaseMessaging.getInstance().token
            .addOnSuccessListener { token -> send(context, session, uid, token) }
            .addOnFailureListener { e -> Log.w(TAG, "could not obtain an FCM token", e) }
    }

    fun send(context: Context, session: Session, uid: String, token: String) {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                val base = BuildConfig.API_BASE
                val conn = (URL("$base/api/v1/helpers/me/push-token")
                    .openConnection() as HttpURLConnection).apply {
                    requestMethod = "PUT"
                    connectTimeout = 6000
                    readTimeout = 8000
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json")
                    session.token?.let { setRequestProperty("Authorization", "Bearer $it") }
                }
                try {
                    val body = JSONObject()
                        .put("fcm_token", token)
                        .put("uid", uid)
                        .toString()
                    conn.outputStream.use { it.write(body.toByteArray()) }
                    val code = conn.responseCode
                    val text = (if (code in 200..299) conn.inputStream else conn.errorStream)
                        ?.bufferedReader()?.use(BufferedReader::readText).orEmpty()
                    Log.i(TAG, "token registered -> HTTP $code ${text.take(100)}")
                } finally {
                    conn.disconnect()
                }
            } catch (e: Exception) {
                // Not fatal: dispatch falls back to the outbox and the helper
                // can still pull assignments from the list screen.
                Log.w(TAG, "token registration failed", e)
            }
        }
    }
}

/**
 * Receives assignments while the app is backgrounded or closed.
 *
 * The server sends a data-only message rather than a notification payload, so
 * this runs in every app state and the notification is built here. A
 * notification payload would be rendered by the system while the app is in the
 * background, and this handler would never see it.
 */
class PactMessagingService : FirebaseMessagingService() {

    override fun onNewToken(token: String) {
        // Tokens rotate. Re-register or the next assignment goes nowhere.
        val session = Session(applicationContext)
        session.uid?.let { Push.send(applicationContext, session, it, token) }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val data = message.data
        val title = data["title"] ?: "New assignment"
        // The body has already been through A7's helper_pre projection on the
        // server: approximate area, no name, no contact. Nothing is redacted
        // here, because nothing sensitive should have arrived.
        val body = data["body"] ?: message.notification?.body ?: ""

        Push.ensureChannel(applicationContext)

        val builder = android.app.Notification.Builder(applicationContext, Push.CHANNEL_ID)
            .setContentTitle(title)
            .setContentText(body)
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setAutoCancel(true)
            .setStyle(android.app.Notification.BigTextStyle().bigText(body))

        val mgr = getSystemService(NotificationManager::class.java) ?: return
        mgr.notify(data["match_id"]?.hashCode() ?: 1, builder.build())
    }
}
