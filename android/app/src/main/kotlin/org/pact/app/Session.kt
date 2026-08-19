package org.pact.app

import android.content.Context
import android.provider.Settings
import java.util.UUID

/**
 * The device session. One short sign-up screen, once, then never again
 * (memory_draft.md 7.1) -- so this has to survive process death and app
 * restarts, and it is the only reason SharedPreferences is here.
 *
 * What is stored locally is deliberately minimal: the UID that goes on the
 * wire, the bearer token, the role, and the sequence counter. The name and
 * phone live server-side, encrypted. Keeping a second copy of them on the
 * handset would undo the identity split for no benefit -- the app never needs
 * to display them back to the user.
 */
class Session(context: Context) {

    private val prefs = context.getSharedPreferences("pact.session", Context.MODE_PRIVATE)
    private val resolver = context.applicationContext.contentResolver

    var uid: String?
        get() = prefs.getString("uid", null)
        private set(v) = prefs.edit().putString("uid", v).apply()

    var token: String?
        get() = prefs.getString("token", null)
        private set(v) = prefs.edit().putString("token", v).apply()

    var role: String?
        get() = prefs.getString("role", null)
        private set(v) = prefs.edit().putString("role", v).apply()

    var orgId: String?
        get() = prefs.getString("org_id", null)
        private set(v) = prefs.edit().putString("org_id", v).apply()

    var orgName: String?
        get() = prefs.getString("org_name", null)
        private set(v) = prefs.edit().putString("org_name", v).apply()

    val signedIn: Boolean get() = !uid.isNullOrEmpty() && !token.isNullOrEmpty()

    /**
     * A stable per-install id. ANDROID_ID is per app-signing-key per user and
     * survives restarts but not a reinstall, which matches the spec exactly:
     * "stable across restarts; regenerated on reinstall" (memory_draft.md 7.2).
     * The random fallback covers the handsets where it comes back null.
     */
    val deviceId: String
        get() = prefs.getString("device_id", null) ?: run {
            @Suppress("HardwareIds")
            val android = try {
                Settings.Secure.getString(resolver, Settings.Secure.ANDROID_ID)
            } catch (_: Exception) { null }
            // 9774d56d682e549c is the notorious shared ANDROID_ID from a batch
            // of buggy devices; treating it as unique would collide accounts.
            val id = android?.takeIf { it.isNotBlank() && it != "9774d56d682e549c" }
                ?: UUID.randomUUID().toString()
            prefs.edit().putString("device_id", id).commit()
            id
        }

    /**
     * Monotonic per-device message counter. The backend dedupes on (uid, seq),
     * so this MUST NOT restart at 0 after the app is killed -- an app that
     * resets its counter re-sends seq 001 and the server silently drops a real
     * emergency as a duplicate. Hence the commit rather than apply.
     */
    fun nextSeq(): Int {
        val next = (prefs.getInt("seq", 0) + 1).let { if (it > 999) 1 else it }
        prefs.edit().putInt("seq", next).commit()
        return next
    }

    fun save(uid: String, token: String, role: String,
             orgId: String?, orgName: String?) {
        this.uid = uid
        this.token = token
        this.role = role
        this.orgId = orgId
        this.orgName = orgName
    }

    fun setOrg(orgId: String?, orgName: String?, token: String?) {
        this.orgId = orgId
        this.orgName = orgName
        if (token != null) this.token = token
    }

    /** Clears the session. The account survives: the UID is derived from the
     *  device id, which is kept, so signing back in restores the same identity. */
    fun signOut() {
        prefs.edit()
            .remove("uid").remove("token").remove("role")
            .remove("org_id").remove("org_name")
            .apply()
    }
}
