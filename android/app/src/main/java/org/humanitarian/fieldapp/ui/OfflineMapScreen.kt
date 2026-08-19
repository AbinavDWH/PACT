package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.delay
import org.humanitarian.fieldapp.models.MapMarker
import org.humanitarian.fieldapp.network.ApiClient
import org.humanitarian.fieldapp.network.ApiResult
import org.humanitarian.fieldapp.sms.SmsDecoder
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker
import java.util.UUID

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OfflineMapScreen(onBack: () -> Unit) {
    var smsInput by remember { mutableStateOf("M|008|23.2599,77.4126|CR|9|F300|7B") }
    var markers by remember { mutableStateOf(listOf<MapMarker>()) }
    var errorMessage by remember { mutableStateOf("") }
    var pollingStatus by remember { mutableStateOf("Waiting for SMS...") }

    // BACKGROUND FAKE SMS POLLING
    LaunchedEffect(Unit) {
        while (true) {
            try {
                val res = ApiClient.getSmsInbox()
                if (res is ApiResult.Success && res.data.isNotEmpty()) {
                    for (sms in res.data) {
                        val decoded = SmsDecoder.decode(sms)
                        if (decoded.valid && decoded.typeCode == "M") {
                            val coords = decoded.fields["Coordinates"]?.split(",")
                            val lat = coords?.getOrNull(0)?.toDoubleOrNull() ?: 0.0
                            val lon = coords?.getOrNull(1)?.toDoubleOrNull() ?: 0.0
                            val newMarker = MapMarker(
                                id = UUID.randomUUID().toString(),
                                type = decoded.fields["Marker Type"] ?: "Unknown",
                                latitude = lat, longitude = lon,
                                severity = decoded.fields["Severity"]?.toIntOrNull() ?: 0,
                                data = decoded.fields["Data"] ?: ""
                            )
                            markers = markers + newMarker
                            pollingStatus = "Plotted new SMS marker!"
                        }
                    }
                    ApiClient.clearInbox()
                } else {
                    pollingStatus = "Listening for backend SMS..."
                }
            } catch (e: Exception) {
                pollingStatus = "Network error"
            }
            delay(3000) // Poll every 3 seconds
        }
    }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = { Text(text = "Live Tactical Map", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold, color = PactTextPrimary) },
                navigationIcon = { TextButton(onClick = onBack) { Text(text = "Back", color = PactPrimary, fontWeight = FontWeight.SemiBold) } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PactSurface, titleContentColor = PactTextPrimary, navigationIconContentColor = PactPrimary)
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier.fillMaxSize().padding(padding).verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(24.dp), color = PactSurface, border = BorderStroke(1.dp, PactAccent)) {
                Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(text = "Live Map & SMS Sync", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold, color = PactTextPrimary)
                    Text(text = pollingStatus, style = MaterialTheme.typography.bodyMedium, color = PactPrimary, fontWeight = FontWeight.Bold)
                }
            }

            // FREE OSM MAP VIEW
            Surface(
                modifier = Modifier.fillMaxWidth().height(400.dp),
                shape = RoundedCornerShape(24.dp),
                color = PactSurface,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                AndroidView(
                    factory = { context ->
                        MapView(context).apply {
                            setTileSource(TileSourceFactory.MAPNIK)
                            controller.setZoom(10.0)
                            controller.setCenter(GeoPoint(23.2599, 77.4126)) // Default center
                        }
                    },
                    update = { mapView ->
                        mapView.overlays.clear()
                        markers.forEach { m ->
                            val marker = Marker(mapView)
                            marker.position = GeoPoint(m.latitude, m.longitude)
                            marker.title = "${m.type} (Sev: ${m.severity})"
                            marker.snippet = m.data
                            marker.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM)
                            mapView.overlays.add(marker)
                        }
                        mapView.invalidate()
                    },
                    modifier = Modifier.fillMaxSize()
                )
            }

            // MANUAL OVERRIDE FOR DEMO
            OutlinedTextField(value = smsInput, onValueChange = { smsInput = it }, label = { Text("Manual SMS Payload") }, minLines = 2, shape = RoundedCornerShape(16.dp), modifier = Modifier.fillMaxWidth())
            Button(
                onClick = {
                    errorMessage = ""
                    val decoded = SmsDecoder.decode(smsInput)
                    if (decoded.valid && decoded.typeCode == "M") {
                        val coords = decoded.fields["Coordinates"]?.split(",")
                        val lat = coords?.getOrNull(0)?.toDoubleOrNull() ?: 0.0
                        val lon = coords?.getOrNull(1)?.toDoubleOrNull() ?: 0.0
                        markers = markers + MapMarker(UUID.randomUUID().toString(), decoded.fields["Marker Type"] ?: "Unknown", lat, lon, decoded.fields["Severity"]?.toIntOrNull() ?: 0, decoded.fields["Data"] ?: "")
                    } else { errorMessage = decoded.error.ifBlank { "Invalid marker payload." } }
                },
                modifier = Modifier.fillMaxWidth().height(56.dp), shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = PactPrimary, contentColor = PactOnPrimary)
            ) { Text("Decode & Plot Manually", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold) }

            if (errorMessage.isNotBlank()) Text(text = errorMessage, color = PactPrimary, fontWeight = FontWeight.Medium)

            if (markers.isNotEmpty()) {
                Text(text = "Active Markers (${markers.size})", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold, color = PactTextPrimary)
                markers.takeLast(3).reversed().forEach { marker ->
                    Surface(modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp), color = PactBackground, border = BorderStroke(1.dp, PactAccent)) {
                        Row(modifier = Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Surface(modifier = Modifier.size(16.dp), shape = CircleShape, color = getMarkerColor(marker.type)) {}
                            Column {
                                Text(text = "${marker.type} (Sev: ${marker.severity})", style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold, color = PactTextPrimary)
                                Text(text = "Lat: ${marker.latitude}, Lon: ${marker.longitude} | ${marker.data}", style = MaterialTheme.typography.bodySmall, fontFamily = FontFamily.Monospace, color = PactTextSecondary)
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun getMarkerColor(type: String): Color {
    return when (type.lowercase()) {
        "crisis zone", "cr" -> Color(0xFFF62440)
        "resource point", "rs" -> Color(0xFF2196F3)
        "medical point", "md" -> Color(0xFF4CAF50)
        "shelter", "sh" -> Color(0xFF9C27B0)
        else -> Color(0xFFFF9800)
    }
}