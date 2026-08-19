package org.pact.app.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

// A high-contrast palette, chosen for the conditions this is used in rather
// than for looks: outdoors, one-handed, on a cracked screen, in a hurry.
private val Amber = Color(0xFFB45309)
private val AmberLight = Color(0xFFF59E0B)
private val Ink = Color(0xFF111827)
private val Paper = Color(0xFFF9FAFB)

private val LightColors = lightColorScheme(
    primary = Amber,
    onPrimary = Color.White,
    secondary = Color(0xFF0F766E),
    background = Paper,
    onBackground = Ink,
    surface = Color.White,
    onSurface = Ink,
    error = Color(0xFFB91C1C),
)

private val DarkColors = darkColorScheme(
    primary = AmberLight,
    onPrimary = Ink,
    secondary = Color(0xFF2DD4BF),
    background = Color(0xFF0B0F19),
    onBackground = Color(0xFFE5E7EB),
    surface = Color(0xFF151B28),
    onSurface = Color(0xFFE5E7EB),
    error = Color(0xFFF87171),
)

@Composable
fun PactTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content,
    )
}

@Composable
fun SectionLabel(text: String, hint: String? = null) {
    Row(
        modifier = Modifier.padding(top = 18.dp, bottom = 6.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            text.uppercase(),
            style = MaterialTheme.typography.labelLarge,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.primary,
        )
        if (hint != null) {
            Text(hint, style = MaterialTheme.typography.labelMedium,
                 color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.55f))
        }
    }
}
