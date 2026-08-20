package org.pact.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import org.json.JSONObject
import org.pact.app.MainActivity
import java.util.Locale

/**
 * Helper mode.
 *
 * This screen is where the privacy model becomes visible to the person it
 * protects and the person it constrains at the same time. Before accepting, a
 * helper sees a need and an approximate area. Accepting is the state
 * transition that releases the seeker's exact position, name and contact --
 * and the server, not this screen, is what enforces that. The app renders
 * whatever the projection returned; it has no unredacted copy to slip.
 *
 * The shared/held tags are the console's `.pLabel`, deliberately: an operator
 * looking over a helper's shoulder should recognise the same marks they see on
 * the privacy panel in the admin console.
 */
@Composable
fun AssignmentsScreen(activity: MainActivity, onSignedOut: () -> Unit) {
    val scope = rememberCoroutineScope()
    var rows by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    // Individual volunteers act as themselves; an org-dispatched helper is
    // named on the match by their organization. Both resolve to the id the
    // backend checks ownership against.
    val actorId = activity.session.orgId ?: activity.session.uid.orEmpty()

    suspend fun refresh() {
        loading = true; error = null
        try { rows = activity.api.assignments(actorId).let { arr ->
                (0 until arr.length()).map { arr.getJSONObject(it) } } }
        catch (e: Exception) { error = e.message }
        finally { loading = false }
    }

    LaunchedEffect(Unit) { refresh() }

    PactScaffold(
        sub = activity.session.orgName ?: "Independent volunteer",
        actions = {
            LinkButton("Sign out", onClick = {
                // Activity-scoped: signing out navigates away, and the
                // server call must not be cancelled by that navigation.
                activity.lifecycleScope.launch {
                    runCatching { activity.api.signout() }
                    activity.session.signOut()
                    onSignedOut()
                }
            })
        },
    ) { pad ->
        Column(Modifier.padding(pad).padding(horizontal = Pact.Gutter)
                   .verticalScroll(rememberScrollState())) {

            Spacer(Modifier.height(Pact.Space5))
            Text("Assignments", style = MaterialTheme.typography.headlineMedium,
                 color = Pact.Ink)
            Text("What has been allocated to you, and why.",
                 style = MaterialTheme.typography.bodyMedium, color = Pact.Dim,
                 modifier = Modifier.padding(top = Pact.Space1))

            Spacer(Modifier.height(Pact.Space4))
            if (loading) {
                LinearProgressIndicator(
                    modifier = Modifier.fillMaxWidth().height(2.dp),
                    color = Pact.Llm,
                    trackColor = Pact.Panel2,
                )
            }
            error?.let {
                NotePanel(Tone.Bad) {
                    Text("Could not load: $it",
                         style = MaterialTheme.typography.bodySmall, color = Pact.Ink)
                }
            }
            if (!loading && rows.isEmpty() && error == null) {
                Panel {
                    Column(Modifier.padding(Pact.Space5)) {
                        Text("Nothing assigned to you yet.",
                             style = MaterialTheme.typography.titleSmall, color = Pact.Ink)
                        Text("This screen fills in when an allocation is approved.",
                             style = MaterialTheme.typography.bodySmall, color = Pact.Faint,
                             modifier = Modifier.padding(top = Pact.Space1))
                    }
                }
            }

            rows.forEach { row ->
                Spacer(Modifier.height(Pact.Space3))
                AssignmentCard(row, onAccept = {
                    scope.launch {
                        runCatching {
                            activity.api.accept(row.getString("match_id"), actorId)
                        }.onFailure { error = it.message }
                        refresh()
                    }
                }, onDecline = {
                    scope.launch {
                        runCatching {
                            activity.api.decline(row.getString("match_id"), actorId,
                                                 "declined from the app")
                        }.onFailure { error = it.message }
                        refresh()
                    }
                })
            }
            Spacer(Modifier.height(Pact.Space6))
        }
    }
}

