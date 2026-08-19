package org.pact.app.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.pact.app.MainActivity

/**
 * The one-time sign-up screen (memory_draft.md 7.1).
 *
 * This is the ONLY screen in the app with text fields, and they are here for a
 * specific reason: a helper has to know whose name to ask for at the door, and
 * an SMS reply needs a number to go to. Neither value ever enters a codec
 * payload -- they go to the server once, are encrypted at rest, and are
 * released only after a helper accepts.
 *
 * There is no password and no verification step. An app that demands account
 * creation from someone trapped in a collapsed building is the wrong product.
 */
@Composable
fun SignupScreen(activity: MainActivity, onGateway: () -> Unit = {},
                 onDone: () -> Unit) {
    val scope = rememberCoroutineScope()

    var role by remember { mutableStateOf("seeker") }
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var groupCode by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }

    val canSubmit = name.trim().length >= 2 && phone.filter { it.isDigit() }.length >= 6 && !busy

    Scaffold { pad ->
        Column(
            Modifier.padding(pad).padding(20.dp).verticalScroll(rememberScrollState()),
        ) {
            Text("PACT", style = MaterialTheme.typography.headlineLarge,
                 fontWeight = FontWeight.Black, color = MaterialTheme.colorScheme.primary)
            Text("Set up once. You will not be asked again.",
                 style = MaterialTheme.typography.bodyMedium,
                 color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f))

            SectionLabel("I am")
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                RoleCard("Asking for help", "I need assistance",
                         selected = role == "seeker", modifier = Modifier.weight(1f)) {
                    role = "seeker"
                }
                RoleCard("Offering help", "I can deliver or assist",
                         selected = role == "helper", modifier = Modifier.weight(1f)) {
                    role = "helper"
                }
            }

            SectionLabel("Your name", "so a helper knows who to look for")
            OutlinedTextField(
                value = name, onValueChange = { name = it },
                singleLine = true, modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("Full name") },
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Words),
            )

            SectionLabel("Phone", "the reply channel when data fails")
            OutlinedTextField(
                value = phone, onValueChange = { phone = it },
                singleLine = true, modifier = Modifier.fillMaxWidth(),
                placeholder = { Text("+91 …") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            )

            if (role == "helper") {
                SectionLabel("Group code", "optional")
                OutlinedTextField(
                    value = groupCode, onValueChange = { groupCode = it.uppercase() },
                    singleLine = true, modifier = Modifier.fillMaxWidth(),
                    placeholder = { Text("e.g. SNJV-4K2") },
                )
                Text(
                    "Leave this blank to volunteer independently. You will still be "
                        + "matched directly.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f),
                    modifier = Modifier.padding(top = 4.dp),
                )
            }

            Spacer(Modifier.height(10.dp))
            PrivacyNote()

            error?.let {
                Spacer(Modifier.height(12.dp))
                Text(it, color = MaterialTheme.colorScheme.error,
                     style = MaterialTheme.typography.bodyMedium)
            }
            notice?.let {
                Spacer(Modifier.height(12.dp))
                Text(it, color = MaterialTheme.colorScheme.secondary,
                     style = MaterialTheme.typography.bodyMedium)
            }

            Spacer(Modifier.height(20.dp))
            Button(
                onClick = {
                    busy = true; error = null; notice = null
                    scope.launch {
                        try {
                            val res = activity.api.signup(
                                role, name.trim(), phone.trim(),
                                groupCode.takeIf { role == "helper" })
                            if (res.optString("status") != "ok") {
                                error = "Sign-up failed: ${res.optString("error")}"
                            } else {
                                activity.session.save(
                                    uid = res.getString("uid"),
                                    token = res.getString("token"),
                                    role = res.getString("role"),
                                    orgId = res.optString("org_id").ifBlank { null },
                                    orgName = res.optString("org_name").ifBlank { null },
                                )
                                // An invalid code is reported, never enforced:
                                // never block someone from helping because a
                                // code failed (memory_draft.md 7.3).
                                val codeErr = res.optString("group_code_error")
                                if (codeErr.isNotBlank() && codeErr != "null") {
                                    notice = "That group code was not recognised. " +
                                        "You are signed up as an independent volunteer."
                                }
                                onDone()
                            }
                        } catch (e: Exception) {
                            error = "Could not reach the server. " +
                                "Sign-up needs a connection once; after that the " +
                                "app works over SMS. (${e.message})"
                        } finally { busy = false }
                    }
                },
                enabled = canSubmit,
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) {
                if (busy) CircularProgressIndicator(
                    modifier = Modifier.size(20.dp), strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary)
                else Text("Continue", style = MaterialTheme.typography.titleMedium)
            }

            // A spare handset can be turned into the SMS receiver without
            // signing up as anyone. Kept off the main path: it is infrastructure,
            // not a role a person has.
            TextButton(onClick = onGateway, modifier = Modifier.fillMaxWidth()) {
                Text("Use this phone as the SMS gateway",
                     style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun RoleCard(title: String, subtitle: String, selected: Boolean,
                     modifier: Modifier = Modifier, onClick: () -> Unit) {
    val colors = if (selected)
        CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primary,
                                contentColor = MaterialTheme.colorScheme.onPrimary)
    else CardDefaults.cardColors()
    Card(onClick = onClick, modifier = modifier.height(96.dp), colors = colors) {
        Column(Modifier.padding(12.dp).fillMaxSize(),
               verticalArrangement = Arrangement.Center) {
            Text(title, style = MaterialTheme.typography.titleSmall,
                 fontWeight = FontWeight.Bold)
            Text(subtitle, style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
fun PrivacyNote() {
    Card(colors = CardDefaults.cardColors(
        containerColor = MaterialTheme.colorScheme.secondary.copy(alpha = 0.10f))) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Your name and number stay private",
                     style = MaterialTheme.typography.titleSmall,
                     fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(6.dp))
            Text(
                "They are never put into a message. What travels is a short code: "
                    + "a situation and a position, no identity. A helper sees only "
                    + "an approximate area until they accept — then, and only then, "
                    + "your exact location and contact are shared with that one person.",
                style = MaterialTheme.typography.bodySmall,
            )
        }
    }
}
