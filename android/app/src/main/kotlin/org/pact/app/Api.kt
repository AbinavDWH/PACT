package org.pact.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedReader
import java.net.HttpURLConnection
import java.net.URL

/**
 * The HTTP client. HttpURLConnection rather than Retrofit or OkHttp: every
 * library added here is a download that has to succeed on venue wifi the
 * morning of a demo, and this needs four verbs and a bearer header.
 *
 * Timeouts are short on purpose. This app's whole premise is that the network
 * is unreliable, so a request that hangs for thirty seconds is worse than one
 * that fails in four and falls back to SMS.
 */
class Api(private val base: String, private val session: Session) {

    class HttpError(val code: Int, val body: String) :
        Exception("HTTP $code: ${body.take(200)}")

    private suspend fun request(
        method: String, path: String, body: String? = null, auth: Boolean = true,
    ): JSONObject = withContext(Dispatchers.IO) {
        val conn = (URL("$base$path").openConnection() as HttpURLConnection).apply {
            requestMethod = method
            connectTimeout = CONNECT_TIMEOUT_MS
            readTimeout = READ_TIMEOUT_MS
            setRequestProperty("Accept", "application/json")
            if (auth) session.token?.let {
                setRequestProperty("Authorization", "Bearer $it")
            }
            if (body != null) {
                doOutput = true
                setRequestProperty("Content-Type", "application/json")
            }
        }
        try {
            body?.let { conn.outputStream.use { os -> os.write(it.toByteArray()) } }
            val code = conn.responseCode
            val text = (if (code in 200..299) conn.inputStream else conn.errorStream)
                ?.bufferedReader()?.use(BufferedReader::readText).orEmpty()
            if (code !in 200..299) throw HttpError(code, text)
            if (text.isBlank()) JSONObject() else JSONObject(text)
        } finally {
            conn.disconnect()
        }
    }

    // -- session ------------------------------------------------------------

    suspend fun signup(role: String, name: String, phone: String,
                       groupCode: String?): JSONObject {
        val body = JSONObject()
            .put("role", role)
            .put("device_id", session.deviceId)
            .put("name", name)
            .put("phone", phone)
        if (!groupCode.isNullOrBlank()) body.put("group_code", groupCode.trim().uppercase())
        return request("POST", "/api/v1/session/signup", body.toString(), auth = false)
    }

    suspend fun me(): JSONObject = request("GET", "/api/v1/session/me")

    suspend fun signout(): JSONObject = request("POST", "/api/v1/session/signout", "{}")

    suspend fun join(groupCode: String): JSONObject = request(
        "POST", "/api/v1/helpers/join",
        JSONObject().put("group_code", groupCode.trim().uppercase()).toString())

    // -- the one wire format ------------------------------------------------

    /**
     * The codec string over HTTP. Byte-for-byte the same string the SMS path
     * sends -- that identity is the claim the whole transport layer exists to
     * make, so there is deliberately no "http variant" of the payload here.
     */
    suspend fun ingest(payload: String): JSONObject = request(
        "POST", "/api/v1/pact/ingest",
        JSONObject().put("payload", payload).put("transport", "http").toString(),
        auth = false)

    // -- helper side --------------------------------------------------------

    suspend fun assignments(actorId: String): JSONArray {
        val o = request("GET", "/api/v1/helpers/me/assignments?actor_id=$actorId")
        return o.optJSONArray("assignments") ?: JSONArray()
    }

    suspend fun accept(matchId: String, actorId: String): JSONObject = request(
        "POST", "/api/v1/assignments/$matchId/accept",
        JSONObject().put("actor_id", actorId).toString())

    suspend fun decline(matchId: String, actorId: String, reason: String): JSONObject = request(
        "POST", "/api/v1/assignments/$matchId/decline",
        JSONObject().put("actor_id", actorId).put("reason", reason).toString())

    suspend fun health(): JSONObject = request("GET", "/api/v1/health", auth = false)

    companion object {
        const val CONNECT_TIMEOUT_MS = 4000
        const val READ_TIMEOUT_MS = 6000
    }
}
