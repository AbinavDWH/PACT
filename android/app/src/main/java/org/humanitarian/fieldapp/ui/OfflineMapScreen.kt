package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
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
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.humanitarian.fieldapp.models.MapMarker
import org.humanitarian.fieldapp.sms.SmsDecoder
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary
import java.util.UUID

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun OfflineMapScreen(
    onBack: () -> Unit
) {
    var smsInput by remember { mutableStateOf("M|008|23.2599,77.4126|CR|9|F300|7B") }
    var markers by remember { mutableStateOf(listOf<MapMarker>()) }
    var errorMessage by remember { mutableStateOf("") }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Offline Tactical Map",
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
                        text = "SMS Map Update",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = PactTextPrimary
                    )
                    Text(
                        text = "Paste an SMS marker payload to plot it on the cached offline map. Map tiles are pre-cached; only coordinates are transferred via SMS.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = PactTextSecondary
                    )
                }
            }

            OutlinedTextField(
                value = smsInput,
                onValueChange = { smsInput = it },
                label = { Text("Marker SMS Payload") },
                supportingText = { Text("Example: M|008|23.2599,77.4126|CR|9|F300|7B") },
                minLines = 2,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth()
            )

            Button(
                onClick = {
                    errorMessage = ""
                    val decoded = SmsDecoder.decode(smsInput)
                    if (decoded.valid && decoded.typeCode == "M") {
                        val coords = decoded.fields["Coordinates"]?.split(",")
                        val lat = coords?.getOrNull(0)?.toDoubleOrNull() ?: 0.0
                        val lon = coords?.getOrNull(1)?.toDoubleOrNull() ?: 0.0
                        
                        val newMarker = MapMarker(
                            id = UUID.randomUUID().toString(),
                            type = decoded.fields["Marker Type"] ?: "Unknown",
                            latitude = lat,
                            longitude = lon,
                            severity = decoded.fields["Severity"]?.toIntOrNull() ?: 0,
                            data = decoded.fields["Data"] ?: ""
                        )
                        markers = markers + newMarker
                    } else {
                        errorMessage = decoded.error.ifBlank { "Invalid marker payload." }
                    }
                },
                modifier = Modifier.fillMaxWidth().height(56.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = PactPrimary, contentColor = PactOnPrimary)
            ) {
                Text("Decode & Plot Marker", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }

            if (errorMessage.isNotBlank()) {
                Text(text = errorMessage, color = PactPrimary, fontWeight = FontWeight.Medium)
            }

            // TACTICAL MAP CANVAS
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(300.dp),
                shape = RoundedCornerShape(24.dp),
                color = PactSurface,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Box(modifier = Modifier.fillMaxSize().padding(8.dp)) {
                    TacticalMapView(markers = markers)
                    
                    Text(
                        text = "CACHED OFFLINE MAP",
                        modifier = Modifier.align(Alignment.TopStart).padding(8.dp),
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = PactTextSecondary,
                        letterSpacing = 1.sp
                    )
                }
            }

            if (markers.isNotEmpty()) {
                Text(
                    text = "Active Markers (${markers.size})",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = PactTextPrimary
                )
                
                markers.takeLast(3).reversed().forEach { marker ->
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        color = PactBackground,
                        border = BorderStroke(1.dp, PactAccent)
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(12.dp)
                        ) {
                            Surface(
                                modifier = Modifier.size(16.dp),
                                shape = CircleShape,
                                color = getMarkerColor(marker.type)
                            ) {}
                            Column {
                                Text(
                                    text = "${marker.type} (Sev: ${marker.severity})",
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontWeight = FontWeight.SemiBold,
                                    color = PactTextPrimary
                                )
                                Text(
                                    text = "Lat: ${marker.latitude}, Lon: ${marker.longitude} | ${marker.data}",
                                    style = MaterialTheme.typography.bodySmall,
                                    fontFamily = FontFamily.Monospace,
                                    color = PactTextSecondary
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun TacticalMapView(markers: List<MapMarker>) {
    val minLat = 23.0
    val maxLat = 24.0
    val minLon = 77.0
    val maxLon = 78.0

    Canvas(modifier = Modifier.fillMaxSize()) {
        val width = size.width
        val height = size.height
        val gridColor = PactAccent
        val stroke = Stroke(width = 2f)

        // Draw Grid
        for (i in 0..10) {
            val x = width * i / 10
            drawLine(gridColor, Offset(x, 0f), Offset(x, height), stroke.width)
            val y = height * i / 10
            drawLine(gridColor, Offset(0f, y), Offset(width, y), stroke.width)
        }

        // Draw Markers
        markers.forEach { marker ->
            if (marker.latitude in minLat..maxLat && marker.longitude in minLon..maxLon) {
                val x = ((marker.longitude - minLon) / (maxLon - minLon) * width).toFloat()
                val y = height - ((marker.latitude - minLat) / (maxLat - minLat) * height).toFloat()
                
                val color = getMarkerColor(marker.type)
                
                // Outer ring
                drawCircle(
                    color = color.copy(alpha = 0.3f),
                    radius = 24f,
                    center = Offset(x, y)
                )
                // Inner pin
                drawCircle(
                    color = color,
                    radius = 12f,
                    center = Offset(x, y),
                    style = stroke
                )
                drawCircle(
                    color = color,
                    radius = 6f,
                    center = Offset(x, y)
                )
            }
        }
    }
}

private fun getMarkerColor(type: String): Color {
    return when (type.lowercase()) {
        "crisis zone", "cr" -> Color(0xFFF62440) // PactPrimary Red
        "resource point", "rs" -> Color(0xFF2196F3) // Blue
        "medical point", "md" -> Color(0xFF4CAF50) // Green
        "shelter", "sh" -> Color(0xFF9C27B0) // Purple
        else -> Color(0xFFFF9800) // Orange
    }
}