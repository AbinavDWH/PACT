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
import org.pact.app.Loc
import org.pact.app.MainActivity
import org.pact.app.Options
import org.pact.app.Selection
import org.pact.codec.PactCodec
import java.util.UUID

/**
 * The request screen. **There is no text input anywhere on it**, by design
 * (memory_draft.md 15).
 *
 * Three reasons, none of them cosmetic:
 *   - free text does not compress into a 35-character code;
 *   - free text is what identifies a person in an intercepted SMS;
 *   - tapping six chips is faster and more reliable than typing a sentence,
 *     one-handed, in the dark, in a hurry, possibly in a language the operator
 *     does not read.
 *
 * Every chip below is generated from the codec tables. None of the labels are
 * written out in this file.
 */
@Composable
fun RequestScreen(activity: MainActivity, onSent: (String, String?) -> Unit) {
    val scope = rememberCoroutineScope()
    var sel by remember { mutableStateOf(Selection()) }
    var fix by remember { mutableStateOf<Loc.Fix?>(null) }
    var locating by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    // Start the GPS fix the moment the screen opens, not when Send is pressed.
    // A cold fix can take thirty seconds; that wait must overlap the tapping,
    // not follow it.
    LaunchedEffect(activity.permissionsAnswered) {
        locating = true
        fix = activity.loc.current()
        locating = false
    }

    Scaffold(
        bottomBar = {
            Surface(tonalElevation = 3.dp) {
                Column(Modifier.padding(16.dp)) {
                    error?.let {
                        Text(it, color = MaterialTheme.colorScheme.error,
                             style = MaterialTheme.typography.bodySmall,
                             modifier = Modifier.padding(bottom = 8.dp))
                    }
                    Button(
                        onClick = {
                            busy = true; error = null
                            scope.launch {
                                val f = fix ?: activity.loc.current()
                                if (f == null) {
                                    error = "No position yet. Turn on location and " +
                                        "step outside if you can — a request without " +
                                        "a position cannot be routed to anyone."
                                    busy = false
                                    return@launch
                                }
                                try {
                                    // The same string, whichever transport carries it.
                                    val payload = PactCodec.encodeRequest(
                                        sel = sel.toCodecMap(),
                                        lat = f.lat, lon = f.lon,
                                        uid = activity.session.uid ?: "0000",
                                        seq = activity.session.nextSeq(),
                                        accuracyM = f.accuracyM,
                                    )
                                    val out = activity.transport.send(
                                        UUID.randomUUID().toString(), payload)
                                    onSent(out.detail, out.traceId)
                                } catch (e: Exception) {
                                    error = "Could not build the request: ${e.message}"
                                } finally { busy = false }
                            }
                        },
                        enabled = sel.complete && !busy,
                        modifier = Modifier.fillMaxWidth().height(60.dp),
                    ) {
                        if (busy) CircularProgressIndicator(
                            Modifier.size(22.dp), strokeWidth = 2.dp,
                            color = MaterialTheme.colorScheme.onPrimary)
                        else Text(
                            if (sel.complete) "Send request" else "Answer the questions above",
                            style = MaterialTheme.typography.titleMedium)
                    }
                }
            }
        }
    ) { pad ->
        Column(Modifier.padding(pad).padding(horizontal = 20.dp)
                   .verticalScroll(rememberScrollState())) {

            Spacer(Modifier.height(8.dp))
            Text("Request help", style = MaterialTheme.typography.headlineMedium,
                 fontWeight = FontWeight.Black)
            Text("Tap what applies. Nothing to type.",
                 style = MaterialTheme.typography.bodyMedium,
                 color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))

            Spacer(Modifier.height(12.dp))
            PositionCard(fix, locating) {
                scope.launch { locating = true; fix = activity.loc.current(); locating = false }
            }

            SectionLabel("What happened")
            ChipGrid(Options.situations.map { it.code to it.pretty },
                     selected = setOfNotNull(sel.situation)) {
                sel = sel.copy(situation = it)
            }

            SectionLabel("How many people")
            ChipGrid(Options.people.map { it.code to it.label },
                     selected = setOfNotNull(sel.people)) { sel = sel.copy(people = it) }

            SectionLabel("Injuries")
            ChipGrid(Options.injuries.map { it.code to it.pretty },
                     selected = setOfNotNull(sel.injury)) { sel = sel.copy(injury = it) }

            SectionLabel("Can you move")
            ChipGrid(Options.mobility.map { it.code to it.pretty },
                     selected = setOfNotNull(sel.mobility)) { sel = sel.copy(mobility = it) }

            SectionLabel("What do you need", "choose any")
            ChipGrid(Options.needs.map { it.label to it.pretty },
                     selected = sel.needs, multi = true) { key ->
                sel = sel.copy(needs = sel.needs.toggle(key))
            }

            SectionLabel("Anyone especially at risk", "optional")
            ChipGrid(Options.vulnerabilities.map { it.label to it.pretty },
                     selected = sel.vulnerabilities, multi = true) { key ->
                sel = sel.copy(vulnerabilities = sel.vulnerabilities.toggle(key))
            }

            SectionLabel("How urgent")
            ChipGrid(Options.urgency.map { it.code to it.pretty },
                     selected = setOf(sel.urgency)) { sel = sel.copy(urgency = it) }

            Spacer(Modifier.height(24.dp))
        }
    }
}

private fun Set<String>.toggle(v: String): Set<String> =
    if (contains(v)) this - v else this + v

@Composable
private fun PositionCard(fix: Loc.Fix?, locating: Boolean, onRetry: () -> Unit) {
    Card(colors = CardDefaults.cardColors(
        containerColor = MaterialTheme.colorScheme.secondary.copy(alpha = 0.10f))) {
        Row(Modifier.padding(14.dp).fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween) {
            Column(Modifier.weight(1f)) {
                Text("Position", style = MaterialTheme.typography.labelLarge,
                     fontWeight = FontWeight.Bold)
                when {
                    locating && fix == null -> Text("Getting a GPS fix…",
                        style = MaterialTheme.typography.bodySmall)
                    fix == null -> Text("No fix yet. Location may be off.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error)
                    else -> Text(
                        "Locked, ±${fix.accuracyM?.toInt() ?: -1} m via ${fix.provider}. " +
                            "Sent to within ~1 m; helpers see ~1 km until they accept.",
                        style = MaterialTheme.typography.bodySmall)
                }
            }
            if (!locating) TextButton(onClick = onRetry) { Text("Refresh") }
        }
    }
}
