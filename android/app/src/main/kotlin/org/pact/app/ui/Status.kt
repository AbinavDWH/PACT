package org.pact.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import org.json.JSONObject
import org.pact.app.MainActivity

/**
 * What happened to the request.
 *
 * The app used to be write-only: someone tapped six chips, saw "Request sent",
 * and that was the last thing the system ever said to them -- while behind the
 * scenes an operator approved or rejected the allocation on the console. The
 * person with the most at stake in that decision was the only one who could
 * not see it.
 *
 * The verdict text is not written here. It comes from the verdict table in
 * `backend/app/routers/seeker.py`, so what a rejection says to someone in a
 * disaster is one reviewable table on the server rather than a string literal
 * on a handset that may not be updated for a year. This screen decides how it
 * looks, not what it says.
 *
 * It polls rather than waits on a socket: this runs on a phone with an
 * unreliable connection, and a five-second GET that fails is recoverable in a
 * way a dropped WebSocket is not. Polling stops as soon as every request is
 * settled, so it is not a battery drain that runs forever.
 */
private const val POLL_MS = 5_000L

@Composable
fun StatusScreen(activity: MainActivity, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    val uid = activity.session.uid.orEmpty()

    var rows by remember { mutableStateOf<List<JSONObject>>(emptyList()) }
    var settled by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }

    suspend fun refresh() {
        try {
            val res = activity.api.myRequests(uid)
            val arr = res.optJSONArray("requests")
            rows = (0 until (arr?.length() ?: 0)).map { arr!!.getJSONObject(it) }
            settled = res.optBoolean("settled", false)
            error = null
        } catch (e: Exception) {
            // Named rather than swallowed: "could not reach the server" and
            // "the operator has not decided yet" are completely different
            // answers and must never look the same on this screen.
            error = e.message ?: "could not reach the server"
        } finally {
            loading = false
        }
    }

    // One effect, not two: the first pass is the load and every pass after it
    // is the poll. It ends only when the server says every request is settled
    // -- a rejection is NOT settled, because it triggers a replan and the next
    // verdict is still coming.
    LaunchedEffect(uid) {
        while (isActive) {
            refresh()
            if (settled) break
            delay(POLL_MS)
        }
    }

    PactScaffold(
        sub = "Status",
        actions = { StatusDot(on = error == null) },
        bottomBar = {
            PactBottomBar {
                Row(horizontalArrangement = Arrangement.spacedBy(Pact.Space3)) {
                    GhostButton("Back", onBack, modifier = Modifier.weight(1f))
                    PrimaryButton(
                        "Refresh",
                        onClick = { scope.launch { loading = true; refresh() } },
                        busy = loading,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
        },
    ) { pad ->
        Column(
            Modifier.padding(pad).padding(horizontal = Pact.Gutter)
                .verticalScroll(rememberScrollState())
                // Announced when it changes: the whole point of this screen is
                // that the answer arrives while it is already open.
                .semantics { liveRegion = LiveRegionMode.Polite },
        ) {
            Spacer(Modifier.height(Pact.Space5))
            Text("Your requests", style = MaterialTheme.typography.headlineMedium,
                 color = Pact.Ink)
            Text(
                if (settled) "Up to date."
                else "Checking every few seconds while a decision is outstanding.",
                style = MaterialTheme.typography.bodyMedium,
                color = Pact.Dim,
                modifier = Modifier.padding(top = Pact.Space1),
            )

            error?.let {
                Spacer(Modifier.height(Pact.Space4))
                NotePanel(Tone.Warn) {
                    Badge("Offline", Tone.Warn)
                    Spacer(Modifier.height(Pact.Space2))
                    Text(
                        "Could not reach the server ($it). This screen needs data — "
                            + "a request sent by SMS still arrived, it just cannot be "
                            + "checked from here without a connection.",
                        style = MaterialTheme.typography.bodySmall, color = Pact.Ink,
                    )
                }
            }

            if (rows.isEmpty() && error == null) {
                Spacer(Modifier.height(Pact.Space4))
                Panel {
                    Column(Modifier.padding(Pact.Space5)) {
                        Text(
                            if (loading) "Looking for your requests…"
                            else "Nothing sent from this phone yet.",
                            style = MaterialTheme.typography.titleSmall, color = Pact.Ink,
                        )
                        if (!loading) {
                            Text(
                                "A request appears here the moment it reaches the "
                                    + "coordination system.",
                                style = MaterialTheme.typography.bodySmall,
                                color = Pact.Faint,
                                modifier = Modifier.padding(top = Pact.Space1),
                            )
                        }
                    }
                }
            }

            rows.forEach { row ->
                Spacer(Modifier.height(Pact.Space3))
                RequestStatusCard(row)
            }

            Spacer(Modifier.height(Pact.Space6))
        }
    }
}

/**
 * One request, one verdict.
 *
 * The verdict word is the largest thing on the card and the tone repeats it,
 * because the question this screen exists to answer is a single word long.
 */
@Composable
private fun RequestStatusCard(row: JSONObject) {
    val verdict = row.optString("verdict")
    val tone = toneFor(verdict)

    Panel(tone = tone) {
        Column(Modifier.padding(Pact.Space4)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Badge(verdict.ifBlank { "pending" }, tone)
                Mono(row.optString("request_id"), color = Pact.Faint, size = 11.sp)
            }

            Spacer(Modifier.height(Pact.Space2))
            Text(row.optString("headline"), style = MaterialTheme.typography.titleLarge,
                 color = Pact.Ink)
            Text(row.optString("detail"), style = MaterialTheme.typography.bodySmall,
                 color = Pact.Dim, modifier = Modifier.padding(top = Pact.Space1))

            // What was asked for, in the seeker's own words rather than the
            // codec's: "water kits", not "water_kits".
            val need = row.optString("need").replace('_', ' ')
            if (need.isNotBlank()) {
                Spacer(Modifier.height(Pact.Space3))
                Text(
                    "You asked for ${row.optInt("quantity")} × $need",
                    style = MaterialTheme.typography.bodySmall, color = Pact.Faint,
                )
            }

            val allocations = row.optJSONArray("allocations")
            if (allocations != null && allocations.length() > 0) {
                Spacer(Modifier.height(Pact.Space2))
                Column(verticalArrangement = Arrangement.spacedBy(Pact.Space1)) {
                    for (i in 0 until allocations.length()) {
                        val a = allocations.getJSONObject(i)
                        // No supplier name: the SEEKER audience masks helper
                        // identity until a helper accepts, and the server has
                        // already removed it. There is nothing to print here.
                        Text(
                            "${a.optInt("qty")} × ${a.optString("resource").replace('_', ' ')}"
                                + " · about ${a.optInt("eta_min")} min away",
                            style = MaterialTheme.typography.bodyMedium, color = Pact.Ink,
                        )
                    }
                }
                val unmet = row.optInt("unmet")
                if (unmet > 0) {
                    Text(
                        "$unmet still unallocated and being worked on.",
                        style = MaterialTheme.typography.bodySmall, color = Pact.Warn,
                        modifier = Modifier.padding(top = Pact.Space1),
                    )
                }
            }

            row.optString("delivery_code").takeIf { it.isNotBlank() }?.let { code ->
                Spacer(Modifier.height(Pact.Space3))
                NotePanel(Tone.Llm) {
                    Badge("Delivery code", Tone.Llm)
                    Spacer(Modifier.height(Pact.Space1))
                    Mono(code, size = 22.sp, color = Pact.Llm)
                    Text(
                        "Read this out to the person who arrives. It is how they "
                            + "confirm they found the right household.",
                        style = MaterialTheme.typography.bodySmall, color = Pact.Dim,
                        modifier = Modifier.padding(top = Pact.Space1),
                    )
                }
            }
        }
    }
}

/** The console's colour vocabulary, applied to the five outcomes the server
 *  can return. An unrecognised verdict is neutral, never good. */
private fun toneFor(verdict: String): Tone = when (verdict) {
    "approved" -> Tone.Good
    "rejected" -> Tone.Bad
    "unmet" -> Tone.Warn
    "pending" -> Tone.Llm
    else -> Tone.Neutral
}