@Composable
private fun AssignmentCard(row: JSONObject, onAccept: () -> Unit, onDecline: () -> Unit) {
    val revealed = row.optBoolean("revealed")
    val state = row.optString("state")
    val alloc = row.optJSONObject("allocation") ?: JSONObject()
    val seeker = row.optJSONObject("seeker") ?: JSONObject()

    // Same status vocabulary as the console's card classes: warn while it is
    // waiting on a human, good once it is committed, quiet once it is out of
    // this helper's hands.
    val tone = when (state) {
        "accepted" -> Tone.Good
        "awaiting_assignment" -> Tone.Warn
        "declined" -> Tone.Neutral
        else -> Tone.Llm
    }

    Panel(tone = tone) {
        Column(Modifier.padding(Pact.Space4)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top,
            ) {
                Text(
                    "${alloc.optInt("qty")} × ${alloc.optString("resource").replace('_', ' ')}",
                    style = MaterialTheme.typography.titleLarge,
                    color = Pact.Ink,
                    modifier = Modifier.weight(1f),
                )
                // One word, not the raw state: "awaiting_assignment" set as a
                // badge is wider than the title it sits beside. The sentence
                // at the foot of the card carries the detail.
                Badge(
                    when (state) {
                        "awaiting_assignment" -> "awaiting"
                        "" -> "offered"
                        else -> state
                    },
                    tone,
                )
            }
            Text("ETA ${alloc.optInt("eta_min")} min · ${alloc.optString("name")}",
                 style = MaterialTheme.typography.bodySmall, color = Pact.Dim,
                 modifier = Modifier.padding(top = Pact.Space1))

            Spacer(Modifier.height(Pact.Space3))

            // Rendered straight from the projected payload. When `revealed` is
            // false these keys are ABSENT, not blanked -- so there is nothing
            // here to accidentally display.
            Column(verticalArrangement = Arrangement.spacedBy(Pact.Space2)) {
                Field(
                    if (revealed) "shared" else "masked",
                    if (revealed) Tone.Good else Tone.Warn,
                    "Position",
                ) {
                    Mono(
                        String.format(
                            Locale.US, "%.5f, %.5f",
                            seeker.optDouble("lat", 0.0), seeker.optDouble("lon", 0.0),
                        ) + if (revealed) "" else "  (~1 km)",
                        color = Pact.Ink,
                    )
                }

                if (revealed) {
                    Field("shared", Tone.Good, "Name") {
                        Text(seeker.optString("name", "—"),
                             style = MaterialTheme.typography.bodyMedium, color = Pact.Ink)
                    }
                    Field("shared", Tone.Good, "Contact") {
                        Mono(seeker.optString("contact", "—"), color = Pact.Ink)
                    }
                } else {
                    Field("held", Tone.Bad, "Name and contact") {
                        Text("Released when you accept.",
                             style = MaterialTheme.typography.bodySmall, color = Pact.Dim)
                    }
                }
            }

            if (revealed) {
                row.optString("delivery_code").takeIf { it.isNotBlank() }?.let {
                    Spacer(Modifier.height(Pact.Space3))
                    NotePanel(Tone.Llm) {
                        Badge("Delivery code", Tone.Llm)
                        Spacer(Modifier.height(Pact.Space1))
                        Mono(it, size = 22.sp, color = Pact.Llm)
                    }
                }
            }

            row.optString("justification").takeIf { it.isNotBlank() && it != "null" }?.let {
                Spacer(Modifier.height(Pact.Space3))
                Text(it, style = MaterialTheme.typography.bodySmall, color = Pact.Dim)
            }

            Spacer(Modifier.height(Pact.Space4))
            when (state) {
                "awaiting_assignment" -> Text(
                    "Your organization must assign a named helper before this can "
                        + "be accepted.",
                    style = MaterialTheme.typography.bodySmall, color = Pact.Warn)

                "accepted" -> Text("Accepted. Go when ready.",
                    style = MaterialTheme.typography.titleSmall, color = Pact.Good)

                "declined" -> Text("Declined. Being reallocated.",
                    style = MaterialTheme.typography.bodySmall, color = Pact.Faint)

                else -> Row(horizontalArrangement = Arrangement.spacedBy(Pact.Space3)) {
                    PrimaryButton("Accept", onAccept, modifier = Modifier.weight(1f))
                    GhostButton("Decline", onDecline, modifier = Modifier.weight(1f),
                                tone = Pact.Bad)
                }
            }
        }
    }
}

/** `.privacy` row: the disclosure tag, then the field name, then the value.
 *  The tag comes first because on this screen it is the more important half. */
@Composable
private fun Field(tag: String, tone: Tone, label: String, value: @Composable () -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(Pact.Space3)) {
        Badge(tag, tone, Modifier.width(64.dp))
        Column {
            Text(label, style = MaterialTheme.typography.labelSmall, color = Pact.Faint)
            value()
        }
    }
}
