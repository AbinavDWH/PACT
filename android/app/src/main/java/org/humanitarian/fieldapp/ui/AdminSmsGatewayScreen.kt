package org.humanitarian.fieldapp.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowDownward
import androidx.compose.material.icons.filled.ArrowUpward
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.launch
import org.humanitarian.fieldapp.models.GatewayLogEntry
import org.humanitarian.fieldapp.models.OutboundSmsMessage
import org.humanitarian.fieldapp.models.RelayDirection
import org.humanitarian.fieldapp.models.RelayStatus
import org.humanitarian.fieldapp.sms.Checksum
import org.humanitarian.fieldapp.sms.SmsGatewayManager
import org.humanitarian.fieldapp.sms.SmsInboxReader
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

private val STATUS_GREEN = Color(0xFF2E7D32)
private val STATUS_BLUE = Color(0xFF1565C0)
private val STATUS_AMBER = Color(0xFFEF6C00)
private val STATUS_RED = Color(0xFFC62828)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminSmsGatewayScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    val isRunning by SmsGatewayManager.isRunning.collectAsState()
    val logs by SmsGatewayManager.logs.collectAsState()
    val stats by SmsGatewayManager.stats.collectAsState()
    val outboundQueue by SmsGatewayManager.outboundQueue.collectAsState()

    var selectedTab by remember { mutableIntStateOf(0) }
    val tabTitles = listOf("Relay Activity", "Outbox Queue", "Gateway Tools")

    // Permission state
    var hasReceiveSmsPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECEIVE_SMS) == PackageManager.PERMISSION_GRANTED
        )
    }
    var hasReadSmsPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.READ_SMS) == PackageManager.PERMISSION_GRANTED
        )
    }
    var hasSendSmsPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.SEND_SMS) == PackageManager.PERMISSION_GRANTED
        )
    }

    val permissionsLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { perms ->
        hasReceiveSmsPermission = perms[Manifest.permission.RECEIVE_SMS] ?: hasReceiveSmsPermission
        hasReadSmsPermission = perms[Manifest.permission.READ_SMS] ?: hasReadSmsPermission
        hasSendSmsPermission = perms[Manifest.permission.SEND_SMS] ?: hasSendSmsPermission
    }

    val allPermissionsGranted = hasReceiveSmsPermission && hasReadSmsPermission && hasSendSmsPermission

    // Auto-start gateway if permissions are granted and not already running
    LaunchedEffect(Unit) {
        if (allPermissionsGranted && !isRunning) {
            SmsGatewayManager.startGateway(context)
        }
    }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            text = "SMS Gateway Hub",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = PactTextPrimary
                        )
                        Text(
                            text = if (isRunning) "ENGINE RUNNING · RELAY ACTIVE" else "GATEWAY STOPPED",
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = if (isRunning) STATUS_GREEN else STATUS_RED
                        )
                    }
                },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text("Back", color = PactPrimary, fontWeight = FontWeight.SemiBold)
                    }
                },
                actions = {
                    TextButton(onClick = {
                        coroutineScope.launch {
                            SmsGatewayManager.pollAndSendOutboundSms(context)
                        }
                    }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Refresh", tint = PactPrimary)
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Poll Outbox", color = PactPrimary, fontWeight = FontWeight.SemiBold)
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PactSurface)
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // ──────────────── GATEWAY SWITCH & CONTROL CARD ────────────────
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(20.dp),
                color = PactSurface,
                border = BorderStroke(1.dp, if (isRunning) STATUS_GREEN else PactAccent)
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            Box(
                                modifier = Modifier
                                    .size(14.dp)
                                    .background(if (isRunning) STATUS_GREEN else STATUS_RED, CircleShape)
                            )
                            Text(
                                text = if (isRunning) "Mobile Gateway Active" else "Mobile Gateway Paused",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = PactTextPrimary
                            )
                        }

                        Button(
                            onClick = {
                                if (!allPermissionsGranted) {
                                    permissionsLauncher.launch(
                                        arrayOf(
                                            Manifest.permission.RECEIVE_SMS,
                                            Manifest.permission.READ_SMS,
                                            Manifest.permission.SEND_SMS
                                        )
                                    )
                                } else {
                                    SmsGatewayManager.toggleGateway(context)
                                }
                            },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (isRunning) STATUS_RED else STATUS_GREEN,
                                contentColor = Color.White
                            ),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Icon(
                                imageVector = if (isRunning) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                                contentDescription = null,
                                modifier = Modifier.size(18.dp)
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Text(if (isRunning) "Stop Gateway" else "Start Gateway")
                        }
                    }

                    Text(
                        text = "Acts as a cellular hardware bridge: automatically catches incoming crisis SMS on this phone and forwards to backend, while polling backend outbox to send real SMS via device SIM.",
                        style = MaterialTheme.typography.bodySmall,
                        color = PactTextSecondary
                    )

                    // Permission warning banner if missing
                    if (!allPermissionsGranted) {
                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            color = Color(0xFFFFF3E0),
                            border = BorderStroke(1.dp, STATUS_AMBER)
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = "SMS Permissions Required",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = STATUS_AMBER
                                    )
                                    Text(
                                        text = "Grant Receive, Read, and Send SMS permissions to enable automated GSM relay.",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = PactTextSecondary
                                    )
                                }
                                Button(
                                    onClick = {
                                        permissionsLauncher.launch(
                                            arrayOf(
                                                Manifest.permission.RECEIVE_SMS,
                                                Manifest.permission.READ_SMS,
                                                Manifest.permission.SEND_SMS
                                            )
                                        )
                                    },
                                    colors = ButtonDefaults.buttonColors(containerColor = STATUS_AMBER),
                                    shape = RoundedCornerShape(8.dp)
                                ) {
                                    Text("Grant", color = Color.White, fontWeight = FontWeight.Bold)
                                }
                            }
                        }
                    }
                }
            }

            // ──────────────── GATEWAY TARGET PHONE NUMBER CARD ────────────────
            var gatewayPhoneInput by remember { mutableStateOf(org.humanitarian.fieldapp.sms.GatewayConfig.getGatewayPhoneNumber(context)) }
            var isSaved by remember { mutableStateOf(false) }

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = PactSurface,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "Gateway Target Phone Number",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = PactTextPrimary
                    )
                    Text(
                        text = "When field workers have no internet, their devices automatically send SMS need reports to this number. Enter this device's SIM phone number.",
                        style = MaterialTheme.typography.bodySmall,
                        color = PactTextSecondary
                    )

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        OutlinedTextField(
                            value = gatewayPhoneInput,
                            onValueChange = {
                                gatewayPhoneInput = it
                                isSaved = false
                            },
                            label = { Text("Gateway SIM Number") },
                            singleLine = true,
                            shape = RoundedCornerShape(12.dp),
                            modifier = Modifier.weight(1f)
                        )

                        Button(
                            onClick = {
                                org.humanitarian.fieldapp.sms.GatewayConfig.setGatewayPhoneNumber(context, gatewayPhoneInput)
                                isSaved = true
                            },
                            colors = ButtonDefaults.buttonColors(
                                containerColor = if (isSaved) STATUS_GREEN else PactPrimary,
                                contentColor = Color.White
                            ),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Text(if (isSaved) "Saved" else "Save Number")
                        }
                    }
                }
            }

            // ──────────────── LIVE RELAY METRICS ROW ────────────────
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                MetricCard(
                    modifier = Modifier.weight(1f),
                    title = "Inbound (Phone->API)",
                    count = "${stats.inboundCount}",
                    color = STATUS_BLUE,
                    icon = Icons.Filled.ArrowDownward
                )
                MetricCard(
                    modifier = Modifier.weight(1f),
                    title = "Outbound (API->SIM)",
                    count = "${stats.outboundCount}",
                    color = STATUS_GREEN,
                    icon = Icons.Filled.ArrowUpward
                )
                MetricCard(
                    modifier = Modifier.weight(1f),
                    title = "Outbox Queue",
                    count = "${outboundQueue.size}",
                    color = STATUS_AMBER,
                    icon = Icons.Filled.Send
                )
            }

            // ──────────────── TABS: Activity, Outbox, Tools ────────────────
            ScrollableTabRow(
                selectedTabIndex = selectedTab,
                containerColor = PactSurface,
                contentColor = PactPrimary,
                edgePadding = 0.dp
            ) {
                tabTitles.forEachIndexed { index, title ->
                    Tab(
                        selected = selectedTab == index,
                        onClick = { selectedTab = index },
                        text = {
                            Text(
                                text = title,
                                fontWeight = if (selectedTab == index) FontWeight.Bold else FontWeight.Normal,
                                color = if (selectedTab == index) PactPrimary else PactTextSecondary
                            )
                        }
                    )
                }
            }

            // ──────────────── TAB CONTENTS ────────────────
            when (selectedTab) {
                0 -> RelayActivityTab(logs = logs, onClear = { SmsGatewayManager.clearLogs() })
                1 -> OutboxQueueTab(
                    queue = outboundQueue,
                    onSendAllNow = {
                        coroutineScope.launch {
                            SmsGatewayManager.pollAndSendOutboundSms(context)
                        }
                    }
                )
                2 -> GatewayToolsTab()
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// METRIC CARD COMPONENT
// ─────────────────────────────────────────────────────────────────────────────
@Composable
private fun MetricCard(
    modifier: Modifier = Modifier,
    title: String,
    count: String,
    color: Color,
    icon: androidx.compose.ui.graphics.vector.ImageVector
) {
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        color = PactSurface,
        border = BorderStroke(1.dp, PactAccent)
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = count,
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = color
                )
                Icon(imageVector = icon, contentDescription = null, tint = color, modifier = Modifier.size(18.dp))
            }
            Text(
                text = title,
                style = MaterialTheme.typography.bodySmall,
                color = PactTextSecondary,
                maxLines = 1
            )
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB 0: RELAY ACTIVITY LOG
// ─────────────────────────────────────────────────────────────────────────────
@Composable
private fun RelayActivityTab(logs: List<GatewayLogEntry>, onClear: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Live Gateway Activity (${logs.size})",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = PactTextPrimary
            )
            if (logs.isNotEmpty()) {
                TextButton(onClick = onClear) {
                    Text("Clear Logs", color = PactPrimary)
                }
            }
        }

        if (logs.isEmpty()) {
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = PactSurface,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Column(modifier = Modifier.padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Text("No SMS transactions yet", style = MaterialTheme.typography.bodyMedium, color = PactTextSecondary)
                    Text(
                        "Incoming SMS received on this phone or outbound allocations from the server will appear here automatically.",
                        style = MaterialTheme.typography.bodySmall,
                        color = PactTextSecondary,
                        modifier = Modifier.padding(top = 4.dp)
                    )
                }
            }
        } else {
            logs.forEach { entry ->
                GatewayLogCard(entry)
            }
        }
    }
}

