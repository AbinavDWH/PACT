package org.pact.app.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import org.pact.app.R

/**
 * The app's half of one design system.
 *
 * Every value here is the Kotlin spelling of a custom property in
 * `web/src/app/globals.css`. The console and the handset are two windows onto
 * the same operation, and until now they looked like two products: the web
 * side is a dark operations console in Fira Sans/Fira Code, the app was an
 * amber-on-white Material default. An operator switching between them had to
 * re-learn what a colour meant.
 *
 * The rule is one-directional: globals.css owns the palette, this file mirrors
 * it. If a token changes there, change it here -- do not invent an app-only
 * colour.
 */
object Pact {
    // --- surfaces (--bg, --panel, --panel2, --panel3, --line) ------------
    val Bg = Color(0xFF0B0F14)
    val Panel = Color(0xFF121820)
    val Panel2 = Color(0xFF171F2A)
    val Panel3 = Color(0xFF1D2634)
    val Line = Color(0xFF223041)
    val LineStrong = Color(0x732E4056)

    // --- text (--ink, --dim, --faint) ------------------------------------
    // --faint is the accessibility-corrected value, not the original #5d7086
    // that measured 3.5:1 on --panel. Contrast is worse on a phone in daylight
    // than on a monitor, so the corrected value matters more here, not less.
    val Ink = Color(0xFFE6EDF6)
    val Dim = Color(0xFF8FA3B8)
    val Faint = Color(0xFF7A8DA6)

    // --- semantic accents -------------------------------------------------
    // Llm/Det carry the same meaning as on the console: blue is a judgement
    // something made, teal is a fact the system computed or confirmed.
    val Llm = Color(0xFF7AA2FF)
    val Det = Color(0xFF4EC9A8)
    val Good = Det
    val Warn = Color(0xFFFFB454)
    val Bad = Color(0xFFFF6B6B)
    val OnAccent = Color(0xFF08111A)

    // Tinted fills, derived rather than re-typed at each use site.
    val LlmFill = Llm.copy(alpha = 0.14f)
    val DetFill = Det.copy(alpha = 0.14f)
    val WarnFill = Warn.copy(alpha = 0.14f)
    val BadFill = Bad.copy(alpha = 0.14f)

    // --- spacing scale ----------------------------------------------------
    // The console is dense because an operator wants many runs on one screen.
    // The phone is not: it is used one-handed, outdoors, in a hurry, so the
    // scale is the same ladder with the bottom two rungs skipped.
    val Space1 = 4.dp
    val Space2 = 8.dp
    val Space3 = 12.dp
    val Space4 = 16.dp
    val Space5 = 24.dp
    val Space6 = 32.dp

    val RadiusSm = 4.dp
    val Radius = 6.dp
    val RadiusLg = 10.dp

    /** The screen gutter. `--gutter` clamps on the web; a phone is always the
     *  narrow end of that clamp. */
    val Gutter = 20.dp

    /** 44dp is the touch floor and there is no coarse/fine split to make on a
     *  handset -- everything here is a thumb. */
    val Hit = 44.dp
}

/** Self-hosted, converted from the same woff2 files the web app serves out of
 *  `web/public/fonts`. Bundled rather than downloadable: this app is built for
 *  a phone with no data connection, which is exactly when a downloadable font
 *  provider does not answer. */
val FiraSans = FontFamily(
    Font(R.font.fira_sans_regular, FontWeight.Normal),
    Font(R.font.fira_sans_medium, FontWeight.Medium),
    Font(R.font.fira_sans_semibold, FontWeight.SemiBold),
    Font(R.font.fira_sans_bold, FontWeight.Bold),
)

/** For anything the system generated: codec payloads, coordinates, trace ids,
 *  delivery codes. Same split as the console, where `--font-mono` marks "this
 *  string is the machine's, not a person's". */
val FiraCode = FontFamily(
    Font(R.font.fira_code_regular, FontWeight.Normal),
    Font(R.font.fira_code_medium, FontWeight.Medium),
)

