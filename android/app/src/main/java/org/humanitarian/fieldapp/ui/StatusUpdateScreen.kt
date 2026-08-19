package org.humanitarian.fieldapp.ui

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.RadioButtonDefaults
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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.humanitarian.fieldapp.sms.StatusSmsBuilder
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun StatusUpdateScreen(
    onBack: () -> Unit
) {
    val context = LocalContext.current
    var organizationId by rememberSaveable { mutableStateOf("NGO01") }
    var planId by rememberSaveable { mutableStateOf("PLAN101") }
    var selectedStatus by rememberSaveable { mutableStateOf("3") }
    var generatedPayload by remember { mutableStateOf("") }
    var generatedMessage by remember { mutableStateOf("") }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Status Update",
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
                        text = "Delivery Status Update",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = PactTextPrimary
                    )
                    Text(
                        text = "Field teams confirm delivery progress by generating a canonical status SMS. This works without internet and can be sent to the coordination gateway.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = PactTextSecondary
                    )
                }
            }

            OutlinedTextField(
                value = organizationId,
                onValueChange = { organizationId = it.uppercase() },
                label = { Text("Organization ID") },
                supportingText = { Text("Example: NGO01, CSR02, GOV03") },
                singleLine = true,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth()
            )

            OutlinedTextField(
                value = planId,
                onValueChange = { planId = it.uppercase() },
                label = { Text("Plan ID") },
                supportingText = { Text("Example: PLAN101") },
                singleLine = true,
                shape = RoundedCornerShape(16.dp),
                modifier = Modifier.fillMaxWidth()
            )

            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = PactSurface,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "Delivery Status",
                        style = MaterialTheme.typography.labelLarge,
                        color = PactTextSecondary
                    )

                    StatusSmsBuilder.statusOptions.forEach { (code, label) ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            RadioButton(
                                selected = selectedStatus == code,
                                onClick = { selectedStatus = code },
                                colors = RadioButtonDefaults.colors(
                                    selectedColor = PactPrimary,
                                    unselectedColor = PactTextSecondary
                                )
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                            Text(
                                text = "$label ($code)",
                                style = MaterialTheme.typography.bodyLarge,
                                color = PactTextPrimary
                            )
                        }
                    }
                }
            }

            Button(
                onClick = {
                    val org = organizationId.trim().uppercase()
                    val plan = planId.trim().uppercase()
                    if (org.isNotBlank() && plan.isNotBlank()) {
                        val seq = StatusSmsBuilder.nextSequence(context, org)
                        generatedPayload = StatusSmsBuilder.encodeStatus(seq, plan, selectedStatus)
                        generatedMessage = StatusSmsBuilder.humanMessage(plan, selectedStatus)
                    } else {
                        Toast.makeText(context, "Enter organization and plan ID", Toast.LENGTH_SHORT).show()
                    }
                },
                modifier = Modifier.fillMaxWidth().height(56.dp),
                shape = RoundedCornerShape(16.dp),
                colors = ButtonDefaults.buttonColors(containerColor = PactPrimary, contentColor = PactOnPrimary)
            ) {
                Text("Generate Status SMS", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }

            if (generatedPayload.isNotBlank()) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(24.dp),
                    color = PactSurface,
                    border = BorderStroke(1.dp, PactAccent)
                ) {
                    Column(modifier = Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            text = "Generated Status SMS",
                            style = MaterialTheme.typography.titleLarge,
                            fontWeight = FontWeight.SemiBold,
                            color = PactTextPrimary
                        )

                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            color = PactBackground,
                            border = BorderStroke(1.dp, PactAccent)
                        ) {
                            Text(
                                text = generatedMessage,
                                modifier = Modifier.padding(16.dp),
                                style = MaterialTheme.typography.bodyLarge,
                                fontWeight = FontWeight.Medium,
                                color = PactTextPrimary
                            )
                        }

                        Text(text = "SMS Payload", style = MaterialTheme.typography.labelLarge, color = PactTextSecondary)

                        Surface(
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            color = PactBackground,
                            border = BorderStroke(1.dp, PactAccent)
                        ) {
                            Text(
                                text = generatedPayload,
                                modifier = Modifier.padding(16.dp),
                                style = MaterialTheme.typography.bodyLarge,
                                fontFamily = FontFamily.Monospace,
                                color = PactTextPrimary
                            )
                        }

                        Button(
                            onClick = {
                                val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                                clipboard.setPrimaryClip(ClipData.newPlainText("Status SMS", generatedPayload))
                                Toast.makeText(context, "Status SMS copied", Toast.LENGTH_SHORT).show()
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = PactPrimary, contentColor = PactOnPrimary)
                        ) {
                            Text("Copy Payload", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                        }

                        Text(
                            text = "Tip: Paste this payload into the SMS Decoder to verify it decodes into a readable status message.",
                            style = MaterialTheme.typography.bodySmall,
                            color = PactTextSecondary
                        )
                    }
                }
            }
        }
    }
}