package org.pact.app.ui

import android.provider.Settings
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.WindowInsetsSides
import androidx.compose.foundation.layout.defaultMinSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.only
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * The pieces the console is built from, in Compose.
 *
 * Each one has a counterpart in `web/src/app/admin/admin.css` or
 * `web/src/app/landing.css` and is named after it, so a change on one side has
 * an obvious address on the other: [Panel] is `.card`, [Badge] is `.badge`,
 * [NotePanel] is `.privacy`, [SectionLabel] is `.sectionTitle`, [Mono] is
 * `--font-mono`.
 *
 * Nothing here holds state or knows about the domain. The screens kept their
 * logic; they just stopped drawing their own boxes.
 */

/** The five meanings a surface can carry, matching the console's status
 *  classes. Colour is never the only carrier -- every use site pairs the tone
 *  with a word. */
enum class Tone(val ink: Color, val fill: Color) {
    Neutral(Pact.Dim, Pact.Panel2),
    Llm(Pact.Llm, Pact.LlmFill),
    Good(Pact.Good, Pact.DetFill),
    Warn(Pact.Warn, Pact.WarnFill),
    Bad(Pact.Bad, Pact.BadFill),
}

/* ---- text -------------------------------------------------------------- */

/** `--font-mono`: a string the machine produced. Codec payloads, coordinates,
 *  trace ids, delivery codes. Never used for prose. */
@Composable
fun Mono(
    text: String,
    modifier: Modifier = Modifier,
    color: Color = Pact.Ink,
    size: TextUnit = 13.sp,
    weight: FontWeight = FontWeight.Normal,
) {
    Text(
        text,
        modifier = modifier,
        color = color,
        fontFamily = FiraCode,
        fontSize = size,
        fontWeight = weight,
        lineHeight = (size.value * 1.5f).sp,
    )
}

/**
 * `.sectionTitle`: a small uppercase label with a rule running to the edge, so
 * stacked groups read as separate without introducing a second border colour.
 */
@Composable
fun SectionLabel(text: String, hint: String? = null) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(top = Pact.Space5, bottom = Pact.Space2),
        horizontalArrangement = Arrangement.spacedBy(Pact.Space2),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text.uppercase(),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
            letterSpacing = 1.6.sp,
            color = Pact.Dim,
        )
        if (hint != null) {
            Text(hint, style = MaterialTheme.typography.labelSmall, color = Pact.Faint)
        }
        Box(Modifier.weight(1f).height(1.dp).background(Pact.Line))
    }
}

/* ---- containers -------------------------------------------------------- */

/**
 * `.card`: panel fill, one hairline border, 10px radius. A tone only changes
 * the border and adds a wash at the top, exactly as `.card.awaiting_admin`
 * does -- the fill stays --panel, so a screen of cards does not become a
 * screen of coloured blocks.
 */
@Composable
fun Panel(
    modifier: Modifier = Modifier,
    tone: Tone? = null,
    shape: Shape = RoundedCornerShape(Pact.RadiusLg),
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier
            .fillMaxWidth()
            .background(Pact.Panel, shape)
            .then(
                if (tone == null) Modifier else Modifier.background(
                    Brush.verticalGradient(
                        0f to tone.fill, 1f to Color.Transparent, endY = 340f,
                    ),
                    shape,
                )
            )
            .border(1.dp, tone?.ink?.copy(alpha = 0.5f) ?: Pact.Line, shape),
        content = content,
    )
}

/** `.privacy` / `.gate`: a tinted note. A card that is saying something about
 *  the rules rather than about a record. */
@Composable
fun NotePanel(
    tone: Tone = Tone.Llm,
    modifier: Modifier = Modifier,
    content: @Composable ColumnScope.() -> Unit,
) {
    val shape = RoundedCornerShape(Pact.RadiusLg)
    Column(
        modifier
            .fillMaxWidth()
            .background(tone.fill, shape)
            .border(1.dp, tone.ink.copy(alpha = 0.35f), shape)
            .padding(Pact.Space4),
        content = content,
    )
}

/* ---- small marks ------------------------------------------------------- */

