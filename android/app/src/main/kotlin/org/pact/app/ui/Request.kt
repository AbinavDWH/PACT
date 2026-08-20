package org.pact.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import org.pact.app.Loc
import org.pact.app.MainActivity
import org.pact.app.Options
import org.pact.app.Selection
import org.pact.codec.PactCodec
import java.util.Locale
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
fun RequestScreen(activity: MainActivity, onStatus: () -> Unit,
                  onSent: (String, String?) -> Unit) {
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

    PactScaffold(
        sub = "Request",
        actions = {
            // Reachable before sending anything, not only afterwards: someone
            // who closed the app while waiting comes back in here.
            LinkButton("Status", onStatus)
            StatusDot(on = fix != null)
        },
        bottomBar = {
            PactBottomBar {
                error?.let {
                    NotePanel(Tone.Bad, Modifier.padding(bottom = Pact.Space3)) {
                        Text(it, style = MaterialTheme.typography.bodySmall, color = Pact.Ink)
                    }
                }
                PrimaryButton(
                    text = if (sel.complete) "Send request" else "Answer the questions above",
                    onClick = {
                        busy = true; error = null
                        // NOT the composition scope. This screen calls
                        // onSent() the moment send() returns, so the screen
                        // leaves the composition while the send is still in
                        // flight -- and on the SMS path send() waits up to 30 s
                        // for the radio. The cancellation surfaced to the user
                        // as "Could not send by SMS: The coroutine scope left
                        // the composition", on a request that was fine. The
                        // activity scope outlives navigation; the outbox still
                        // covers process death.
                        activity.lifecycleScope.launch {
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
                    enabled = sel.complete,
                    busy = busy,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
    ) { pad ->
        Column(Modifier.padding(pad).padding(horizontal = Pact.Gutter)
                   .verticalScroll(rememberScrollState())) {

            Spacer(Modifier.height(Pact.Space5))
            Text("Request help", style = MaterialTheme.typography.headlineMedium,
                 color = Pact.Ink)
            Text("Tap what applies. Nothing to type.",
                 style = MaterialTheme.typography.bodyMedium,
                 color = Pact.Dim,
                 modifier = Modifier.padding(top = Pact.Space1))

            Spacer(Modifier.height(Pact.Space4))
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

            Spacer(Modifier.height(Pact.Space6))
        }
    }
}

private fun Set<String>.toggle(v: String): Set<String> =
    if (contains(v)) this - v else this + v

/**
 * The one panel on this screen that reports rather than asks.
 *
 * The coordinates are set in Fira Code and the state is a badge, matching how
 * the console prints a position: mono means the machine produced this string,
 * and the badge says what the system currently believes, in a word, next to
 * the colour that repeats it.
 */
@Composable
private fun PositionCard(fix: Loc.Fix?, locating: Boolean, onRetry: () -> Unit) {
    val tone = when {
        fix != null -> Tone.Good
        locating -> Tone.Neutral
        else -> Tone.Warn
    }
    Panel(tone = tone) {
        Column(Modifier.padding(Pact.Space4)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Position", style = MaterialTheme.typography.titleSmall,
                     color = Pact.Ink)
                Badge(
                    when {
                        fix != null -> "locked"
                        locating -> "searching"
                        else -> "no fix"
                    },
                    tone,
                )
            }
            Spacer(Modifier.height(Pact.Space2))
            when {
                locating && fix == null -> Text(
                    "Getting a GPS fix…",
                    style = MaterialTheme.typography.bodySmall, color = Pact.Dim)

                fix == null -> Text(
                    "No fix yet. Location may be off.",
                    style = MaterialTheme.typography.bodySmall, color = Pact.Warn)

                else -> {
                    Mono(
                        String.format(
                            Locale.US, "%.5f, %.5f  ±%d m",
                            fix.lat, fix.lon, fix.accuracyM?.toInt() ?: -1,
                        ),
                        color = Pact.Ink,
                    )
                    Text(
                        "via ${fix.provider}. Sent to within ~1 m; helpers see ~1 km "
                            + "until they accept.",
                        style = MaterialTheme.typography.bodySmall,
                        color = Pact.Dim,
                        modifier = Modifier.padding(top = Pact.Space1),
                    )
                }
            }
            if (!locating) {
                Spacer(Modifier.height(Pact.Space2))
                GhostButton("Refresh position", onRetry)
            }
        }
    }
}
