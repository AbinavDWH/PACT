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
import org.humanitarian.fieldapp.ui.OfflineMapScreen
import org.humanitarian.fieldapp.ui.SmsDecoderScreen
import org.humanitarian.fieldapp.ui.SmsFallbackScreen
import org.humanitarian.fieldapp.ui.StatusUpdateScreen
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
                            onNavigateToSmsDecoder = {
                                currentScreen = "sms_decoder"
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
                        SmsFallbackScreen(
                            onBack = {
                                currentScreen = "home"
                            }
                        )
                    }

                    "sms_decoder" -> {
                        SmsDecoderScreen(
                            onBack = {
                                currentScreen = "home"
                            }
                        )
                    }

                    "offline_map" -> {
                        OfflineMapScreen(
                            onBack = {
                                currentScreen = "home"
                            }
                        )
                    }

                    "status_update" -> {
                        StatusUpdateScreen(
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