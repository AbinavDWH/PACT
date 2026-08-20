package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
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
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import org.humanitarian.fieldapp.models.OrgRequest
import org.humanitarian.fieldapp.models.UserRole
import org.humanitarian.fieldapp.models.UserSession
import org.humanitarian.fieldapp.network.ApiClient
import org.humanitarian.fieldapp.network.ApiResult
import org.humanitarian.fieldapp.offline.LocalRequestItem
import org.humanitarian.fieldapp.offline.LocalRequestStore
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary

private val STATUS_GREEN = Color(0xFF2E7D32)
private val STATUS_ORANGE = Color(0xFFEF6C00)
private val STATUS_RED = Color(0xFFF62440)
private val STATUS_BLUE = Color(0xFF1565C0)
private val STATUS_PURPLE = Color(0xFF6A1B9A)

private fun getDisplayColor(status: String): Color {
    val s = status.uppercase()
    return when {
        s.contains("WAITING") || s.contains("PENDING") -> STATUS_ORANGE
        s.contains("ACCEPTED") || s.contains("APPROVED") -> STATUS_GREEN
        s.contains("ALLOCAT") || s.contains("MATCH") -> STATUS_BLUE
        s.contains("DELIVER") || s.contains("COMPLET") -> STATUS_PURPLE
        s.contains("REJECT") -> STATUS_RED
        else -> Color(0xFF7C6A58)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MyRequestsScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val session = UserSession.current
    val orgId = session?.organizationId ?: "DONOR01"
    val isDonor = session?.role == UserRole.DONOR_GROUP
    val titleText = if (isDonor) "My Donations & Allocations" else "My Requests"

    val localRequests by LocalRequestStore.requestsFlow.collectAsState()
    var serverRequests by remember { mutableStateOf<List<OrgRequest>>(emptyList()) }
    var syncStatusText by remember { mutableStateOf("Offline SMS Mode · Instant Local Updates") }

    val permissionLauncher = androidx.activity.compose.rememberLauncherForActivityResult(
        contract = androidx.activity.result.contract.ActivityResultContracts.RequestMultiplePermissions()
    ) { _ -> }

    // Initialize local store on start & verify permissions
    LaunchedEffect(Unit) {
        permissionLauncher.launch(
            arrayOf(
                android.Manifest.permission.RECEIVE_SMS,
                android.Manifest.permission.READ_SMS,
                android.Manifest.permission.SEND_SMS
            )
        )
        LocalRequestStore.init(context)
    }

    // Passive, non-spam background sync (every 10s if internet is reachable, no frequent SMS)
    LaunchedEffect(orgId) {
        while (true) {
            try {
                when (val res = ApiClient.getRequestsByOrg(orgId)) {
                    is ApiResult.Success -> {
                        serverRequests = res.data
                        syncStatusText = "Internet Active · ${res.data.size} server item(s) synced"
                    }
                    is ApiResult.Error -> {
                        syncStatusText = "Offline SMS Mode · Listening for reply SMS"
                    }
                }
            } catch (t: Throwable) {
                t.printStackTrace()
                syncStatusText = "Offline SMS Mode · Listening for reply SMS"
            }
            delay(10000)
        }
    }

    // Filter local requests for this org (or all for admin)
    val filteredLocal = if (session?.role == UserRole.ADMIN) {
        localRequests
    } else {
        localRequests.filter { it.organizationId.equals(orgId, ignoreCase = true) }
    }

    val coroutineScope = rememberCoroutineScope()

    val onConfirmHandover: (String?, String?) -> Unit = { planId, reqId ->
        LocalRequestStore.markHandedOver(context, planId, reqId)
        coroutineScope.launch {
            try {
                ApiClient.confirmHandover(planId, reqId, orgId)
                val res = ApiClient.getRequestsByOrg(orgId)
                if (res is ApiResult.Success) serverRequests = res.data
            } catch (t: Throwable) {
                t.printStackTrace()
            }
        }
    }

    val onConfirmReceipt: (String?, String?) -> Unit = { planId, reqId ->
        LocalRequestStore.markReceived(context, planId, reqId)
        coroutineScope.launch {
            try {
                ApiClient.confirmReceipt(planId, reqId, orgId)
                val res = ApiClient.getRequestsByOrg(orgId)
                if (res is ApiResult.Success) serverRequests = res.data
            } catch (t: Throwable) {
                t.printStackTrace()
            }
        }
    }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = { Text(titleText, fontWeight = FontWeight.SemiBold, color = PactTextPrimary) },
                navigationIcon = {
                    TextButton(onClick = onBack) {
                        Text("Back", color = PactPrimary, fontWeight = FontWeight.SemiBold)
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
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Status bar
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = syncStatusText,
                    style = MaterialTheme.typography.bodySmall,
                    color = PactTextSecondary
                )
                Text(
                    text = "${filteredLocal.size + serverRequests.size} total",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Bold,
                    color = PactPrimary
                )
            }

            if (filteredLocal.isEmpty() && serverRequests.isEmpty()) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    color = PactSurface,
                    border = BorderStroke(1.dp, PactAccent)
                ) {
                    Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            text = if (isDonor) "No donations found for $orgId" else "No requests found for $orgId",
                            style = MaterialTheme.typography.bodyLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = PactTextPrimary
                        )
                        Text(
                            text = "Submit a field report. It will be sent via SMS when offline with default status 'WAITING FOR RESPONSE' and update automatically when the gateway replies.",
                            style = MaterialTheme.typography.bodySmall,
                            color = PactTextSecondary
                        )
                    }
                }
            }

            // 1. Render Local & SMS Requests (with real-time SMS status)
            filteredLocal.forEach { item ->
                LocalRequestCard(
                    item = item,
                    isDonor = isDonor,
                    onConfirmHandover = onConfirmHandover,
                    onConfirmReceipt = onConfirmReceipt
                )
            }

            // 2. Render Server Requests not already in local list
            val localIds = filteredLocal.map { it.id }.toSet()
            serverRequests.filterNot { localIds.contains(it.id) }.forEach { req ->
                ServerRequestCard(
                    req = req,
                    isDonor = isDonor,
                    onConfirmHandover = onConfirmHandover,
                    onConfirmReceipt = onConfirmReceipt
                )
            }
        }
    }
}

