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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import org.humanitarian.fieldapp.models.OrgRequest
import org.humanitarian.fieldapp.network.ApiClient
import org.humanitarian.fieldapp.network.ApiResult
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary

private val ORG_ID = "NGO01"

private val STATUS_GREEN = Color(0xFF4CAF50)
private val STATUS_ORANGE = Color(0xFFFF9800)
private val STATUS_RED = Color(0xFFF62440)
private val STATUS_BLUE = Color(0xFF2196F3)

private fun statusColor(status: String): Color {
    return when (status) {
        "pending" -> STATUS_ORANGE
        "accepted", "processing" -> STATUS_BLUE
        "matched", "allocated", "completed" -> STATUS_GREEN
        "rejected", "duplicate" -> STATUS_RED
        else -> Color(0xFF7c6a58)
    }
}

private fun statusLabel(status: String): String {
    return when (status) {
        "pending" -> "PENDING REVIEW"
        "accepted" -> "APPROVED"
        "processing" -> "APPROVED · AGENT WORKING"
        "matched" -> "RESOURCES MATCHED"
        "allocated" -> "ALLOCATED · PLAN CREATED"
        "completed" -> "DELIVERED"
        "rejected" -> "REJECTED"
        "duplicate" -> "DUPLICATE"
        else -> status.uppercase()
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MyRequestsScreen(onBack: () -> Unit) {
    var requests by remember { mutableStateOf<List<OrgRequest>>(emptyList()) }
    var lastSync by remember { mutableStateOf("Loading…") }

    // Poll every 3 seconds — after Accept on web, status + allocation update here automatically
    LaunchedEffect(Unit) {
        while (true) {
            when (val res = ApiClient.getRequestsByOrg(ORG_ID)) {
                is ApiResult.Success -> {
                    requests = res.data
                    lastSync = "Live · ${res.data.size} request(s) · synced"
                }
                is ApiResult.Error -> lastSync = "Backend unreachable"
            }
            delay(3000)
        }
    }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = { Text("My Requests", fontWeight = FontWeight.SemiBold, color = PactTextPrimary) },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back", color = PactPrimary, fontWeight = FontWeight.SemiBold) } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PactSurface)
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(lastSync, style = MaterialTheme.typography.bodySmall, color = PactTextSecondary)

            if (requests.isEmpty()) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    color = PactSurface,
                    border = BorderStroke(1.dp, PactAccent)
                ) {
                    Column(modifier = Modifier.padding(20.dp)) {
                        Text("No requests found for $ORG_ID", style = MaterialTheme.typography.bodyLarge, color = PactTextSecondary)
                        Text("Submit a field report to see it here.", style = MaterialTheme.typography.bodySmall, color = PactTextSecondary)
                    }
                }
            }

            requests.forEach { req ->
                RequestCard(req)
            }
        }
    }
}

@Composable
private fun RequestCard(req: OrgRequest) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = PactSurface,
        border = BorderStroke(1.dp, PactAccent)
    ) {
        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            // Row 1: ID + live status badge
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(req.id, fontWeight = FontWeight.Bold, color = PactTextPrimary)
                Text(
                    text = statusLabel(req.status),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.Bold,
                    color = statusColor(req.status)
                )
            }

            // Row 2: resource line
            Text(
                text = "${req.type.uppercase()} · ${req.resource} × ${req.quantity}",
                style = MaterialTheme.typography.bodyLarge,
                color = PactTextPrimary
            )

            // Row 3: GPS coordinates
            val coords = if (req.latitude != null && req.longitude != null)
                String.format("GPS: %.4f, %.4f", req.latitude, req.longitude)
            else "GPS: not attached"
            Text(
                text = coords,
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
                color = PactTextSecondary
            )

            // ── ALLOCATION RESULT (appears after Accept + agent pipeline) ──
            if (req.matches.isNotEmpty()) {
                val totalMatched = req.totalMatched ?: req.matches.sumOf { it.quantity }
                val coverage = if (req.quantity > 0) (totalMatched * 100 / req.quantity) else 0
                val fullyCovered = totalMatched >= req.quantity

                Spacer(modifier = Modifier.height(4.dp))
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = if (fullyCovered) Color(0xFFE8F5E9) else Color(0xFFFFF8E1),
                    border = BorderStroke(1.dp, PactAccent)
                ) {
                    Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(
                            text = if (req.status == "allocated" || req.status == "completed") {
                                if (req.planId != null) "ALLOCATED · ${req.planId}" else "ALLOCATED"
                            } else {
                                "RESOURCES MATCHED"
                            },
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.Bold,
                            color = if (fullyCovered) Color(0xFF2E7D32) else Color(0xFFEF6C00)
                        )

                        Text(
                            text = "$totalMatched of ${req.quantity} units covered ($coverage%)",
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Medium,
                            color = PactTextPrimary
                        )

                        req.matches.forEach { m ->
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween
                            ) {
                                Text(
                                    text = m.organizationId,
                                    style = MaterialTheme.typography.bodyMedium,
                                    fontWeight = FontWeight.Medium,
                                    color = PactTextPrimary
                                )
                                Text(
                                    text = "${m.quantity} units · ETA ${m.etaHours}h",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = PactTextSecondary
                                )
                            }
                        }
                    }
                }
            } else if (req.status == "allocated" || req.status == "matched") {
                // Pipeline finished but no suppliers had this resource
                Spacer(modifier = Modifier.height(4.dp))
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    color = Color(0xFFFFEBEE),
                    border = BorderStroke(1.dp, PactAccent)
                ) {
                    Text(
                        text = "No suppliers found — needs replanning or new donor registration",
                        modifier = Modifier.padding(12.dp),
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        color = STATUS_RED
                    )
                }
            } else if (req.status == "accepted" || req.status == "processing") {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Agent pipeline running — matching providers…",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                    color = STATUS_BLUE
                )
            } else if (req.status == "rejected") {
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Request was rejected during validation",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                    color = STATUS_RED
                )
            }
        }
    }
}