package org.humanitarian.fieldapp

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import org.humanitarian.fieldapp.network.ApiClient
import org.humanitarian.fieldapp.ui.FieldReportScreen
import org.humanitarian.fieldapp.ui.HomeScreen
import org.humanitarian.fieldapp.ui.MyRequestsScreen
import org.humanitarian.fieldapp.ui.OfflineMapScreen
import org.humanitarian.fieldapp.ui.SmsDecoderScreen
import org.humanitarian.fieldapp.ui.SmsFallbackScreen
import org.humanitarian.fieldapp.ui.StatusUpdateScreen
import org.humanitarian.fieldapp.ui.theme.PactTheme
import kotlin.coroutines.resume

class MainActivity : ComponentActivity() {

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { /* result handled silently for hackathon */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // OSMDroid init
        org.osmdroid.config.Configuration.getInstance().userAgentValue = packageName

        // Location permissions
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissionLauncher.launch(
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            )
        }

        // START REAL-TIME LOCATION SENDER (every 10 seconds)
        startRealTimeLocationSender()

        setContent {
            PactTheme {
                var currentScreen by remember { mutableStateOf("home") }

                when (currentScreen) {
                    "home" -> HomeScreen(
                        onNavigateToFieldReport = { currentScreen = "field_report" },
                        onNavigateToMyRequests = { currentScreen = "my_requests" },
                        onNavigateToSmsFallback = { currentScreen = "sms_fallback" },
                        onNavigateToSmsDecoder = { currentScreen = "sms_decoder" },
                        onNavigateToOfflineMap = { currentScreen = "offline_map" },
                        onNavigateToStatus = { currentScreen = "status_update" }
                    )
                    "field_report" -> FieldReportScreen(onBack = { currentScreen = "home" }, onReturnHome = { currentScreen = "home" })
                    "my_requests" -> MyRequestsScreen(onBack = { currentScreen = "home" })
                    "sms_fallback" -> SmsFallbackScreen(onBack = { currentScreen = "home" })
                    "sms_decoder" -> SmsDecoderScreen(onBack = { currentScreen = "home" })
                    "offline_map" -> OfflineMapScreen(onBack = { currentScreen = "home" })
                    "status_update" -> StatusUpdateScreen(onBack = { currentScreen = "home" })
                }
            }
        }
    }

    private fun startRealTimeLocationSender() {
        val fused = LocationServices.getFusedLocationProviderClient(this)
        lifecycleScope.launch {
            while (true) {
                if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED) {
                    try {
                        val location = suspendCancellableCoroutine { cont ->
                            fused.getCurrentLocation(Priority.PRIORITY_HIGH_ACCURACY, null)
                                .addOnSuccessListener { loc -> cont.resume(loc) }
                                .addOnFailureListener { cont.resume(null) }
                        }
                        if (location != null) {
                            ApiClient.postLocationUpdate("NGO01", location.latitude, location.longitude)
                        }
                    } catch (_: Exception) {
                        // ignore GPS/network errors silently
                    }
                }
                delay(10_000) // send every 10 seconds
            }
        }
    }
}