@Composable
private fun LocalRequestCard(
    item: LocalRequestItem,
    isDonor: Boolean,
    onConfirmHandover: (String?, String?) -> Unit,
    onConfirmReceipt: (String?, String?) -> Unit
) {
    val context = LocalContext.current
    val statusColor = getDisplayColor(item.status)
    val isHandedOver = item.status.contains("DISPATCH") || item.status.contains("HAND") || item.status.contains("TRANSIT") || item.status.contains("DELIVER")
    val isDelivered = item.status.contains("DELIVER") || item.status.contains("COMPLET")

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = PactSurface,
        border = BorderStroke(1.dp, PactAccent)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            // Row 1: ID + Channel Badge + Status
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = item.id,
                        fontWeight = FontWeight.Bold,
                        color = PactTextPrimary
                    )
                    Surface(
                        shape = RoundedCornerShape(4.dp),
                        color = if (item.channel == "SMS") PactAccent else Color(0xFFE3F2FD)
                    ) {
                        Text(
                            text = item.channel,
                            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.Bold,
                            color = if (item.channel == "SMS") PactPrimary else STATUS_BLUE
                        )
                    }
                }

                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = statusColor.copy(alpha = 0.12f),
                    border = BorderStroke(1.dp, statusColor.copy(alpha = 0.4f))
                ) {
                    Text(
                        text = item.status,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = statusColor
                    )
                }
            }

            // Row 2: Resource & Quantity
            Text(
                text = "${item.resource} × ${item.quantity}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = PactTextPrimary
            )

            // Row 3: GPS / Location
            Text(
                text = "GPS: ${item.locationCode} · Org: ${item.organizationId} · Urgency: ${item.urgency}",
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
                color = PactTextSecondary
            )

            // Dynamic details based on SMS response status
            when {
                item.status.contains("ALLOCATED") && item.planId != null -> {
                    Spacer(modifier = Modifier.height(4.dp))
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        color = Color(0xFFE8F5E9),
                        border = BorderStroke(1.dp, STATUS_GREEN)
                    ) {
                        Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(
                                text = "ALLOCATION CONFIRMED · ${item.planId}",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = STATUS_GREEN
                            )
                            Text(
                                text = "${item.allocatedQty ?: item.quantity} units assigned from ${item.allocatedOrg ?: "Provider"} · ETA: ${item.etaHours ?: 4} hrs",
                                style = MaterialTheme.typography.bodyMedium,
                                fontWeight = FontWeight.Medium,
                                color = PactTextPrimary
                            )
                        }
                    }
                }

                item.status == "ACCEPTED" -> {
                    Spacer(modifier = Modifier.height(4.dp))
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        color = Color(0xFFE8F5E9),
                        border = BorderStroke(1.dp, STATUS_GREEN)
                    ) {
                        Text(
                            text = "Received by Gateway & Accepted by Coordination Server. Matching resources…",
                            modifier = Modifier.padding(10.dp),
                            style = MaterialTheme.typography.bodySmall,
                            color = STATUS_GREEN,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }

                item.status == "REJECTED" -> {
                    Spacer(modifier = Modifier.height(4.dp))
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        color = Color(0xFFFFEBEE),
                        border = BorderStroke(1.dp, STATUS_RED)
                    ) {
                        Column(modifier = Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(
                                text = "REQUEST REJECTED",
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = STATUS_RED
                            )
                            Text(
                                text = "Reason: ${item.rejectReason ?: "Invalid details or duplicate request"}",
                                style = MaterialTheme.typography.bodySmall,
                                color = Color(0xFFB71C1C),
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }

                item.status.contains("WAITING") -> {
                    val isLowUrgency = item.urgency.equals("Low", ignoreCase = true)
                    Spacer(modifier = Modifier.height(4.dp))
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        color = if (isLowUrgency) Color(0xFFF3E5F5) else Color(0xFFFFF8E1),
                        border = BorderStroke(1.dp, if (isLowUrgency) Color(0xFF8E24AA) else STATUS_ORANGE)
                    ) {
                        Column(modifier = Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(
                                text = if (isLowUrgency)
                                    "🤖 AI Urgency Assessment: Low · Held in WAITING state to conserve cellular SMS quota. Updates sync via Internet only."
                                else
                                    "Transmitted via SMS to Gateway (7401231450). Awaiting confirmation reply SMS.",
                                style = MaterialTheme.typography.bodySmall,
                                color = if (isLowUrgency) Color(0xFF6A1B9A) else STATUS_ORANGE,
                                fontWeight = FontWeight.Medium
                            )

                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(4.dp)
                            ) {
                                OutlinedButton(
                                    onClick = {
                                        LocalRequestStore.markAccepted(context, item.seq, "REQ-${item.seq.padStart(3, '0')}")
                                    },
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(8.dp),
                                    border = BorderStroke(1.dp, STATUS_GREEN)
                                ) {
                                    Text("Accept", style = MaterialTheme.typography.labelSmall, color = STATUS_GREEN)
                                }

                                Button(
                                    onClick = {
                                        LocalRequestStore.markAllocated(
                                            context = context,
                                            seq = item.seq,
                                            planId = "PLAN-${item.seq.padStart(3, '0')}",
                                            allocatedOrg = "CSR02",
                                            resourceCode = item.resourceCode,
                                            allocatedQty = item.quantity,
                                            etaHours = 4
                                        )
                                    },
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(8.dp),
                                    colors = ButtonDefaults.buttonColors(containerColor = STATUS_BLUE, contentColor = Color.White)
                                ) {
                                    Text("Allocate", style = MaterialTheme.typography.labelSmall)
                                }

                                OutlinedButton(
                                    onClick = {
                                        LocalRequestStore.markRejected(context, item.seq, "REQ-${item.seq.padStart(3, '0')}", "Duplicate or invalid supplies")
                                    },
                                    modifier = Modifier.weight(1f),
                                    shape = RoundedCornerShape(8.dp),
                                    border = BorderStroke(1.dp, STATUS_RED)
                                ) {
                                    Text("Reject", style = MaterialTheme.typography.labelSmall, color = STATUS_RED)
                                }
                            }
                        }
                    }
                }
            }

            // HANDOVER & RECEIPT ACTIONS
            Spacer(modifier = Modifier.height(4.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (isDonor) {
                    // Donor Side Action: Confirm Handed Over
                    if (!isHandedOver) {
                        Button(
                            onClick = { onConfirmHandover(item.planId, item.id) },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = STATUS_GREEN, contentColor = Color.White)
                        ) {
                            Text("✓ Confirm Handed Over", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                        }
                    } else {
                        Surface(
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            color = Color(0xFFE8F5E9),
                            border = BorderStroke(1.dp, STATUS_GREEN)
                        ) {
                            Text(
                                text = if (isDelivered) "✓ Confirmed Handed & Delivered" else "✓ Handed Over (In Transit)",
                                modifier = Modifier.padding(vertical = 8.dp),
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = STATUS_GREEN,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                } else {
                    // Needer Side Action: Confirm Received
                    if (!isDelivered) {
                        Button(
                            onClick = { onConfirmReceipt(item.planId, item.id) },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = STATUS_BLUE, contentColor = Color.White)
                        ) {
                            Text("✓ Confirm Received", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                        }
                    } else {
                        Surface(
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            color = Color(0xFFE8F5E9),
                            border = BorderStroke(1.dp, STATUS_GREEN)
                        ) {
                            Text(
                                text = "✓ Received Successfully",
                                modifier = Modifier.padding(vertical = 8.dp),
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = STATUS_GREEN,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }
            }

            // Raw SMS payload snippet
            if (item.rawPayload.isNotBlank()) {
                Text(
                    text = "SMS: ${item.rawPayload}",
                    style = MaterialTheme.typography.labelSmall,
                    fontFamily = FontFamily.Monospace,
                    color = PactTextSecondary
                )
            }
        }
    }
}

@Composable
private fun ServerRequestCard(
    req: OrgRequest,
    isDonor: Boolean,
    onConfirmHandover: (String?, String?) -> Unit,
    onConfirmReceipt: (String?, String?) -> Unit
) {
    val statusColor = getDisplayColor(req.status)
    val isHandedOver = req.status.equals("in_transit", ignoreCase = true) ||
                       req.status.equals("dispatched", ignoreCase = true) ||
                       req.status.equals("handed_over", ignoreCase = true) ||
                       req.status.equals("delivered", ignoreCase = true) ||
                       req.status.equals("completed", ignoreCase = true)
    val isDelivered = req.status.equals("delivered", ignoreCase = true) || req.status.equals("completed", ignoreCase = true)

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = PactSurface,
        border = BorderStroke(1.dp, PactAccent)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(req.id, fontWeight = FontWeight.Bold, color = PactTextPrimary)
                Surface(
                    shape = RoundedCornerShape(8.dp),
                    color = statusColor.copy(alpha = 0.12f),
                    border = BorderStroke(1.dp, statusColor.copy(alpha = 0.4f))
                ) {
                    Text(
                        text = req.status.uppercase(),
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = statusColor
                    )
                }
            }

            Text(
                text = "${req.type.uppercase()} · ${req.resource} × ${req.quantity}",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = PactTextPrimary
            )

            val coords = if (req.latitude != null && req.longitude != null)
                String.format(java.util.Locale.US, "GPS: %.4f, %.4f", req.latitude, req.longitude)
            else "Location: ${req.locationCode ?: "RA"}"

            Text(
                text = coords,
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
                color = PactTextSecondary
            )

            val totalMatched = req.totalMatched ?: req.matches.sumOf { it.quantity }

            if (req.status.equals("rejected", ignoreCase = true)) {
                Spacer(modifier = Modifier.height(4.dp))
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFFFFEBEE),
                    border = BorderStroke(1.dp, STATUS_RED)
                ) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = "AI AGENT: AUTO-REJECTED",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = STATUS_RED
                        )
                        Text(
                            text = "Reason: ${req.rejectReason ?: "Excessive quantity, frequency limit, or medical quota violation"}",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Medium,
                            color = Color(0xFFB71C1C)
                        )
                    }
                }
            } else if (req.status.equals("waiting", ignoreCase = true) || (req.type.equals("need", ignoreCase = true) && totalMatched < req.quantity)) {
                Spacer(modifier = Modifier.height(4.dp))
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFFFFF8E1),
                    border = BorderStroke(1.dp, STATUS_ORANGE)
                ) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = "AI CHECK: WAITING (R < N · SUPPLY DEFICIT)",
                            style = MaterialTheme.typography.labelMedium,
                            fontWeight = FontWeight.Bold,
                            color = STATUS_ORANGE
                        )
                        Text(
                            text = "Available Resource: $totalMatched · Requested Need: ${req.quantity}. Request is kept in WAITING status until additional donor inventory is registered.",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.Medium,
                            color = PactTextPrimary
                        )
                    }
                }
            } else if (req.matches.isNotEmpty()) {
                val coverage = if (req.quantity > 0) (totalMatched * 100 / req.quantity) else 0

                Spacer(modifier = Modifier.height(4.dp))
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFFE8F5E9),
                    border = BorderStroke(1.dp, STATUS_GREEN)
                ) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = if (req.planId != null) "ALLOCATED · ${req.planId}" else "ALLOCATED",
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.Bold,
                            color = STATUS_GREEN
                        )
                        Text(
                            text = "$totalMatched of ${req.quantity} units covered ($coverage%)",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                            color = PactTextPrimary
                        )
                    }
                }
            }

            // HANDOVER & RECEIPT ACTIONS (SERVER CARD)
            Spacer(modifier = Modifier.height(4.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                if (isDonor) {
                    if (!isHandedOver) {
                        Button(
                            onClick = { onConfirmHandover(req.planId, req.id) },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = STATUS_GREEN, contentColor = Color.White)
                        ) {
                            Text("✓ Confirm Handed Over", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                        }
                    } else {
                        Surface(
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            color = Color(0xFFE8F5E9),
                            border = BorderStroke(1.dp, STATUS_GREEN)
                        ) {
                            Text(
                                text = if (isDelivered) "✓ Confirmed Handed & Delivered" else "✓ Handed Over (In Transit)",
                                modifier = Modifier.padding(vertical = 8.dp),
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = STATUS_GREEN,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                } else {
                    if (!isDelivered) {
                        Button(
                            onClick = { onConfirmReceipt(req.planId, req.id) },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = STATUS_BLUE, contentColor = Color.White)
                        ) {
                            Text("✓ Confirm Received", style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                        }
                    } else {
                        Surface(
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(8.dp),
                            color = Color(0xFFE8F5E9),
                            border = BorderStroke(1.dp, STATUS_GREEN)
                        ) {
                            Text(
                                text = "✓ Received Successfully",
                                modifier = Modifier.padding(vertical = 8.dp),
                                style = MaterialTheme.typography.labelSmall,
                                fontWeight = FontWeight.Bold,
                                color = STATUS_GREEN,
                                textAlign = TextAlign.Center
                            )
                        }
                    }
                }
            }
        }
    }
}