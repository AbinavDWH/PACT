package org.humanitarian.fieldapp.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val PactColorScheme = lightColorScheme(
    primary = PactPrimary,
    onPrimary = PactOnPrimary,
    background = PactBackground,
    onBackground = PactTextPrimary,
    surface = PactSurface,
    onSurface = PactTextPrimary,
    surfaceVariant = PactAccent,
    onSurfaceVariant = PactTextSecondary,
    outline = PactAccent,
    error = PactPrimary,
    onError = Color.White
)

@Composable
fun PactTheme(
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = PactColorScheme,
        content = content
    )
}