private val PactShapes = Shapes(
    extraSmall = RoundedCornerShape(Pact.RadiusSm),
    small = RoundedCornerShape(Pact.Radius),
    medium = RoundedCornerShape(Pact.RadiusLg),
    large = RoundedCornerShape(Pact.RadiusLg),
    extraLarge = RoundedCornerShape(Pact.RadiusLg),
)

// 15px/1.6 body, headings at a tight tracking -- the console's `.lpTitle` uses
// -0.025em, which is -0.4sp at these sizes.
private val PactTypography = Typography(
    headlineLarge = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.Bold,
        fontSize = 30.sp, lineHeight = 34.sp, letterSpacing = (-0.7).sp,
    ),
    headlineMedium = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.Bold,
        fontSize = 25.sp, lineHeight = 30.sp, letterSpacing = (-0.5).sp,
    ),
    headlineSmall = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.SemiBold,
        fontSize = 21.sp, lineHeight = 27.sp, letterSpacing = (-0.3).sp,
    ),
    titleLarge = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.SemiBold,
        fontSize = 19.sp, lineHeight = 25.sp, letterSpacing = (-0.2).sp,
    ),
    titleMedium = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.SemiBold,
        fontSize = 16.sp, lineHeight = 22.sp,
    ),
    titleSmall = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.SemiBold,
        fontSize = 14.sp, lineHeight = 20.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.Normal,
        fontSize = 16.sp, lineHeight = 26.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.Normal,
        fontSize = 15.sp, lineHeight = 24.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.Normal,
        fontSize = 13.sp, lineHeight = 20.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.SemiBold,
        fontSize = 14.sp, lineHeight = 18.sp,
    ),
    labelMedium = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.Medium,
        fontSize = 12.sp, lineHeight = 16.sp,
    ),
    labelSmall = TextStyle(
        fontFamily = FiraSans, fontWeight = FontWeight.Medium,
        fontSize = 11.sp, lineHeight = 15.sp,
    ),
)

// Material's roles, filled with the console's tokens. `secondary` is --det
// throughout the screens (confirmations, "sent", "listening"), `tertiary` is
// --warn, and the container roles step up through --panel2/--panel3 the same
// way the console layers a card inside a card.
private val PactColors = darkColorScheme(
    primary = Pact.Llm,
    onPrimary = Pact.OnAccent,
    primaryContainer = Pact.Panel2,
    onPrimaryContainer = Pact.Llm,
    secondary = Pact.Det,
    onSecondary = Pact.OnAccent,
    secondaryContainer = Pact.Panel2,
    onSecondaryContainer = Pact.Det,
    tertiary = Pact.Warn,
    onTertiary = Pact.OnAccent,
    background = Pact.Bg,
    onBackground = Pact.Ink,
    surface = Pact.Panel,
    onSurface = Pact.Ink,
    surfaceVariant = Pact.Panel2,
    onSurfaceVariant = Pact.Dim,
    surfaceContainerLowest = Pact.Bg,
    surfaceContainerLow = Pact.Panel,
    surfaceContainer = Pact.Panel2,
    surfaceContainerHigh = Pact.Panel3,
    surfaceContainerHighest = Pact.Panel3,
    outline = Pact.Line,
    outlineVariant = Pact.Line,
    error = Pact.Bad,
    onError = Pact.OnAccent,
    errorContainer = Pact.Panel2,
    onErrorContainer = Pact.Bad,
    scrim = Color(0xCC050809),
)

/**
 * Dark only, deliberately, and for the same reason the console is: this is
 * used in field and low-light conditions, and a half-finished light theme
 * reads worse than a committed dark one. The previous build followed the
 * system setting, so the same demo looked like two different apps depending on
 * which handset it ran on.
 */
@Composable
fun PactTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = PactColors,
        typography = PactTypography,
        shapes = PactShapes,
        content = content,
    )
}
