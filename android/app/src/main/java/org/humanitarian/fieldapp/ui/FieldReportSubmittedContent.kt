package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.humanitarian.fieldapp.models.FieldReport
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary

@Composable
fun FieldReportSubmittedContent(
    padding: PaddingValues,
    report: FieldReport,
    submissionState: String,
    apiMessage: String,
    smsPayload: String,
    onCreateAnother: () -> Unit,
    onReturnHome: () -> Unit
) {
    val isSubmitting = submissionState == "submitting"

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
            }
        }

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
                    text = "Submission Status",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = PactTextPrimary
                )

                if (isSubmitting) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(20.dp),
                            color = PactPrimary,
                            strokeWidth = 3.dp
                        )

                        Text(
                            text = "Sending report to backend.",
                            style = MaterialTheme.typography.bodyMedium,
                            color = PactTextSecondary
                        )
                    }
                } else if (submissionState == "queued") {
                    Text(
                        text = apiMessage,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = PactPrimary
                    )

                    Text(
                        text = "This report is safely stored on your device. M5 converts it to an SMS payload, and M10 will sync it when internet returns.",
                        style = MaterialTheme.typography.bodySmall,
                        color = PactTextSecondary
                    )
                } else {
                    Text(
                        text = apiMessage,
                        style = MaterialTheme.typography.bodyMedium,
                        color = PactTextSecondary
                    )
                }
            }
        }

        if (smsPayload.isNotBlank()) {
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
                        text = "SMS Fallback Payload",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = PactTextPrimary
                    )

                    Text(
                        text = smsPayload,
                        style = MaterialTheme.typography.bodyLarge,
                        fontFamily = FontFamily.Monospace,
                        color = PactTextPrimary
                    )

                    Text(
                        text = "This payload follows the canonical need format from sms.md. M6 will add a dedicated SMS fallback screen with copy and send options.",
                        style = MaterialTheme.typography.bodySmall,
                        color = PactTextSecondary
                    )
                }
            }
        }

        Button(
            onClick = onCreateAnother,
            enabled = !isSubmitting,
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
            enabled = !isSubmitting,
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