package org.humanitarian.fieldapp.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
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
fun SmsFallbackScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    var queuedReports by remember { mutableStateOf(OfflineQueue.getQueuedReports(context)) }
    var isSyncing by remember { mutableStateOf(false) }
    var syncMessage by remember { mutableStateOf("") }

    val queueSize = queuedReports.size

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "SMS Fallback Queue",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = PactTextPrimary
                    )
                },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text(text = "Back", color = PactPrimary, fontWeight = FontWeight.SemiBold)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = PactSurface,
                    titleContentColor = PactTextPrimary,
                    navigationIconContentColor = PactPrimary
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
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(24.dp),
                color = PactSurface,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "Queue Status",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = PactTextPrimary
                    )
                    Text(
                        text = if (queueSize == 0) {
                            "No pending reports. All field reports are synced."
                        } else {
                            "$queueSize pending report(s) waiting for network sync or manual SMS transmission."
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = PactTextSecondary
                    )
                }
            }

            if (queueSize > 0) {
                // SYNC NOW BUTTON
                Button(
                    onClick = {
                        isSyncing = true
                        syncMessage = ""
                        coroutineScope.launch {
                            val result = SyncManager.syncQueue(context)
                            queuedReports = OfflineQueue.getQueuedReports(context)
                            isSyncing = false
                            syncMessage = when {
                                result.synced > 0 && result.failed == 0 ->
                                    "${result.synced} report(s) synced to coordination backend."
                                result.synced > 0 && result.failed > 0 ->
                                    "${result.synced} synced. ${result.failed} still queued (backend unreachable for those)."
                                else ->
                                    "Sync failed. Backend unreachable. Reports remain safely queued."
                            }
                        }
                    },
                    enabled = !isSyncing,
                    modifier = Modifier
                        .fillMaxWidth()
                        .size(56.dp)
                        .then(Modifier.fillMaxWidth()),
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PactPrimary,
                        contentColor = PactOnPrimary
                    )
                ) {
                    if (isSyncing) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(20.dp),
                                color = PactOnPrimary,
                                strokeWidth = 3.dp
                            )
                            Text(
                                text = "Syncing...",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold
                            )
                        }
                    } else {
                        Text(
                            text = "Sync Now",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold
                        )
                    }
                }

                if (syncMessage.isNotBlank()) {
                    Text(
                        text = syncMessage,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        color = PactPrimary
                    )
                }
            }

            if (queueSize > 0) {
                queuedReports.forEachIndexed { index, queued ->
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(24.dp),
                        color = PactSurface,
                        border = BorderStroke(1.dp, PactAccent)
                    ) {
                        Column(
                            modifier = Modifier.padding(20.dp),
                            verticalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Text(
                                text = "Report ${index + 1}",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                                color = PactTextPrimary
                            )

                            Text(
                                text = "Location: ${queued.report.locationCode} | Resource: ${queued.report.resourceCode} | Qty: ${queued.report.quantity}",
                                style = MaterialTheme.typography.bodyMedium,
                                color = PactTextSecondary
                            )

                            Text(
                                text = "Canonical SMS Payload",
                                style = MaterialTheme.typography.labelLarge,
                                color = PactTextSecondary
                            )

                            Surface(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp),
                                color = PactBackground,
                                border = BorderStroke(1.dp, PactAccent)
                            ) {
                                Text(
                                    text = queued.smsPayload.ifBlank { "Payload missing" },
                                    modifier = Modifier.padding(16.dp),
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontFamily = FontFamily.Monospace,
                                    color = PactTextPrimary
                                )
                            }

                            if (queued.smsPayload.isNotBlank()) {
                                OutlinedButton(
                                    onClick = {
                                        val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                        val clip = ClipData.newPlainText("SMS Payload", queued.smsPayload)
                                        clipboard.setPrimaryClip(clip)
                                        Toast.makeText(context, "SMS payload copied", Toast.LENGTH_SHORT).show()
                                    },
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(16.dp),
                                    border = BorderStroke(1.dp, PactAccent),
                                    colors = ButtonDefaults.outlinedButtonColors(
                                        containerColor = PactBackground,
                                        contentColor = PactTextPrimary
                                    )
                                ) {
                                    Text(
                                        text = "Copy Payload",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Medium
                                    )
                                }
                            }
                        }
                    }
                }

                OutlinedButton(
                    onClick = {
                        OfflineQueue.clearQueue(context)
                        queuedReports = OfflineQueue.getQueuedReports(context)
                        syncMessage = ""
                        Toast.makeText(context, "Queue cleared manually", Toast.LENGTH_SHORT).show()
                    },
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    border = BorderStroke(1.dp, PactPrimary),
                    colors = ButtonDefaults.outlinedButtonColors(
                        containerColor = PactBackground,
                        contentColor = PactPrimary
                    )
                ) {
                    Text(
                        text = "Clear Queue Manually",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium
                    )
                }
            }
        }
    }
}