package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import org.humanitarian.fieldapp.models.FieldReport
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary

private val locationCodes = listOf("RA", "RB", "RC", "D1", "D2")
private val resourceCodes = listOf("F", "W", "M", "T", "B", "H", "D", "U")
private val urgencyCodes = listOf("L", "M", "H", "C")

private fun submitReport(report: FieldReport): Boolean {
    return report.organizationId.isNotBlank() &&
        report.locationCode in locationCodes &&
        report.resourceCode in resourceCodes &&
        report.quantity > 0 &&
        report.urgencyCode in urgencyCodes
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
                onCreateAnother = {
                    submittedReport = null
                    showError = false
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
                            text = "Enter the minimum required field data. This form will later support online submission, offline queueing, and SMS fallback.",
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
                    value = locationCode,
                    onValueChange = { locationCode = it.uppercase() },
                    label = { Text("Location Code") },
                    supportingText = { Text("Allowed: RA, RB, RC, D1, D2") },
                    singleLine = true,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth()
                )

                OutlinedTextField(
                    value = resourceCode,
                    onValueChange = { resourceCode = it.uppercase() },
                    label = { Text("Resource Code") },
                    supportingText = {
                        Text("F food, W water, M medical, T tents, B blankets, H hygiene, D medical teams, U unknown")
                    },
                    singleLine = true,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier.fillMaxWidth()
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
                    value = urgencyCode,
                    onValueChange = { urgencyCode = it.uppercase() },
                    label = { Text("Urgency Code") },
                    supportingText = { Text("L low, M medium, H high, C critical") },
                    singleLine = true,
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
                        text = "Please fill all required fields with valid codes and a positive quantity.",
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
                            submittedReport = reportCandidate
                            showError = false
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
private fun FieldReportSubmittedContent(
    padding: PaddingValues,
    report: FieldReport,
    onCreateAnother: () -> Unit,
    onReturnHome: () -> Unit
) {
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
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "Report Prepared",
                    style = MaterialTheme.typography.headlineSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = PactTextPrimary
                )

                ReportSummaryRow(
                    label = "Organization",
                    value = report.organizationId
                )

                ReportSummaryRow(
                    label = "Location",
                    value = report.locationCode
                )

                ReportSummaryRow(
                    label = "Resource",
                    value = report.resourceCode
                )

                ReportSummaryRow(
                    label = "Quantity",
                    value = report.quantity.toString()
                )

                ReportSummaryRow(
                    label = "Urgency",
                    value = report.urgencyCode
                )

                if (report.notes.isNotBlank()) {
                    ReportSummaryRow(
                        label = "Notes",
                        value = report.notes
                    )
                }

                Text(
                    text = "Next module will convert this into an online API request or an SMS fallback payload.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = PactTextSecondary
                )
            }
        }

        Button(
            onClick = onCreateAnother,
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
                text = "Create Another Report",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
        }

        OutlinedButton(
            onClick = onReturnHome,
            modifier = Modifier
                .fillMaxWidth()
                .height(56.dp),
            shape = RoundedCornerShape(16.dp),
            border = BorderStroke(1.dp, PactAccent),
            colors = ButtonDefaults.outlinedButtonColors(
                containerColor = PactBackground,
                contentColor = PactTextPrimary
            )
        ) {
            Text(
                text = "Return to Home",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Medium
            )
        }
    }
}

@Composable
private fun ReportSummaryRow(
    label: String,
    value: String
) {
    Column {
        Text(
            text = label,
            style = MaterialTheme.typography.labelLarge,
            color = PactTextSecondary
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.Medium,
            color = PactTextPrimary
        )
    }
}