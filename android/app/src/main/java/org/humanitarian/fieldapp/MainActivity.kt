package org.humanitarian.fieldapp

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import org.humanitarian.fieldapp.ui.FieldReportScreen
import org.humanitarian.fieldapp.ui.HomeScreen
import org.humanitarian.fieldapp.ui.PlaceholderScreen
import org.humanitarian.fieldapp.ui.theme.PactTheme

class MainActivity : ComponentActivity() {

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        setContent {
            PactTheme {
                var currentScreen by remember {
                    mutableStateOf("home")
                }

                when (currentScreen) {
                    "home" -> {
                        HomeScreen(
                            onNavigateToFieldReport = {
                                currentScreen = "field_report"
                            },
                            onNavigateToSmsFallback = {
                                currentScreen = "sms_fallback"
                            },
                            onNavigateToOfflineMap = {
                                currentScreen = "offline_map"
                            },
                            onNavigateToStatus = {
                                currentScreen = "status_update"
                            }
                        )
                    }

                    "field_report" -> {
                        FieldReportScreen(
                            onBack = {
                                currentScreen = "home"
                            },
                            onReturnHome = {
                                currentScreen = "home"
                            }
                        )
                    }

                    "sms_fallback" -> {
                        PlaceholderScreen(
                            title = "SMS Fallback",
                            description = "Compact message encoding and decoding for low-connectivity reporting.",
                            onBack = {
                                currentScreen = "home"
                            }
                        )
                    }

                    "offline_map" -> {
                        PlaceholderScreen(
                            title = "Offline Map",
                            description = "Map-based incident visualization for field coordination.",
                            onBack = {
                                currentScreen = "home"
                            }
                        )
                    }

                    "status_update" -> {
                        PlaceholderScreen(
                            title = "Status Update",
                            description = "Team availability, safety status, and operational readiness updates.",
                            onBack = {
                                currentScreen = "home"
                            }
                        )
                    }
                }
            }
        }
    }
}