package org.pact.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.lifecycleScope
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
 *
 * Visually this is the app's front door, so it borrows the web landing page's
 * treatment -- the eyebrow pill, the gradient-turned headline, the two role
 * cards laid out like `.lpDoor`, and the shared/never-shared boundary block --
 * rather than the dense console styling the later screens use.
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

    PactScaffold(sub = "Set up", hero = true) { pad ->
        Column(
            Modifier.padding(pad).padding(horizontal = Pact.Gutter)
                .verticalScroll(rememberScrollState()),
        ) {
            Spacer(Modifier.height(Pact.Space5))
            Eyebrow("Works when the network does not")

            Spacer(Modifier.height(Pact.Space4))
            HeroTitle("Set up once.", " You will not be asked again.")

            Spacer(Modifier.height(Pact.Space3))
            Text(
                "Two fields and a choice. After this the app works with no typing, "
                    + "and over SMS when there is no data.",
                style = MaterialTheme.typography.bodyMedium,
                color = Pact.Dim,
            )

            SectionLabel("I am")
            Row(horizontalArrangement = Arrangement.spacedBy(Pact.Space3)) {
                RoleCard("Seeker", "Asking for help", "I need assistance",
                         selected = role == "seeker", modifier = Modifier.weight(1f)) {
                    role = "seeker"
                }
                RoleCard("Helper", "Offering help", "I can deliver or assist",
                         selected = role == "helper", modifier = Modifier.weight(1f)) {
                    role = "helper"
                }
            }

            SectionLabel("Your name", "so a helper knows who to look for")
            PactTextField(
                value = name, onValueChange = { name = it },
                placeholder = "Full name",
                keyboardOptions = KeyboardOptions(
                    capitalization = KeyboardCapitalization.Words),
            )

            SectionLabel("Phone", "the reply channel when data fails")
            PactTextField(
                value = phone, onValueChange = { phone = it },
                placeholder = "+91 …",
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            )

            if (role == "helper") {
                SectionLabel("Group code", "optional")
                PactTextField(
                    value = groupCode, onValueChange = { groupCode = it.uppercase() },
                    placeholder = "e.g. SNJV-4K2",
                )
                Text(
                    "Leave this blank to volunteer independently. You will still be "
                        + "matched directly.",
                    style = MaterialTheme.typography.bodySmall,
                    color = Pact.Faint,
                    modifier = Modifier.padding(top = Pact.Space2),
                )
            }

            Spacer(Modifier.height(Pact.Space5))
            PrivacyNote()

            error?.let {
                Spacer(Modifier.height(Pact.Space3))
                NotePanel(Tone.Bad) {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = Pact.Ink)
                }
            }
            notice?.let {
                Spacer(Modifier.height(Pact.Space3))
                NotePanel(Tone.Warn) {
                    Text(it, style = MaterialTheme.typography.bodySmall, color = Pact.Ink)
                }
            }

            Spacer(Modifier.height(Pact.Space5))
            PrimaryButton(
                text = "Continue",
                onClick = {
                    busy = true; error = null; notice = null
                    // Activity-scoped: this completes by navigating away,
                    // which would cancel a composition scope mid-request.
                    activity.lifecycleScope.launch {
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
                busy = busy,
                modifier = Modifier.fillMaxWidth(),
            )

            // A spare handset can be turned into the SMS receiver without
            // signing up as anyone. Kept off the main path: it is infrastructure,
            // not a role a person has.
            LinkButton("Use this phone as the SMS gateway", onGateway,
                       modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(Pact.Space6))
        }
    }
}

/** `.lpDoor`: a bordered panel that turns blue when it is the chosen one. The
 *  tag above the title is what makes the two cards scannable at arm's length. */
@Composable
private fun RoleCard(tag: String, title: String, subtitle: String, selected: Boolean,
                     modifier: Modifier = Modifier, onClick: () -> Unit) {
    val shape = RoundedCornerShape(Pact.RadiusLg)
    Column(
        modifier
            .background(if (selected) Pact.LlmFill else Pact.Panel, shape)
            .border(1.dp, if (selected) Pact.Llm.copy(alpha = 0.6f) else Pact.Line, shape)
            .clickable(onClick = onClick)
            .semantics { this.role = Role.RadioButton; this.selected = selected }
            .heightIn(min = 108.dp)
            .padding(Pact.Space4),
        verticalArrangement = Arrangement.spacedBy(Pact.Space1),
    ) {
        Text(
            tag.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 1.4.sp,
            color = if (selected) Pact.Llm else Pact.Faint,
        )
        Text(title, style = MaterialTheme.typography.titleSmall, color = Pact.Ink)
        Text(subtitle, style = MaterialTheme.typography.bodySmall, color = Pact.Dim)
    }
}

/** The web landing page's privacy boundary, stacked for a phone. Two tagged
 *  lists rather than one paragraph: the thing a seeker needs to be able to
 *  check in five seconds is which side of the line their name is on. */
@Composable
fun PrivacyNote() {
    NotePanel(Tone.Good) {
        Text(
            "What travels is a short code: a situation and a position, no identity.",
            style = MaterialTheme.typography.bodySmall,
            color = Pact.Ink,
        )
        Spacer(Modifier.height(Pact.Space3))
        BoundaryList(
            "Shared", Tone.Good,
            listOf(
                "What you need, and how urgent",
                "An area, rounded to about a kilometre",
            ),
        )
        Spacer(Modifier.height(Pact.Space3))
        BoundaryList(
            "Never shared until a helper accepts", Tone.Bad,
            listOf(
                "Your name and phone number",
                "Your exact position",
            ),
        )
    }
}

/** `.lpBoundaryCol`: a tag over a short list. */
@Composable
private fun BoundaryList(tag: String, tone: Tone, items: List<String>) {
    Column(verticalArrangement = Arrangement.spacedBy(Pact.Space1)) {
        Badge(tag, tone)
        items.forEach {
            Row(horizontalArrangement = Arrangement.spacedBy(Pact.Space2)) {
                Text("·", style = MaterialTheme.typography.bodySmall, color = tone.ink)
                Text(it, style = MaterialTheme.typography.bodySmall, color = Pact.Dim)
            }
        }
    }
}