/** `.badge`: uppercase, tracked, tinted. The state a record is in. */
@Composable
fun Badge(text: String, tone: Tone = Tone.Neutral, modifier: Modifier = Modifier) {
    Text(
        text.uppercase(),
        modifier = modifier
            .background(tone.fill, RoundedCornerShape(Pact.RadiusSm))
            .padding(horizontal = 6.dp, vertical = 3.dp),
        color = tone.ink,
        fontFamily = FiraSans,
        fontSize = 10.sp,
        lineHeight = 13.sp,
        fontWeight = FontWeight.SemiBold,
        letterSpacing = 1.1.sp,
    )
}

/** `.chip`: an outlined pill. Says what kind of thing something is, not what
 *  state it is in. */
@Composable
fun OutlineChip(text: String, tone: Tone = Tone.Neutral, modifier: Modifier = Modifier) {
    Text(
        text,
        modifier = modifier
            .border(1.dp, tone.ink.copy(alpha = 0.45f), RoundedCornerShape(999.dp))
            .padding(horizontal = Pact.Space3, vertical = 5.dp),
        color = tone.ink,
        fontFamily = FiraSans,
        fontSize = 11.sp,
        lineHeight = 14.sp,
    )
}

/**
 * `.dot`: a live/idle indicator. Decorative -- the state is always written
 * beside it -- so it is hidden from the screen reader, and it holds still when
 * the device asks for reduced motion.
 */
@Composable
fun StatusDot(on: Boolean, modifier: Modifier = Modifier) {
    val tone = if (on) Tone.Good else Tone.Bad
    val pulses = !on && rememberAnimationsEnabled()
    val alpha by rememberInfiniteTransition(label = "dot").animateFloat(
        initialValue = 1f,
        targetValue = if (pulses) 0.4f else 1f,
        animationSpec = infiniteRepeatable(tween(900), RepeatMode.Reverse),
        label = "dotAlpha",
    )
    Box(
        modifier
            .clearAndSetSemantics { }
            .size(14.dp)
            .background(tone.fill, CircleShape)
            .padding(3.dp)
            .background(tone.ink.copy(alpha = alpha), CircleShape)
    )
}

/** `.lpMark`: the wordmark, tracked wide, with the teal dot that sits in the
 *  same position on the web header. */
@Composable
fun Brand(sub: String? = null, modifier: Modifier = Modifier) {
    Row(modifier, verticalAlignment = Alignment.CenterVertically) {
        Text(
            "PACT",
            fontFamily = FiraSans,
            fontWeight = FontWeight.Bold,
            fontSize = 15.sp,
            letterSpacing = 2.2.sp,
            color = Pact.Ink,
        )
        Spacer(Modifier.width(6.dp))
        Box(Modifier.size(6.dp).background(Pact.Det, CircleShape))
        if (sub != null) {
            Spacer(Modifier.width(Pact.Space3))
            Text(sub, style = MaterialTheme.typography.labelMedium, color = Pact.Dim)
        }
    }
}

/* ---- chrome ------------------------------------------------------------ */

/** `.topbar`: brand on the left, whatever the screen needs on the right, one
 *  hairline underneath and the faint blue wash the console header carries. */
@Composable
fun PactTopBar(sub: String? = null, actions: @Composable RowScope.() -> Unit = {}) {
    Row(
        Modifier
            .fillMaxWidth()
            .background(Pact.Panel)
            .background(
                Brush.verticalGradient(listOf(Pact.Llm.copy(alpha = 0.08f), Color.Transparent))
            )
            .drawBehind {
                drawRect(
                    color = Pact.Line,
                    topLeft = Offset(0f, size.height - 1f),
                    size = Size(size.width, 1f),
                )
            }
            // targetSdk 35 makes edge-to-edge mandatory on Android 15: the
            // window now extends under the status bar whether or not the app
            // asks, and nothing here handled insets -- so the brand rendered
            // on top of the clock. Applied after the background modifiers so
            // the panel fill and its hairline still reach the physical edge;
            // only the content moves down. safeDrawing rather than statusBars
            // so a display cutout is covered too.
            .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Top))
            .heightIn(min = 54.dp)
            .padding(horizontal = Pact.Gutter, vertical = Pact.Space2),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween,
    ) {
        Brand(sub)
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(Pact.Space2),
            content = actions,
        )
    }
}

