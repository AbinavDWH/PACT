package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.humanitarian.fieldapp.sms.SmsDecoder
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SmsDecoderScreen(
    onBack: () -> Unit
) {
    var input by remember { mutableStateOf("") }
    var result by remember { mutableStateOf<SmsDecoder.DecodedSms?>(null) }
    var showTechnical by remember { mutableStateOf(false) }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "SMS Decoder",
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
                        text = "SMS Decoder Demo",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = PactTextPrimary
                    )
                    Text(
                        text = "Paste an SMS payload and it will be decoded into a readable message. Encoding and decoding are handled by separate functions.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = PactTextSecondary
                    )
                }
            }

            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                label = { Text("SMS Payload") },
                supportingText = { Text("Example: N|001|NGO01|RA|F|300|H|1C") },
                minLines = 3,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth()
            )

            SamplePayloadRow { sample ->
                input = sample
                result = null
                showTechnical = false
            }

            Button(
                onClick = {
                    result = SmsDecoder.decode(input)
                    showTechnical = false
                },
                modifier = Modifier.fillMaxWidth().height(56.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = PactPrimary, contentColor = PactOnPrimary)
            ) {
                Text("Decode SMS", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }

            val decoded = result
            if (decoded != null) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(24.dp),
                    color = PactSurface,
                    border = BorderStroke(1.dp, if (decoded.valid) PactAccent else PactPrimary)
                ) {
                    Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        if (decoded.valid) {
                            // Type + integrity badge
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = decoded.typeLabel,
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.SemiBold,
                                    color = PactTextSecondary
                                )
                                Text(
                                    text = "Integrity verified",
                                    style = MaterialTheme.typography.labelLarge,
                                    fontWeight = FontWeight.SemiBold,
                                    color = PactPrimary
                                )
                            }

                            // PRIMARY OUTPUT: the readable decoded message
                            Surface(
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(16.dp),
                                color = PactBackground,
                                border = BorderStroke(1.dp, PactAccent)
                            ) {
                                Text(
                                    text = decoded.message,
                                    modifier = Modifier.padding(16.dp),
                                    style = MaterialTheme.typography.bodyLarge,
                                    fontWeight = FontWeight.Medium,
                                    color = PactTextPrimary
                                )
                            }

                            // Optional technical details (hidden by default)
                            OutlinedButton(
                                onClick = { showTechnical = !showTechnical },
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(16.dp),
                                border = BorderStroke(1.dp, PactAccent),
                                colors = ButtonDefaults.outlinedButtonColors(
                                    containerColor = PactSurface, contentColor = PactTextPrimary
                                )
                            ) {
                                Text(
                                    text = if (showTechnical) "Hide technical details" else "Show technical details",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.Medium
                                )
                            }

                            if (showTechnical) {
                                decoded.fields.forEach { (key, value) ->
                                    Column {
                                        Text(key, style = MaterialTheme.typography.labelLarge, color = PactTextSecondary)
                                        Text(
                                            text = value,
                                            style = MaterialTheme.typography.bodyLarge,
                                            fontWeight = FontWeight.Medium,
                                            color = PactTextPrimary
                                        )
                                    }
                                }

                                Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(PactAccent))

                                Text(
                                    text = "Structured JSON (for agent pipeline)",
                                    style = MaterialTheme.typography.titleMedium,
                                    fontWeight = FontWeight.SemiBold,
                                    color = PactTextPrimary
                                )
                                Surface(
                                    modifier = Modifier.fillMaxWidth(),
                                    shape = RoundedCornerShape(12.dp),
                                    color = PactBackground,
                                    border = BorderStroke(1.dp, PactAccent)
                                ) {
                                    Text(
                                        text = decoded.json,
                                        modifier = Modifier.padding(16.dp),
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontFamily = FontFamily.Monospace,
                                        color = PactTextPrimary
                                    )
                                }
                            }
                        } else {
                            Text(
                                text = "Decode Failed",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.SemiBold,
                                color = PactPrimary
                            )
                            Text(text = decoded.error, style = MaterialTheme.typography.bodyMedium, color = PactTextSecondary)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun SamplePayloadRow(
    onSelect: (String) -> Unit
) {
    // Checksums below are the REAL XOR values (sms.md examples are illustrative).
    val samples = listOf(
        "Need" to "N|001|NGO01|RA|F|300|H|1C",
        "Need (legacy)" to "N|NGO01|RegionA|food|300|H",
        "Status" to "S|004|PLAN101|3|0B",
        "Marker" to "M|008|23.2599,77.4126|CR|9|F300|7B"
    )

    Row(
        modifier = Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp)
    ) {
        samples.forEach { (label, payload) ->
            OutlinedButton(
                onClick = { onSelect(payload) },
                shape = RoundedCornerShape(16.dp),
                border = BorderStroke(1.dp, PactAccent),
                colors = ButtonDefaults.outlinedButtonColors(containerColor = PactSurface, contentColor = PactTextPrimary)
            ) {
                Text(text = label, style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}