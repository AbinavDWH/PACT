package org.pact.app.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import org.pact.app.BuildConfig
import org.pact.app.MainActivity
import org.pact.app.SmsGateway
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Gateway mode: this handset acts as the SMS receiver.
 *
 * Install the same APK on a second phone, turn this on, and the offline path
 * is genuinely end to end — a real SMS crosses a real cellular network and
 * arrives at the backend. Previously the seeker phone sent a real message and
 * nothing received it; the only route into the backend was a human pasting the
 * string into the simulator.
 *
 * This is the most console-like screen in the app, and it is styled like one:
 * a live indicator in the top bar, a log of received frames, and every wire
 * string in Fira Code.
 */
@Composable
fun GatewayScreen(activity: MainActivity, onBack: () -> Unit) {
    val context = LocalContext.current
    var enabled by remember { mutableStateOf(SmsGateway.isEnabled(context)) }
    var entries by remember { mutableStateOf(SmsGateway.entries(context)) }
    var hasPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECEIVE_SMS)
                == PackageManager.PERMISSION_GRANTED
        )
    }

    val ask = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted ->
        hasPermission = granted
        if (granted) {
            SmsGateway.setEnabled(context, true)
            enabled = true
        }
    }

    PactScaffold(
        sub = "Gateway",
        actions = { StatusDot(on = enabled) },
        bottomBar = {
            PactBottomBar {
                Row(horizontalArrangement = Arrangement.spacedBy(Pact.Space3)) {
                    GhostButton("Back", onBack, modifier = Modifier.weight(1f))
                    PrimaryButton(
                        "Refresh",
                        onClick = { entries = SmsGateway.entries(context) },
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        },
    ) { pad ->
        Column(
            Modifier.padding(pad).padding(horizontal = Pact.Gutter)
                .verticalScroll(rememberScrollState())
        ) {
            Spacer(Modifier.height(Pact.Space5))
            Text("SMS gateway", style = MaterialTheme.typography.headlineMedium,
                 color = Pact.Ink)
            Text(
                "This phone receives the real SMS and forwards it to the server. "
                    + "Leave it plugged in and on this screen.",
                style = MaterialTheme.typography.bodyMedium,
                color = Pact.Dim,
                modifier = Modifier.padding(top = Pact.Space1),
            )

            Spacer(Modifier.height(Pact.Space4))
            Panel(tone = if (enabled) Tone.Good else null) {
                Row(
                    Modifier.padding(Pact.Space4).fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("Gateway mode", style = MaterialTheme.typography.titleSmall,
                             color = Pact.Ink)
                        Text(
                            if (enabled) "Listening for PACT messages"
                            else "Off — inbound messages are ignored",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (enabled) Pact.Good else Pact.Faint,
                        )
                    }
                    Switch(
                        checked = enabled,
                        onCheckedChange = { want ->
                            if (want && !hasPermission) {
                                ask.launch(Manifest.permission.RECEIVE_SMS)
                            } else {
                                SmsGateway.setEnabled(context, want)
                                enabled = want
                            }
                        },
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = Pact.OnAccent,
                            checkedTrackColor = Pact.Det,
                            checkedBorderColor = Pact.Det,
                            uncheckedThumbColor = Pact.Dim,
                            uncheckedTrackColor = Pact.Panel3,
                            uncheckedBorderColor = Pact.Line,
                        ),
                    )
                }
            }

            Spacer(Modifier.height(Pact.Space3))
            NotePanel(Tone.Llm) {
                Badge("Forwarding to", Tone.Llm)
                Spacer(Modifier.height(Pact.Space2))
                Mono(BuildConfig.API_BASE, color = Pact.Ink)
                Spacer(Modifier.height(Pact.Space2))
                // Saying this out loud matters: a gateway handset still
                // receives OTPs and private messages, and forwarding those
                // would be a worse privacy failure than anything this
                // project defends against.
                Text(
                    "Only messages that look like PACT frames are forwarded. "
                        + "Anything else — OTPs, personal messages — is ignored and "
                        + "never leaves this phone.",
                    style = MaterialTheme.typography.bodySmall,
                    color = Pact.Dim,
                )
            }

            SectionLabel("Received", if (entries.isEmpty()) "nothing yet" else "${entries.size}")
            entries.forEach { e ->
                val ok = e.optBoolean("ok")
                Panel(Modifier.padding(bottom = Pact.Space2)) {
                    Column(Modifier.padding(Pact.Space3)) {
                        Row(
                            Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Badge(
                                if (ok) "forwarded" else "failed",
                                if (ok) Tone.Good else Tone.Bad,
                            )
                            Mono(
                                SimpleDateFormat("HH:mm:ss", Locale.getDefault())
                                    .format(Date(e.optLong("at"))),
                                color = Pact.Faint,
                                size = 11.sp,
                            )
                        }
                        Text("from ${e.optString("from")}",
                             style = MaterialTheme.typography.labelSmall, color = Pact.Faint,
                             modifier = Modifier.padding(top = Pact.Space2))
                        // The wire string itself. This is the demo: the same
                        // text that left the other handset.
                        Mono(e.optString("body"), color = Pact.Ink,
                             modifier = Modifier.padding(top = Pact.Space1))
                    }
                }
            }
            Spacer(Modifier.height(Pact.Space6))
        }
    }
}