/** The bar carrying the one decision a screen exists to make. Lifted off the
 *  background by a fill and a hairline rather than a Material tonal elevation
 *  -- the console has no elevation model, it has surfaces and lines. */
@Composable
fun PactBottomBar(content: @Composable ColumnScope.() -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(Pact.Panel)
            .drawBehind { drawRect(color = Pact.Line, size = Size(size.width, 1f)) }
            // safeDrawing covers the gesture bar and the keyboard in one
            // inset, so an open IME cannot bury the button this bar exists for
            // and the two never double-count.
            .windowInsetsPadding(WindowInsets.safeDrawing.only(WindowInsetsSides.Bottom))
            .padding(Pact.Space4),
        content = content,
    )
}

/**
 * Every screen's frame: console background, top bar, optional bottom bar.
 * `hero` paints the landing page's two radial glows behind the content --
 * worth it on the first screen someone sees, noise everywhere else.
 */
@Composable
fun PactScaffold(
    sub: String? = null,
    hero: Boolean = false,
    actions: @Composable RowScope.() -> Unit = {},
    bottomBar: @Composable () -> Unit = {},
    content: @Composable (PaddingValues) -> Unit,
) {
    val base = Modifier.background(Pact.Bg)
    Scaffold(
        // Transparent, so the glow drawn by the modifier below is not painted
        // over by Scaffold's own container fill.
        containerColor = Color.Transparent,
        contentColor = Pact.Ink,
        modifier = if (hero) base.heroGlow() else base,
        // The two bars consume their own insets above, so the frame only has
        // to cover the case of a screen with no bottom bar, whose content
        // would otherwise scroll under the gesture bar.
        contentWindowInsets = WindowInsets.safeDrawing.only(WindowInsetsSides.Bottom),
        topBar = { PactTopBar(sub, actions) },
        bottomBar = bottomBar,
        content = content,
    )
}

/** `--grad-hero`: two radial washes, blue from the top left and teal from the
 *  top right. Same geometry as the CSS, expressed against the drawn size. */
fun Modifier.heroGlow(): Modifier = drawBehind {
    if (size.minDimension <= 0f) return@drawBehind
    drawRect(
        Brush.radialGradient(
            colors = listOf(Pact.Llm.copy(alpha = 0.16f), Color.Transparent),
            center = Offset(size.width * 0.12f, -size.height * 0.04f),
            radius = size.width * 1.3f,
        )
    )
    drawRect(
        Brush.radialGradient(
            colors = listOf(Pact.Det.copy(alpha = 0.11f), Color.Transparent),
            center = Offset(size.width * 0.96f, size.height * 0.06f),
            radius = size.width,
        )
    )
}

/* ---- controls ---------------------------------------------------------- */

/** `.fire` / `.lpBtnPrimary`: the blue commit. One per screen. */
@Composable
fun PrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    busy: Boolean = false,
) {
    Button(
        onClick = onClick,
        enabled = enabled && !busy,
        modifier = modifier.defaultMinSize(minHeight = 52.dp),
        shape = RoundedCornerShape(Pact.Radius),
        colors = ButtonDefaults.buttonColors(
            containerColor = Pact.Llm,
            contentColor = Pact.OnAccent,
            disabledContainerColor = Pact.Llm.copy(alpha = 0.26f),
            disabledContentColor = Pact.OnAccent.copy(alpha = 0.6f),
        ),
    ) {
        if (busy) {
            CircularProgressIndicator(
                Modifier.size(18.dp), strokeWidth = 2.dp, color = Pact.OnAccent,
            )
            Spacer(Modifier.width(Pact.Space2))
        }
        Text(text, style = MaterialTheme.typography.titleMedium)
    }
}

/** `.lpBtnGhost`: panel fill, hairline border. The secondary way out of a
 *  screen. `tone` tints it for the one destructive pair (accept/decline). */
@Composable
fun GhostButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    tone: Color = Pact.Ink,
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.defaultMinSize(minHeight = Pact.Hit),
        shape = RoundedCornerShape(Pact.Radius),
        border = BorderStroke(
            1.dp,
            if (tone == Pact.Ink) Pact.LineStrong else tone.copy(alpha = 0.45f),
        ),
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = Pact.Panel2,
            contentColor = tone,
            disabledContentColor = Pact.Faint,
        ),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

