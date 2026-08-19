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
import org.humanitarian.fieldapp.ui.FieldReportScreen
import org.humanitarian.fieldapp.ui.HomeScreen
import org.humanitarian.fieldapp.ui.MyRequestsScreen
import org.humanitarian.fieldapp.ui.OfflineMapScreen
import org.humanitarian.fieldapp.ui.SmsDecoderScreen
import org.humanitarian.fieldapp.ui.SmsFallbackScreen
import org.humanitarian.fieldapp.ui.StatusUpdateScreen
import org.humanitarian.fieldapp.ui.theme.PactTheme

class MainActivity : ComponentActivity() {

    private val requestPermissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { /* Permissions requested */ }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 1. Initialize OSMDroid
        org.osmdroid.config.Configuration.getInstance().userAgentValue = packageName

        // 2. Request Location Permissions
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            requestPermissionLauncher.launch(
                arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION)
            )
        }

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
}