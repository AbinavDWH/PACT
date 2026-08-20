package org.humanitarian.fieldapp.sms

import android.content.Context

object GatewayConfig {

    private const val PREFS_NAME = "pact_gateway_config"
    private const val KEY_GATEWAY_PHONE = "gateway_phone_number"
    private const val KEY_AUTO_SMS_FALLBACK = "auto_sms_fallback_enabled"
    private const val KEY_IS_GATEWAY_HOST = "is_gateway_host_mode"

    // Default emergency coordinator gateway number requested by user
    const val DEFAULT_GATEWAY_PHONE = "7401231450"

    fun getGatewayPhoneNumber(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val num = prefs.getString(KEY_GATEWAY_PHONE, DEFAULT_GATEWAY_PHONE) ?: DEFAULT_GATEWAY_PHONE
        return if (num.isBlank()) DEFAULT_GATEWAY_PHONE else num
    }

    fun setGatewayPhoneNumber(context: Context, phoneNumber: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_GATEWAY_PHONE, phoneNumber.trim()).apply()
    }

    fun isAutoSmsFallbackEnabled(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getBoolean(KEY_AUTO_SMS_FALLBACK, true)
    }

    fun setAutoSmsFallbackEnabled(context: Context, enabled: Boolean) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putBoolean(KEY_AUTO_SMS_FALLBACK, enabled).apply()
    }

    fun isGatewayHostMode(context: Context): Boolean {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getBoolean(KEY_IS_GATEWAY_HOST, true)
    }

    fun setGatewayHostMode(context: Context, isHost: Boolean) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putBoolean(KEY_IS_GATEWAY_HOST, isHost).apply()
    }
}