/** `.linkBtn`: a quiet action that is not a decision. */
@Composable
fun LinkButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    TextButton(
        onClick = onClick,
        modifier = modifier.defaultMinSize(minHeight = Pact.Hit),
        shape = RoundedCornerShape(Pact.Radius),
        colors = ButtonDefaults.textButtonColors(contentColor = Pact.Dim),
    ) {
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

/* ---- helpers ----------------------------------------------------------- */

/**
 * The Android equivalent of `prefers-reduced-motion`, which the console
 * honours. Read once per screen: someone who turns animations off mid-demo can
 * live with the next screen picking it up.
 */
@Composable
fun rememberAnimationsEnabled(): Boolean {
    val resolver = LocalContext.current.contentResolver
    return remember {
        Settings.Global.getFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) != 0f
    }
}

/* ---- landing-page marks ------------------------------------------------ */

/** `.lpEyebrow`: a pill above the title with the live dot in it. Says the
 *  system is doing something before any text has to. */
@Composable
fun Eyebrow(text: String, modifier: Modifier = Modifier) {
    val shape = RoundedCornerShape(999.dp)
    Row(
        modifier
            .background(Pact.Panel, shape)
            .border(1.dp, Pact.Line, shape)
            .padding(start = Pact.Space3, end = Pact.Space4, top = 6.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PulseDot()
        Spacer(Modifier.width(Pact.Space2))
        Text(text, style = MaterialTheme.typography.labelMedium, color = Pact.Dim)
    }
}

/** `.lpPulse`: a teal dot with a ring that expands and fades. Decorative, so
 *  it is hidden from the screen reader and still when motion is reduced. */
@Composable
private fun PulseDot() {
    val enabled = rememberAnimationsEnabled()
    val ring by rememberInfiniteTransition(label = "pulse").animateFloat(
        initialValue = 0f,
        targetValue = if (enabled) 1f else 0f,
        animationSpec = infiniteRepeatable(tween(2400), RepeatMode.Restart),
        label = "pulseRing",
    )
    Box(
        Modifier
            .clearAndSetSemantics { }
            .size(7.dp)
            .drawBehind {
                if (ring > 0f) {
                    drawCircle(
                        color = Pact.Det.copy(alpha = 0.55f * (1f - ring)),
                        radius = size.minDimension / 2f + 14f * ring,
                    )
                }
            }
            .background(Pact.Det, CircleShape)
    )
}

/** `.lpTitle` with `.lpTitleAccent`: the second clause carries the blue-to-teal
 *  gradient, so the sentence turns at the same point it does on the web. */
@Composable
fun HeroTitle(lead: String, accent: String, modifier: Modifier = Modifier) {
    Text(
        buildAnnotatedString {
            append(lead)
            withStyle(
                SpanStyle(brush = Brush.linearGradient(listOf(Pact.Llm, Pact.Det)))
            ) { append(accent) }
        },
        modifier = modifier,
        style = MaterialTheme.typography.headlineLarge,
        color = Pact.Ink,
    )
}

/** The console's form control: `--panel2` fill, hairline border, --llm on
 *  focus. Material's default underline field had no border at all against a
 *  dark card, so a text input and a paragraph looked the same. */
@Composable
fun PactTextField(
    value: String,
    onValueChange: (String) -> Unit,
    placeholder: String,
    modifier: Modifier = Modifier,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier.fillMaxWidth(),
        singleLine = true,
        shape = RoundedCornerShape(Pact.Radius),
        textStyle = MaterialTheme.typography.bodyMedium,
        placeholder = {
            Text(placeholder, style = MaterialTheme.typography.bodyMedium, color = Pact.Faint)
        },
        keyboardOptions = keyboardOptions,
        colors = OutlinedTextFieldDefaults.colors(
            focusedContainerColor = Pact.Panel2,
            unfocusedContainerColor = Pact.Panel2,
            focusedBorderColor = Pact.Llm,
            unfocusedBorderColor = Pact.Line,
            focusedTextColor = Pact.Ink,
            unfocusedTextColor = Pact.Ink,
            cursorColor = Pact.Llm,
        ),
    )
}
