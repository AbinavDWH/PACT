package org.pact.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.sp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import org.pact.app.MainActivity
import org.pact.app.Outbox

/**
 * Confirmation, and the outbox.
 *
 * The outbox is shown rather than hidden because the honest answer to "did my
 * request go?" is sometimes "not yet". A spinner that implies delivery it
 * cannot confirm is worse than a queue the person can see.
 *
 * Each row is styled like a console card: a state badge, then the wire string
 * in Fira Code. That string is the demo -- it is character-for-character what
 * the admin console shows arriving at the other end.
 */
@Composable
fun SentScreen(activity: MainActivity, detail: String, traceId: String?,
               onAgain: () -> Unit, onStatus: () -> Unit) {
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

    val queued = entries.any { it.pending }

    PactScaffold(
        sub = "Sent",
        actions = { StatusDot(on = !queued) },
        bottomBar = {
            PactBottomBar {
                Row(horizontalArrangement = Arrangement.spacedBy(Pact.Space3)) {
                    GhostButton("Send another", onAgain, modifier = Modifier.weight(1f))
                    // The primary action after sending is finding out what
                    // happened, not sending again. The old screen ended here,
                    // which is why "was it approved?" had no answer.
                    PrimaryButton("Check status", onStatus,
                                  modifier = Modifier.weight(1f))
                }
            }
        },
    ) { pad ->
        Column(Modifier.padding(pad).padding(horizontal = Pact.Gutter)
                   .verticalScroll(rememberScrollState())) {

            Spacer(Modifier.height(Pact.Space5))
            Text("Request sent", style = MaterialTheme.typography.headlineMedium,
                 color = Pact.Ink)
            Text(detail, style = MaterialTheme.typography.bodyMedium,
                 color = Pact.Dim,
                 modifier = Modifier.padding(top = Pact.Space2))

            traceId?.let {
                Spacer(Modifier.height(Pact.Space4))
                Panel(tone = Tone.Llm) {
                    Column(Modifier.padding(Pact.Space4)) {
                        Badge("Reference", Tone.Llm)
                        Spacer(Modifier.height(Pact.Space2))
                        Mono(it, size = 18.sp, color = Pact.Ink)
                        Text("Quote this if someone calls you back.",
                             style = MaterialTheme.typography.bodySmall,
                             color = Pact.Faint,
                             modifier = Modifier.padding(top = Pact.Space1))
                    }
                }
            }

            SectionLabel("Outbox", if (draining) "retrying…" else "${entries.size}")
            if (entries.isEmpty()) {
                Text("Nothing queued.", style = MaterialTheme.typography.bodyMedium,
                     color = Pact.Dim)
            } else {
                entries.sortedByDescending { it.createdAt }.take(12).forEach { e ->
                    OutboxRow(e)
                    Spacer(Modifier.height(Pact.Space2))
                }
            }

            if (queued) {
                Spacer(Modifier.height(Pact.Space3))
                GhostButton(
                    "Retry queued messages",
                    onClick = {
                        // Activity-scoped: drain() re-sends over SMS, which
                        // blocks on the radio for up to 30 s per message. A
                        // composition scope cancels that the moment someone
                        // navigates away mid-retry.
                        activity.lifecycleScope.launch {
                            draining = true
                            activity.transport.drain()
                            entries = activity.outbox.all()
                            draining = false
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            Spacer(Modifier.height(Pact.Space6))
        }
    }
}

@Composable
private fun OutboxRow(e: Outbox.Entry) {
    // The tone repeats what the label already says. Transport is part of the
    // state on this screen, not a detail: "sent as SMS" is the claim the whole
    // project rests on, and it should not look identical to "sent over data".
    val (label, tone) = when (e.state) {
        "sent_http" -> "Sent over data" to Tone.Good
        "sent_sms" -> "Sent as SMS" to Tone.Llm
        "failed" -> "Rejected" to Tone.Bad
        else -> "Waiting for signal" to Tone.Warn
    }
    Panel {
        Column(Modifier.padding(Pact.Space3)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Badge(label, tone)
                if (e.attempts > 1) {
                    Text("${e.attempts} attempts",
                         style = MaterialTheme.typography.labelSmall, color = Pact.Faint)
                }
            }
            Spacer(Modifier.height(Pact.Space2))
            // The actual wire string. Showing it is the demo: this exact text
            // is what goes over SMS and over HTTP, unchanged.
            Mono(e.payload, color = Pact.Ink)
            e.note?.let {
                Text(it, style = MaterialTheme.typography.labelSmall, color = Pact.Faint,
                     modifier = Modifier.padding(top = Pact.Space1))
            }
        }
    }
}