@Composable
private fun GatewayLogCard(entry: GatewayLogEntry) {
    val isInbound = entry.direction == RelayDirection.INBOUND
    val timeFormat = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
    val formattedTime = timeFormat.format(Date(entry.timestamp))

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        color = PactSurface,
        border = BorderStroke(1.dp, PactAccent)
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Surface(
                        shape = RoundedCornerShape(6.dp),
                        color = if (isInbound) STATUS_BLUE.copy(alpha = 0.15f) else STATUS_GREEN.copy(alpha = 0.15f)
                    ) {
                        Text(
                            text = if (isInbound) "INBOUND · GSM->API" else "OUTBOUND · API->GSM",
                            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = if (isInbound) STATUS_BLUE else STATUS_GREEN
                        )
                    }

                    Text(
                        text = entry.fromTo,
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Bold,
                        color = PactTextPrimary
                    )
                }

                Text(
                    text = formattedTime,
                    style = MaterialTheme.typography.labelSmall,
                    color = PactTextSecondary
                )
            }

            // Raw payload box
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(8.dp),
                color = PactBackground,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Text(
                    text = entry.message,
                    modifier = Modifier.padding(8.dp),
                    fontFamily = FontFamily.Monospace,
                    style = MaterialTheme.typography.bodySmall,
                    color = PactPrimary
                )
            }

            // Status & Details
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = entry.details,
                    style = MaterialTheme.typography.bodySmall,
                    color = PactTextSecondary
                )

                Text(
                    text = when (entry.status) {
                        RelayStatus.FORWARDED_TO_SERVER -> "FORWARDED"
                        RelayStatus.SENT_VIA_GSM -> "SENT VIA GSM"
                        RelayStatus.RECEIVED -> "CAPTURED"
                        RelayStatus.PENDING -> "PENDING"
                        RelayStatus.FAILED -> "FAILED"
                    },
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = when (entry.status) {
                        RelayStatus.FORWARDED_TO_SERVER, RelayStatus.SENT_VIA_GSM -> STATUS_GREEN
                        RelayStatus.RECEIVED, RelayStatus.PENDING -> STATUS_BLUE
                        RelayStatus.FAILED -> STATUS_RED
                    }
                )
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB 1: OUTBOX QUEUE (SERVER -> GSM)
// ─────────────────────────────────────────────────────────────────────────────
@Composable
private fun OutboxQueueTab(queue: List<OutboundSmsMessage>, onSendAllNow: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Pending Outbound Queue (${queue.size})",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = PactTextPrimary
            )

            if (queue.isNotEmpty()) {
                Button(
                    onClick = onSendAllNow,
                    colors = ButtonDefaults.buttonColors(containerColor = PactPrimary, contentColor = PactOnPrimary),
                    shape = RoundedCornerShape(10.dp)
                ) {
                    Icon(Icons.Filled.Send, contentDescription = null, modifier = Modifier.size(16.dp))
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("Transmit All via SIM")
                }
            }
        }

        if (queue.isEmpty()) {
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = PactSurface,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Column(modifier = Modifier.padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Filled.CheckCircle, contentDescription = null, tint = STATUS_GREEN, modifier = Modifier.size(32.dp))
                    Spacer(modifier = Modifier.height(8.dp))
                    Text("All outbound SMS sent", style = MaterialTheme.typography.titleSmall, fontWeight = FontWeight.Bold, color = PactTextPrimary)
                    Text("When allocation plans or alerts are generated, they will queue here for GSM dispatch.", style = MaterialTheme.typography.bodySmall, color = PactTextSecondary)
                }
            }
        } else {
            queue.forEach { item ->
                OutboundMessageCard(item)
            }
        }
    }
}

