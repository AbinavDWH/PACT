package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.json.JSONObject
import org.humanitarian.fieldapp.models.FieldReport
import org.humanitarian.fieldapp.network.ApiClient
import org.humanitarian.fieldapp.network.ApiResult
import org.humanitarian.fieldapp.offline.OfflineQueue
import org.humanitarian.fieldapp.offline.SubmittedReports
import org.humanitarian.fieldapp.sms.SmsEncoder
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary

private data class CodeOption(
    val code: String,
    val label: String
)

private val locationOptions = listOf(
    CodeOption("RA", "Region A"),
    CodeOption("RB", "Region B"),
    CodeOption("RC", "Region C"),
    CodeOption("D1", "District North"),
    CodeOption("D2", "District South")
)

private val resourceOptions = listOf(
    CodeOption("F", "Food kits"),
    CodeOption("W", "Water kits"),
    CodeOption("M", "Medical kits"),
    CodeOption("T", "Tents"),
    CodeOption("B", "Blankets"),
    CodeOption("H", "Hygiene kits"),
    CodeOption("D", "Medical teams"),
    CodeOption("U", "Unknown")
)

private val urgencyOptions = listOf(
    CodeOption("L", "Low"),
    CodeOption("M", "Medium"),
    CodeOption("H", "High"),
    CodeOption("C", "Critical")
)

