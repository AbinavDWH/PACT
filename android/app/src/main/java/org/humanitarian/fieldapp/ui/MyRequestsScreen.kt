package org.humanitarian.fieldapp.ui

import android.text.format.DateUtils
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.humanitarian.fieldapp.models.FieldReport
import org.humanitarian.fieldapp.offline.OfflineQueue
import org.humanitarian.fieldapp.offline.QueuedReport
import org.humanitarian.fieldapp.offline.SubmittedReport
import org.humanitarian.fieldapp.offline.SubmittedReports
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
fun MyRequestsScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var queued by remember { mutableStateOf<List<QueuedReport>>(emptyList()) }
    var sent by remember { mutableStateOf<List<SubmittedReport>>(emptyList()) }
    var busy by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf("") }

    val reload: () -> Unit = {
        queued = OfflineQueue.getQueuedReports(context)
        sent = SubmittedReports.list(context)
    }

    LaunchedEffect(Unit) { reload() }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "My Requests",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = PactTextPrimary
                    )
                },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text(
                            text = "Back",
                            color = PactPrimary,
                            fontWeight = FontWeight.SemiBold
                        )
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
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 20.dp, vertical = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(bottom = 16.dp)
        ) {
            // Action bar
            item {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    color = PactSurface,
                    border = BorderStroke(1.dp, PactAccent)
                ) {
                    androidx.compose.foundation.layout.Column(
                        modifier = Modifier.padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(
                            text = "${queued.size} queued · ${sent.size} sent",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = PactTextPrimary
                        )
                        Text(
                            text = "Queued reports auto-sync when internet returns. Use Sync Now to force.",
                            style = MaterialTheme.typography.bodySmall,
                            color = PactTextSecondary
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = {
                                    if (busy) return@Button
                                    busy = true
                                    statusMessage = ""
                                    scope.launch {
                                        val result = SyncManager.syncQueue(context)
                                        statusMessage = when {
                                            result.synced > 0 -> "${result.synced} report(s) synced."
                                            result.failed > 0 -> "Sync failed (${result.failed} left). Check connectivity."
                                            else -> "Nothing to sync."
                                        }
                                        reload()
                                        busy = false
                                    }
                                },
                                enabled = !busy && queued.isNotEmpty(),
                                modifier = Modifier.weight(1f).height(44.dp),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(
                                    containerColor = PactPrimary, contentColor = PactOnPrimary
                                )
                            ) {
                                Text("Sync Now", fontWeight = FontWeight.SemiBold)
                            }

                            OutlinedButton(
                                onClick = {
                                    SubmittedReports.clear(context)
                                    statusMessage = "Sent history cleared."
                                    reload()
                                },
                                enabled = sent.isNotEmpty(),
                                modifier = Modifier.weight(1f).height(44.dp),
                                shape = RoundedCornerShape(12.dp),
                                border = BorderStroke(1.dp, PactAccent),
                                colors = ButtonDefaults.outlinedButtonColors(
                                    containerColor = PactBackground, contentColor = PactTextPrimary
                                )
                            ) {
                                Text("Clear sent", fontWeight = FontWeight.Medium)
                            }
                        }
                        if (statusMessage.isNotBlank()) {
                            Text(
                                text = statusMessage,
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.Medium,
                                color = PactPrimary
                            )
                        }
                    }
                }
            }

            // Queued section
            if (queued.isNotEmpty()) {
                item {
                    SectionHeader(title = "Queued (not yet synced)", count = queued.size)
                }
                items(queued, key = { it.smsPayload }) { q ->
                    RequestCard(
                        statusLabel = "QUEUED",
                        statusColor = PactPrimary,
                        report = q.report,
                        subline = q.smsPayload,
                        sublineMono = true,
                        footer = "Waiting for internet or next auto-sync."
                    )
                }
            }

            // Sent section
            if (sent.isNotEmpty()) {
                item {
                    SectionHeader(title = "Recently sent", count = sent.size)
                }
                items(sent, key = { "${it.needId}-${it.submittedAt}" }) { s ->
                    val ago = DateUtils.getRelativeTimeSpanString(
                        s.submittedAt, System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS
                    ).toString()
                    RequestCard(
                        statusLabel = "SENT",
                        statusColor = PactTextSecondary,
                        report = s.report,
                        subline = "Backend ID: ${s.needId}",
                        sublineMono = false,
                        footer = ago
                    )
                }
            }

            // Empty state
            if (queued.isEmpty() && sent.isEmpty()) {
                item {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        color = PactSurface,
                        border = BorderStroke(1.dp, PactAccent)
                    ) {
                        androidx.compose.foundation.layout.Column(
                            modifier = Modifier.padding(24.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Text(
                                text = "No requests yet",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.SemiBold,
                                color = PactTextPrimary
                            )
                            Text(
                                text = "Submit a Field Report and it will appear here, whether it reached the backend or was queued for later.",
                                style = MaterialTheme.typography.bodyMedium,
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
private fun SectionHeader(title: String, count: Int) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp, bottom = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        Text(
            text = title,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.SemiBold,
            color = PactTextSecondary
        )
        Surface(
            shape = RoundedCornerShape(8.dp),
            color = PactAccent
        ) {
            Text(
                text = count.toString(),
                modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                style = MaterialTheme.typography.labelMedium,
                fontWeight = FontWeight.SemiBold,
                color = PactTextPrimary
            )
        }
    }
}

@Composable
private fun RequestCard(
    statusLabel: String,
    statusColor: androidx.compose.ui.graphics.Color,
    report: FieldReport,
    subline: String,
    sublineMono: Boolean,
    footer: String
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = PactSurface,
        border = BorderStroke(1.dp, PactAccent)
    ) {
        androidx.compose.foundation.layout.Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = statusLabel,
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Bold,
                    color = statusColor
                )
                Text(
                    text = "${report.urgencyCode} urgency",
                    style = MaterialTheme.typography.labelMedium,
                    color = PactTextSecondary
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text(
                    text = "${report.quantity} x ${report.resourceCode}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = PactTextPrimary
                )
                Text(
                    text = "${report.organizationId} @ ${report.locationCode}",
                    style = MaterialTheme.typography.bodyMedium,
                    color = PactTextSecondary
                )
            }

            if (report.notes.isNotBlank()) {
                Text(
                    text = report.notes,
                    style = MaterialTheme.typography.bodySmall,
                    color = PactTextSecondary
                )
            }

            Text(
                text = subline,
                style = MaterialTheme.typography.bodySmall,
                fontFamily = if (sublineMono) FontFamily.Monospace else FontFamily.Default,
                color = PactTextPrimary
            )

            Text(
                text = footer,
                style = MaterialTheme.typography.labelSmall,
                color = PactTextSecondary
            )
        }
    }
}