@Composable
private fun OutboundMessageCard(item: OutboundSmsMessage) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(14.dp),
        color = PactSurface,
        border = BorderStroke(1.dp, PactAccent)
    ) {
        Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "To: ${item.toNumber}",
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Bold,
                    color = PactTextPrimary
                )
                Text(
                    text = item.type.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = STATUS_AMBER
                )
            }

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(8.dp),
                color = PactBackground,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Text(
                    text = item.message,
                    modifier = Modifier.padding(8.dp),
                    fontFamily = FontFamily.Monospace,
                    style = MaterialTheme.typography.bodySmall,
                    color = PactPrimary
                )
            }

            if (item.planId != null) {
                Text(
                    text = "Linked Plan: ${item.planId}",
                    style = MaterialTheme.typography.bodySmall,
                    color = PactTextSecondary
                )
            }
        }
    }
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB 2: MANUAL GATEWAY TOOLS & SIM TESTER
// ─────────────────────────────────────────────────────────────────────────────
@Composable
private fun GatewayToolsTab() {
    val context = LocalContext.current
    val coroutineScope = rememberCoroutineScope()

    var testPhone by remember { mutableStateOf("+919876543211") }
    var testMessage by remember { mutableStateOf("A|003|PLAN-101|CSR02|F|200|RA|4|${Checksum.xor("A|003|PLAN-101|CSR02|F|200|RA|4")}") }
    var sendStatusMessage by remember { mutableStateOf("") }

    var simSenderPhone by remember { mutableStateOf("+919876543210") }
    var simPayload by remember { mutableStateOf("N|001|NGO01|RA|F|300|H|${Checksum.xor("N|001|NGO01|RA|F|300|H")}") }
    var simStatusMessage by remember { mutableStateOf("") }

    var inboxScanCount by remember { mutableIntStateOf(0) }

    Column(verticalArrangement = Arrangement.spacedBy(16.dp)) {
        // ── TOOL 1: SEND REAL SMS VIA SIM ──
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            color = PactSurface,
            border = BorderStroke(1.dp, PactAccent)
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Transmit Real SMS via Mobile SIM", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = PactTextPrimary)
                Text("Physically sends an SMS message through this device's SIM card to a recipient number.", style = MaterialTheme.typography.bodySmall, color = PactTextSecondary)

                OutlinedTextField(
                    value = testPhone,
                    onValueChange = { testPhone = it },
                    label = { Text("Recipient Phone Number") },
                    singleLine = true,
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = testMessage,
                    onValueChange = { testMessage = it },
                    label = { Text("SMS Message Payload") },
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                )

                // Quick template buttons
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    OutlinedButton(
                        onClick = {
                            val body = "A|004|PLAN-102|GOV03|W|400|D1|6"
                            testMessage = "$body|${Checksum.xor(body)}"
                        },
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("Plan SMS", style = MaterialTheme.typography.bodySmall)
                    }

                    OutlinedButton(
                        onClick = {
                            val body = "S|005|PLAN-102|3"
                            testMessage = "$body|${Checksum.xor(body)}"
                        },
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("Status SMS", style = MaterialTheme.typography.bodySmall)
                    }
                }

                Button(
                    onClick = {
                        SmsGatewayManager.sendManualOutboundSms(context, testPhone, testMessage) { success, msg ->
                            sendStatusMessage = msg
                        }
                    },
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = PactPrimary, contentColor = PactOnPrimary)
                ) {
                    Icon(Icons.Filled.Send, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Send SMS via GSM Hardware")
                }

                if (sendStatusMessage.isNotBlank()) {
                    Text(
                        text = sendStatusMessage,
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Bold,
                        color = if (sendStatusMessage.contains("success", ignoreCase = true)) STATUS_GREEN else STATUS_RED
                    )
                }
            }
        }

        // ── TOOL 2: SIMULATE INCOMING SMS ──
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            color = PactSurface,
            border = BorderStroke(1.dp, PactAccent)
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Simulate Inbound SMS Message", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = PactTextPrimary)
                Text("Injects a test incoming SMS directly into the gateway relay pipeline to trigger server webhook processing.", style = MaterialTheme.typography.bodySmall, color = PactTextSecondary)

                OutlinedTextField(
                    value = simSenderPhone,
                    onValueChange = { simSenderPhone = it },
                    label = { Text("Simulated Sender Phone") },
                    singleLine = true,
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = simPayload,
                    onValueChange = { simPayload = it },
                    label = { Text("SMS Body Payload") },
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier.fillMaxWidth()
                )

                // Quick payload buttons
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    OutlinedButton(
                        onClick = {
                            val body = "N|008|NGO01|RA|F|300|H"
                            simPayload = "$body|${Checksum.xor(body)}"
                        },
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("Need (N)", style = MaterialTheme.typography.bodySmall)
                    }

                    OutlinedButton(
                        onClick = {
                            val body = "R|009|CSR02|RB|M|150|A"
                            simPayload = "$body|${Checksum.xor(body)}"
                        },
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("Resource (R)", style = MaterialTheme.typography.bodySmall)
                    }

                    OutlinedButton(
                        onClick = {
                            val body = "M|010|13.0827,80.2707|CR|9|F300"
                            simPayload = "$body|${Checksum.xor(body)}"
                        },
                        shape = RoundedCornerShape(8.dp)
                    ) {
                        Text("Marker (M)", style = MaterialTheme.typography.bodySmall)
                    }
                }

                Button(
                    onClick = {
                        SmsGatewayManager.simulateInboundSms(context, simSenderPhone, simPayload) { success, msg ->
                            simStatusMessage = msg
                        }
                    },
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = STATUS_BLUE, contentColor = Color.White)
                ) {
                    Icon(Icons.Filled.ArrowDownward, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Trigger Inbound Gateway Relay")
                }

                if (simStatusMessage.isNotBlank()) {
                    Text(
                        text = simStatusMessage,
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Bold,
                        color = if (simStatusMessage.contains("success", ignoreCase = true)) STATUS_GREEN else STATUS_RED
                    )
                }
            }
        }

        // ── TOOL 3: SCAN DEVICE INBOX ──
        Surface(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            color = PactSurface,
            border = BorderStroke(1.dp, PactAccent)
        ) {
            Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Scan Device SMS Inbox", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold, color = PactTextPrimary)
                Text("Scans telephony storage for un-relayed PACT SMS messages received while app was in the background.", style = MaterialTheme.typography.bodySmall, color = PactTextSecondary)

                Button(
                    onClick = {
                        coroutineScope.launch {
                            val list = SmsInboxReader.readRecentSms(context)
                            inboxScanCount = list.size
                            for (item in list) {
                                if (item.message.contains("|")) {
                                    SmsGatewayManager.processInboundSms(context, item.fromNumber, item.message)
                                }
                            }
                        }
                    },
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = PactAccent, contentColor = PactTextPrimary)
                ) {
                    Icon(Icons.Filled.Refresh, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Scan & Relay Recent SMS (${if (inboxScanCount > 0) "$inboxScanCount scanned" else "Scan Now"})")
                }
            }
        }
    }
}