private fun submitReport(report: FieldReport): Boolean {
    return report.organizationId.isNotBlank() &&
        locationOptions.any { it.code == report.locationCode } &&
        resourceOptions.any { it.code == report.resourceCode } &&
        report.quantity > 0 &&
        urgencyOptions.any { it.code == report.urgencyCode }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FieldReportScreen(
    onBack: () -> Unit,
    onReturnHome: () -> Unit
) {
    var organizationId by rememberSaveable { mutableStateOf("NGO01") }
    var locationCode by rememberSaveable { mutableStateOf("RA") }
    var resourceCode by rememberSaveable { mutableStateOf("F") }
    var quantity by rememberSaveable { mutableStateOf("") }
    var urgencyCode by rememberSaveable { mutableStateOf("H") }
    var notes by rememberSaveable { mutableStateOf("") }

    var submittedReport by remember { mutableStateOf<FieldReport?>(null) }
    var showError by rememberSaveable { mutableStateOf(false) }
    var submissionState by remember { mutableStateOf("idle") }
    var apiMessage by remember { mutableStateOf("") }
    var smsPayload by remember { mutableStateOf("") }

    val coroutineScope = rememberCoroutineScope()
    val context = LocalContext.current

    val sendReport: (FieldReport) -> Unit = { report ->
        submittedReport = report
        showError = false
        submissionState = "submitting"
        apiMessage = ""

        coroutineScope.launch {
            when (val result = ApiClient.postNeed(report)) {
                is ApiResult.Success -> {
                    submissionState = "success"
                    apiMessage = "Online submission successful."
                    smsPayload = ""
                    // Persist to My Requests screen
                    val needId = try {
                        JSONObject(result.data).optString("need_id", "unknown")
                    } catch (e: Exception) {
                        "unknown"
                    }
                    SubmittedReports.add(context, report, needId)
                }

                is ApiResult.Error -> {
                    // 1. Generate sequence and SMS payload first
                    val seq = SmsEncoder.nextSequence(
                        context = context,
                        organizationId = report.organizationId
                    )

                    val generatedPayload = SmsEncoder.encodeNeed(
                        report = report,
                        seq = seq
                    )

                    // 2. Update UI state
                    smsPayload = generatedPayload
                    submissionState = "queued"
                    apiMessage = "Internet unavailable. Report saved to offline queue."

                    // 3. Save to offline queue with the generated payload
                    OfflineQueue.addReport(context, report, generatedPayload)
                }
            }
        }
    }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Field Report",
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
        val report = submittedReport

        if (report != null) {
            FieldReportSubmittedContent(
                padding = padding,
                report = report,
                submissionState = submissionState,
                apiMessage = apiMessage,
                smsPayload = smsPayload,
                onCreateAnother = {
                    submittedReport = null
                    showError = false
                    submissionState = "idle"
                    apiMessage = ""
                    smsPayload = ""
                },
                onReturnHome = onReturnHome
            )
        } else {
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
                    Column(
                        modifier = Modifier.padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Text(
                            text = "Need Report",
                            style = MaterialTheme.typography.headlineSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = PactTextPrimary
                        )

                        Text(
                            text = "Select location, resource, and urgency using predefined codes. If internet is unavailable, the report is automatically saved to the offline queue.",
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

                CodeDropdown(
                    label = "Location",
                    options = locationOptions,
                    selectedCode = locationCode,
                    onCodeSelected = { locationCode = it },
                    supportingText = "Select a predefined location code."
                )

                CodeDropdown(
                    label = "Resource",
                    options = resourceOptions,
                    selectedCode = resourceCode,
                    onCodeSelected = { resourceCode = it },
                    supportingText = "Select a resource type code."
                )

                UrgencyRadioGroup(
                    selectedCode = urgencyCode,
                    onCodeSelected = { urgencyCode = it }
                )

                OutlinedTextField(
                    value = quantity,
                    onValueChange = { newValue ->
                        quantity = newValue.filter { character ->
                            character.isDigit()
                        }
                    },
                    label = { Text("Quantity") },
                    supportingText = { Text("Enter a positive integer") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = notes,
                    onValueChange = { notes = it },
                    label = { Text("Notes, optional") },
                    supportingText = { Text("Do not include personal or sensitive data") },
                    maxLines = 3,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth()
                )

                if (showError) {
                    Text(
                        text = "Please fill all required fields with valid selections and a positive quantity.",
                        color = PactPrimary,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium
                    )
                }

                Button(
                    onClick = {
                        val reportCandidate = FieldReport(
                            organizationId = organizationId.trim().uppercase(),
                            locationCode = locationCode.trim().uppercase(),
                            resourceCode = resourceCode.trim().uppercase(),
                            quantity = quantity.trim().toIntOrNull() ?: 0,
                            urgencyCode = urgencyCode.trim().uppercase(),
                            notes = notes.trim()
                        )

                        if (submitReport(reportCandidate)) {
                            sendReport(reportCandidate)
                        } else {
                            showError = true
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PactPrimary,
                        contentColor = PactOnPrimary
                    )
                ) {
                    Text(
                        text = "Submit Field Report",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }
    }
}

@Composable
private fun CodeDropdown(
    label: String,
    options: List<CodeOption>,
    selectedCode: String,
    onCodeSelected: (String) -> Unit,
    supportingText: String
) {
    var expanded by remember { mutableStateOf(false) }

    val selectedOption = options.firstOrNull { it.code == selectedCode }

    val displayValue = selectedOption?.let {
        "${it.code} - ${it.label}"
    } ?: "Select"

    Box(
        modifier = Modifier.fillMaxWidth()
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clickable { expanded = true }
        ) {
            Surface(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = PactBackground,
                border = BorderStroke(1.dp, PactAccent)
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(4.dp)
                ) {
                    Text(
                        text = label,
                        style = MaterialTheme.typography.labelLarge,
                        color = PactTextSecondary
                    )

                    Text(
                        text = displayValue,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.Medium,
                        color = PactTextPrimary
                    )

                    Text(
                        text = supportingText,
                        style = MaterialTheme.typography.bodySmall,
                        color = PactTextSecondary
                    )
                }
            }
        }

        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false }
        ) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = {
                        Text("${option.code} - ${option.label}")
                    },
                    onClick = {
                        onCodeSelected(option.code)
                        expanded = false
                    }
                )
            }
        }
    }
}

@Composable
private fun UrgencyRadioGroup(
    selectedCode: String,
    onCodeSelected: (String) -> Unit
) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        color = PactSurface,
        border = BorderStroke(1.dp, PactAccent)
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "Urgency",
                style = MaterialTheme.typography.labelLarge,
                color = PactTextSecondary
            )

            urgencyOptions.forEach { option ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    RadioButton(
                        selected = selectedCode == option.code,
                        onClick = {
                            onCodeSelected(option.code)
                        },
                        colors = RadioButtonDefaults.colors(
                            selectedColor = PactPrimary,
                            unselectedColor = PactTextSecondary
                        )
                    )

                    Spacer(modifier = Modifier.width(8.dp))

                    Text(
                        text = "${option.label} (${option.code})",
                        style = MaterialTheme.typography.bodyLarge,
                        color = PactTextPrimary
                    )
                }
            }
        }
    }
}