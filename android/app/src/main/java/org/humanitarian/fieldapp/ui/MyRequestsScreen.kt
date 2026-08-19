package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
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

private fun statusColor(status: String): Color {
    return when (status) {
        "pending" -> Color(0xFFFF9800)
        "accepted", "processing", "matched", "allocated", "completed" -> Color(0xFF4CAF50)
        "rejected", "duplicate" -> Color(0xFFF62440)
        else -> Color(0xFF7c6a58)
    }
}

private fun statusLabel(status: String): String {
    return when (status) {
        "pending" -> "PENDING REVIEW"
        "accepted" -> "APPROVED"
        "processing" -> "APPROVED · AGENT WORKING"
        "matched" -> "APPROVED · RESOURCES MATCHED"
        "allocated" -> "APPROVED · PLAN CREATED"
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
    var errorCount by remember { mutableStateOf(0) }

    LaunchedEffect(Unit) {
        while (true) {
            when (val res = ApiClient.getRequestsByOrg(ORG_ID)) {
                is ApiResult.Success -> {
                    requests = res.data
                    lastSync = "Live · ${res.data.size} request(s) · synced ${java.time.LocalTime.now()}"
                    errorCount = 0
                }
                is ApiResult.Error -> {
                    errorCount++
                    lastSync = "Backend unreachable (${errorCount} attempts)"
                }
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
                        Text(
                            "No requests found for $ORG_ID",
                            style = MaterialTheme.typography.bodyLarge,
                            color = PactTextSecondary
                        )
                        Text(
                            "Submit a field report to see it here.",
                            style = MaterialTheme.typography.bodySmall,
                            color = PactTextSecondary
                        )
                    }
                }
            }

            requests.forEach { req ->
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
                            Text(
                                text = statusLabel(req.status),
                                style = MaterialTheme.typography.labelMedium,
                                fontWeight = FontWeight.Bold,
                                color = statusColor(req.status)
                            )
                        }

                        Text(
                            text = "${req.type.uppercase()} · ${req.resource} × ${req.quantity}",
                            style = MaterialTheme.typography.bodyLarge,
                            color = PactTextPrimary
                        )

                        val coords = if (req.latitude != null && req.longitude != null)
                            String.format("GPS: %.4f, %.4f", req.latitude, req.longitude)
                        else "GPS: not attached"

                        Text(
                            text = coords,
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                            color = PactTextSecondary
                        )

                        if (req.createdAt.isNotBlank()) {
                            Text(
                                text = "Created: ${req.createdAt}",
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