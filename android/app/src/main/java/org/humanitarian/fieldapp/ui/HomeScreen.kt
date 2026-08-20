package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.humanitarian.fieldapp.models.UserRole
import org.humanitarian.fieldapp.models.UserSession
import org.humanitarian.fieldapp.offline.OfflineQueue
import org.humanitarian.fieldapp.sync.SyncManager
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    onNavigateToFieldReport: () -> Unit,
    onNavigateToMyRequests: () -> Unit,
    onNavigateToSmsGateway: () -> Unit,
    onNavigateToSmsFallback: () -> Unit,
    onNavigateToSmsDecoder: () -> Unit,
    onNavigateToOfflineMap: () -> Unit,
    onNavigateToStatus: () -> Unit,
    onLogout: () -> Unit
) {
    val context = LocalContext.current
    val userSession = UserSession.current
    var queueSize by remember { mutableStateOf(OfflineQueue.getQueueSize(context)) }
    var autoSyncMessage by remember { mutableStateOf("") }

    val permissionLauncher = androidx.activity.compose.rememberLauncherForActivityResult(
        contract = androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions()
    ) { _ -> }

    // Request SMS permissions and auto-sync whenever the home screen opens
    LaunchedEffect(Unit) {
        permissionLauncher.launch(
            arrayOf(
                android.Manifest.permission.RECEIVE_SMS,
                android.Manifest.permission.READ_SMS,
                android.Manifest.permission.SEND_SMS
            )
        )
        queueSize = OfflineQueue.getQueueSize(context)
        if (queueSize > 0) {
            val result = SyncManager.syncQueue(context)
            if (result.synced > 0) {
                autoSyncMessage = "${result.synced} queued report(s) synced automatically."
            }
            queueSize = OfflineQueue.getQueueSize(context)
        }
    }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "PACT Field App",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = PactTextPrimary
                        )
                        if (userSession != null) {
                            Text(
                                text = "${userSession.displayName} · ${userSession.organizationId}",
                                style = MaterialTheme.typography.bodySmall,
                                color = PactTextSecondary
                            )
                        }
                    }
                },
                actions = {
                    TextButton(onClick = onLogout) {
                        Text(
                            text = "Logout",
                            color = PactPrimary,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = PactSurface,
                    titleContentColor = PactTextPrimary
                )
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // USER ROLE CARD
            if (userSession != null) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    color = PactSurface,
                    border = BorderStroke(1.dp, PactAccent)
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "Logged in as",
                                style = MaterialTheme.typography.bodySmall,
                                color = PactTextSecondary
                            )
                            Text(
                                text = when (userSession.role) {
                                    UserRole.ADMIN -> "Administrator"
                                    UserRole.DONOR_GROUP -> "Donor Group"
                                    UserRole.INDIVIDUAL -> "Individual"
                                },
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                                color = PactTextPrimary
                            )
                        }
                        Surface(
                            shape = RoundedCornerShape(12.dp),
                            color = PactAccent
                        ) {
                            Text(
                                text = userSession.organizationId,
                                modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold,
                                color = PactPrimary
                            )
                        }
                    }
                }
            }

            // MISSION CONSOLE
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = PactSurface,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "Mission Console",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = PactTextPrimary
                    )
                    Text(
                        text = "Select an operational module. The interface is optimized for low connectivity and fast field use.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = PactTextSecondary
                    )
                }
            }

            // OFFLINE QUEUE BANNER
            if (queueSize > 0) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    color = PactAccent,
                    border = BorderStroke(1.dp, PactPrimary)
                ) {
                    Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = "$queueSize report(s) in offline queue",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = PactTextPrimary
                        )
                        Text(
                            text = "Open My Requests to view payloads or sync when internet returns.",
                            style = MaterialTheme.typography.bodySmall,
                            color = PactTextSecondary
                        )
                    }
                }
            }

            if (autoSyncMessage.isNotBlank()) {
                Text(
                    text = autoSyncMessage,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    color = PactPrimary
                )
            }

            // ROLE-SPECIFIC MODULES & ACTION BUTTONS
            when (userSession?.role) {
                UserRole.ADMIN -> {
                    // Admin: Full control over field reporting, request review, and gateway tools
                    Button(
                        onClick = onNavigateToSmsGateway,
                        modifier = Modifier.fillMaxWidth().height(64.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = PactPrimary,
                            contentColor = PactOnPrimary
                        )
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Column(horizontalAlignment = Alignment.Start) {
                                Text(
                                    text = "SMS Gateway Hub",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Bold
                                )
                                Text(
                                    text = "Automated GSM Relay (Inbound / Outbound)",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = PactAccent
                                )
                            }
                            Surface(
                                shape = RoundedCornerShape(8.dp),
                                color = PactAccent
                            ) {
                                Text(
                                    text = "RELAY HUB",
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                    color = PactPrimary
                                )
                            }
                        }
                    }

                    Button(
                        onClick = onNavigateToFieldReport,
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = PactSurface,
                            contentColor = PactTextPrimary
                        ),
                        border = BorderStroke(1.dp, PactAccent)
                    ) {
                        Text(
                            text = "Field Report",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    Button(
                        onClick = onNavigateToMyRequests,
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = PactSurface,
                            contentColor = PactTextPrimary
                        ),
                        border = BorderStroke(1.dp, PactAccent)
                    ) {
                        Text(
                            text = "All Requests",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    HomeActionButton(title = "SMS Fallback", onClick = onNavigateToSmsFallback)
                    HomeActionButton(title = "SMS Decoder", onClick = onNavigateToSmsDecoder)
                    HomeActionButton(title = "Offline Map", onClick = onNavigateToOfflineMap)
                    HomeActionButton(title = "Status Update", onClick = onNavigateToStatus)
                }

                UserRole.INDIVIDUAL -> {
                    // Individual: Field crisis reporting and offline map
                    Button(
                        onClick = onNavigateToFieldReport,
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = PactPrimary,
                            contentColor = PactOnPrimary
                        )
                    ) {
                        Text(
                            text = "Field Report",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    Button(
                        onClick = onNavigateToMyRequests,
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = PactSurface,
                            contentColor = PactTextPrimary
                        ),
                        border = BorderStroke(1.dp, PactAccent)
                    ) {
                        Text(
                            text = "My Requests",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    HomeActionButton(title = "SMS Gateway Hub", onClick = onNavigateToSmsGateway)
                    HomeActionButton(title = "SMS Fallback", onClick = onNavigateToSmsFallback)
                    HomeActionButton(title = "Offline Map", onClick = onNavigateToOfflineMap)
                }

                UserRole.DONOR_GROUP, null -> {
                    // Donor Group: Restricted access - Track aid donations & allocations, view regional map
                    Button(
                        onClick = onNavigateToMyRequests,
                        modifier = Modifier.fillMaxWidth().height(56.dp),
                        shape = RoundedCornerShape(16.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = PactPrimary,
                            contentColor = PactOnPrimary
                        )
                    ) {
                        Text(
                            text = "My Donations & Allocations",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }

                    HomeActionButton(title = "SMS Gateway Hub", onClick = onNavigateToSmsGateway)
                    HomeActionButton(title = "Offline Map", onClick = onNavigateToOfflineMap)

                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        color = PactSurface,
                        border = BorderStroke(1.dp, PactAccent)
                    ) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            Text(
                                text = "Donor Organization Access",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Bold,
                                color = PactTextPrimary
                            )
                            Text(
                                text = "Your account is authorized to view registered aid, match distributions, and crisis coverage maps. Field crisis intake and decoder tools are restricted to field coordinators.",
                                style = MaterialTheme.typography.bodySmall,
                                color = PactTextSecondary
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun HomeActionButton(
    title: String,
    onClick: () -> Unit
) {
    OutlinedButton(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().height(56.dp),
        shape = RoundedCornerShape(16.dp),
        border = BorderStroke(1.dp, PactAccent),
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = PactBackground,
            contentColor = PactTextPrimary
        )
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Medium
        )
    }
}