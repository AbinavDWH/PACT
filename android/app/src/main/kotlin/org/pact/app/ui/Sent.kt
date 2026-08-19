package org.pact.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.pact.app.MainActivity
import org.pact.app.Outbox

/**
 * Confirmation, and the outbox.
 *
 * The outbox is shown rather than hidden because the honest answer to "did my
 * request go?" is sometimes "not yet". A spinner that implies delivery it
 * cannot confirm is worse than a queue the person can see.
 */
@Composable
fun SentScreen(activity: MainActivity, detail: String, traceId: String?,
               onAgain: () -> Unit) {
    val scope = rememberCoroutineScope()
    var entries by remember { mutableStateOf(activity.outbox.all()) }
    var draining by remember { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        // Anything queued from an earlier attempt gets another try whenever
        // this screen opens.
        draining = true
        activity.transport.drain()
        entries = activity.outbox.all()
        draining = false
    }

    Scaffold(
        bottomBar = {
            Surface(tonalElevation = 3.dp) {
                Column(Modifier.padding(16.dp)) {
                    Button(onClick = onAgain,
                           modifier = Modifier.fillMaxWidth().height(56.dp)) {
                        Text("Send another request")
                    }
                }
            }
        }
    ) { pad ->
        Column(Modifier.padding(pad).padding(horizontal = 20.dp)
                   .verticalScroll(rememberScrollState())) {

            Spacer(Modifier.height(16.dp))
            Text("Request sent", style = MaterialTheme.typography.headlineMedium,
                 fontWeight = FontWeight.Black)
            Text(detail, style = MaterialTheme.typography.bodyLarge,
                 modifier = Modifier.padding(top = 6.dp))

            traceId?.let {
                Spacer(Modifier.height(10.dp))
                Card {
                    Column(Modifier.padding(14.dp)) {
                        Text("Reference", style = MaterialTheme.typography.labelLarge,
                             fontWeight = FontWeight.Bold)
                        Text(it, style = MaterialTheme.typography.titleMedium)
                        Text("Quote this if someone calls you back.",
                             style = MaterialTheme.typography.bodySmall,
                             color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
                    }
                }
            }

            SectionLabel("Outbox", if (draining) "retrying…" else null)
            if (entries.isEmpty()) {
                Text("Nothing queued.", style = MaterialTheme.typography.bodyMedium)
            } else {
                entries.sortedByDescending { it.createdAt }.take(12).forEach { e ->
                    OutboxRow(e)
                    Spacer(Modifier.height(6.dp))
                }
            }

            if (entries.any { it.pending }) {
                Spacer(Modifier.height(10.dp))
                OutlinedButton(
                    onClick = {
                        scope.launch {
                            draining = true
                            activity.transport.drain()
                            entries = activity.outbox.all()
                            draining = false
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Retry queued messages") }
            }

            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun OutboxRow(e: Outbox.Entry) {
    val (label, colour) = when (e.state) {
        "sent_http" -> "Sent over data" to MaterialTheme.colorScheme.secondary
        "sent_sms" -> "Sent as SMS" to MaterialTheme.colorScheme.primary
        "failed" -> "Rejected" to MaterialTheme.colorScheme.error
        else -> "Waiting for signal" to MaterialTheme.colorScheme.onSurface
    }
    Card {
        Column(Modifier.padding(12.dp)) {
            Row(Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween) {
                Text(label, style = MaterialTheme.typography.labelLarge,
                     fontWeight = FontWeight.Bold, color = colour)
                if (e.attempts > 1) Text("${e.attempts} attempts",
                    style = MaterialTheme.typography.labelSmall)
            }
            // The actual wire string. Showing it is the demo: this exact text
            // is what goes over SMS and over HTTP, unchanged.
            Text(e.payload, style = MaterialTheme.typography.bodySmall,
                 modifier = Modifier.padding(top = 4.dp))
            e.note?.let {
                Text(it, style = MaterialTheme.typography.labelSmall,
                     color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
            }
        }
    }
}
