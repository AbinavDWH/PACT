package org.pact.app

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.location.Location
import android.location.LocationManager
import androidx.core.content.ContextCompat
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeoutOrNull
import kotlin.coroutines.resume

/**
 * GPS, via android.location.LocationManager.
 *
 * Not Play Services' FusedLocationProvider, for a specific reason rather than
 * dependency minimalism: fused location leans on network and wifi positioning,
 * and this app has to produce a coordinate on a handset with no data at all.
 * The raw GPS provider is the one that still works in that case, which is the
 * scenario the product exists for.
 */
class Loc(private val context: Context) {

    data class Fix(val lat: Double, val lon: Double, val accuracyM: Double?,
                   val provider: String, val ageMs: Long)

    fun hasPermission(): Boolean =
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) ==
            PackageManager.PERMISSION_GRANTED

    @SuppressLint("MissingPermission")
    fun lastKnown(): Fix? {
        if (!hasPermission()) return null
        val lm = context.getSystemService(LocationManager::class.java) ?: return null
        val best = lm.allProviders
            .mapNotNull { p -> runCatching { lm.getLastKnownLocation(p) }.getOrNull() }
            .maxByOrNull { it.time } ?: return null
        return best.toFix()
    }

    /**
     * Waits for a fresh fix, falling back to the last known one.
     *
     * A cold GPS fix can take thirty seconds or more. Blocking a person
     * reporting a collapsed building for that long is not acceptable, so this
     * caps the wait and the caller proceeds with whatever it has -- the codec
     * carries an accuracy character precisely so a coarse fix is legible as
     * coarse rather than passed off as exact.
     */
    @SuppressLint("MissingPermission")
    suspend fun current(timeoutMs: Long = 8_000): Fix? {
        if (!hasPermission()) return null
        val lm = context.getSystemService(LocationManager::class.java) ?: return null

        val fresh = withTimeoutOrNull(timeoutMs) {
            suspendCancellableCoroutine<Location?> { cont ->
                val providers = listOf(LocationManager.GPS_PROVIDER,
                                       LocationManager.NETWORK_PROVIDER)
                    .filter { runCatching { lm.isProviderEnabled(it) }.getOrDefault(false) }
                if (providers.isEmpty()) { cont.resume(null); return@suspendCancellableCoroutine }

                val listener = object : android.location.LocationListener {
                    override fun onLocationChanged(location: Location) {
                        runCatching { lm.removeUpdates(this) }
                        if (cont.isActive) cont.resume(location)
                    }
                    @Deprecated("required on API < 30")
                    override fun onStatusChanged(p: String?, s: Int, e: android.os.Bundle?) {}
                    override fun onProviderDisabled(provider: String) {}
                    override fun onProviderEnabled(provider: String) {}
                }
                providers.forEach {
                    runCatching { lm.requestLocationUpdates(it, 0L, 0f, listener) }
                }
                cont.invokeOnCancellation { runCatching { lm.removeUpdates(listener) } }
            }
        }
        return fresh?.toFix() ?: lastKnown()
    }

    private fun Location.toFix() = Fix(
        lat = latitude, lon = longitude,
        accuracyM = if (hasAccuracy()) accuracy.toDouble() else null,
        provider = provider ?: "unknown",
        ageMs = (System.currentTimeMillis() - time).coerceAtLeast(0),
    )
}
