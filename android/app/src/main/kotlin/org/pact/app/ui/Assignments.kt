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
import org.json.JSONObject
import org.pact.app.MainActivity

/**
 * Helper mode.
 *
 * This screen is where the privacy model becomes visible to the person it
 * protects and the person it constrains at the same time. Before accepting, a
 * helper sees a need and an approximate area. Accepting is the state
 * transition that releases the seeker's exact position, name and contact --
 * and the server, not this screen, is what enforces that. The app renders
 * whatever the projection returned; it has no unredacted copy to slip.
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

    Scaffold { pad ->
        Column(Modifier.padding(pad).padding(horizontal = 20.dp)
                   .verticalScroll(rememberScrollState())) {

            Spacer(Modifier.height(16.dp))
            Row(Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween) {
                Column {
                    Text("Assignments", style = MaterialTheme.typography.headlineMedium,
                         fontWeight = FontWeight.Black)
                    Text(activity.session.orgName ?: "Independent volunteer",
                         style = MaterialTheme.typography.bodyMedium,
                         color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))
                }
                TextButton(onClick = {
                    scope.launch {
                        runCatching { activity.api.signout() }
                        activity.session.signOut()
                        onSignedOut()
                    }
                }) { Text("Sign out") }
            }

            Spacer(Modifier.height(12.dp))
            if (loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            error?.let {
                Text("Could not load: $it", color = MaterialTheme.colorScheme.error,
                     style = MaterialTheme.typography.bodyMedium)
            }
            if (!loading && rows.isEmpty() && error == null) {
                Text("Nothing assigned to you yet.",
                     style = MaterialTheme.typography.bodyMedium)
            }

            rows.forEach { row ->
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
                Spacer(Modifier.height(10.dp))
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun AssignmentCard(row: JSONObject, onAccept: () -> Unit, onDecline: () -> Unit) {
    val revealed = row.optBoolean("revealed")
    val state = row.optString("state")
    val alloc = row.optJSONObject("allocation") ?: JSONObject()
    val seeker = row.optJSONObject("seeker") ?: JSONObject()

    Card {
        Column(Modifier.padding(16.dp)) {
            Text(
                "${alloc.optInt("qty")} × ${alloc.optString("resource").replace('_', ' ')}",
                style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            Text("ETA ${alloc.optInt("eta_min")} min · ${alloc.optString("name")}",
                 style = MaterialTheme.typography.bodyMedium)

            Spacer(Modifier.height(10.dp))
            AssistChip(onClick = {}, label = {
                Text(if (revealed) "Details released" else "Approximate area only")
            })

            Spacer(Modifier.height(10.dp))
            // Rendered straight from the projected payload. When `revealed` is
            // false these keys are ABSENT, not blanked -- so there is nothing
            // here to accidentally display.
            Text("Position: ${seeker.optDouble("lat", 0.0)}, " +
                     "${seeker.optDouble("lon", 0.0)}" +
                     if (revealed) "" else "  (~1 km)",
                 style = MaterialTheme.typography.bodySmall)

            if (revealed) {
                Text("Name: ${seeker.optString("name", "—")}",
                     style = MaterialTheme.typography.bodySmall)
                Text("Contact: ${seeker.optString("contact", "—")}",
                     style = MaterialTheme.typography.bodySmall)
                row.optString("delivery_code").takeIf { it.isNotBlank() }?.let {
                    Spacer(Modifier.height(8.dp))
                    Text("Delivery code $it",
                         style = MaterialTheme.typography.titleMedium,
                         fontWeight = FontWeight.Bold,
                         color = MaterialTheme.colorScheme.primary)
                }
            } else {
                Text("Name and contact are released when you accept.",
                     style = MaterialTheme.typography.bodySmall,
                     color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))
            }

            row.optString("justification").takeIf { it.isNotBlank() && it != "null" }?.let {
                Spacer(Modifier.height(8.dp))
                Text(it, style = MaterialTheme.typography.bodySmall,
                     color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.75f))
            }

            Spacer(Modifier.height(12.dp))
            when (state) {
                "awaiting_assignment" -> Text(
                    "Your organization must assign a named helper before this can "
                        + "be accepted.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f))

                "accepted" -> Text("Accepted. Go when ready.",
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.secondary)

                "declined" -> Text("Declined. Being reallocated.",
                    style = MaterialTheme.typography.bodySmall)

                else -> Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Button(onClick = onAccept, modifier = Modifier.weight(1f)) {
                        Text("Accept")
                    }
                    OutlinedButton(onClick = onDecline, modifier = Modifier.weight(1f)) {
                        Text("Decline")
                    }
                }
            }
        }
    }
}
