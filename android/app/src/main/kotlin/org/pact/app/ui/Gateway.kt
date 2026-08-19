package org.pact.app.ui

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
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

    Scaffold(
        bottomBar = {
            Surface(tonalElevation = 3.dp) {
                Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedButton(onClick = onBack, modifier = Modifier.weight(1f)) {
                        Text("Back")
                    }
                    Button(
                        onClick = { entries = SmsGateway.entries(context) },
                        modifier = Modifier.weight(1f),
                    ) { Text("Refresh") }
                }
            }
        }
    ) { pad ->
        Column(
            Modifier.padding(pad).padding(horizontal = 20.dp)
                .verticalScroll(rememberScrollState())
        ) {
            Spacer(Modifier.height(16.dp))
            Text("SMS gateway", style = MaterialTheme.typography.headlineMedium,
                 fontWeight = FontWeight.Black)
            Text(
                "This phone receives the real SMS and forwards it to the server. "
                    + "Leave it plugged in and on this screen.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f),
            )

            Spacer(Modifier.height(16.dp))
            Card {
                Row(
                    Modifier.padding(16.dp).fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    Column(Modifier.weight(1f)) {
                        Text("Gateway mode", style = MaterialTheme.typography.titleMedium,
                             fontWeight = FontWeight.Bold)
                        Text(
                            if (enabled) "Listening for PACT messages"
                            else "Off — inbound messages are ignored",
                            style = MaterialTheme.typography.bodySmall,
                            color = if (enabled) MaterialTheme.colorScheme.secondary
                                    else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
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
                    )
                }
            }

            Spacer(Modifier.height(10.dp))
            Card(colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.secondary.copy(alpha = 0.10f))) {
                Column(Modifier.padding(14.dp)) {
                    Text("Forwarding to", style = MaterialTheme.typography.labelLarge,
                         fontWeight = FontWeight.Bold)
                    Text(BuildConfig.API_BASE, style = MaterialTheme.typography.bodySmall)
                    Spacer(Modifier.height(6.dp))
                    // Saying this out loud matters: a gateway handset still
                    // receives OTPs and private messages, and forwarding those
                    // would be a worse privacy failure than anything this
                    // project defends against.
                    Text(
                        "Only messages that look like PACT frames are forwarded. "
                            + "Anything else — OTPs, personal messages — is ignored and "
                            + "never leaves this phone.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }

            SectionLabel("Received", if (entries.isEmpty()) "nothing yet" else null)
            entries.forEach { e ->
                Card(Modifier.padding(bottom = 8.dp)) {
                    Column(Modifier.padding(12.dp)) {
                        Row(Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(
                                if (e.optBoolean("ok")) "forwarded" else "failed",
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold,
                                color = if (e.optBoolean("ok"))
                                    MaterialTheme.colorScheme.secondary
                                else MaterialTheme.colorScheme.error,
                            )
                            Text(
                                SimpleDateFormat("HH:mm:ss", Locale.getDefault())
                                    .format(Date(e.optLong("at"))),
                                style = MaterialTheme.typography.labelSmall,
                            )
                        }
                        Text("from ${e.optString("from")}",
                             style = MaterialTheme.typography.labelSmall)
                        // The wire string itself. This is the demo: the same
                        // text that left the other handset.
                        Text(e.optString("body"),
                             style = MaterialTheme.typography.bodySmall,
                             modifier = Modifier.padding(top = 4.dp))
                    }
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}
