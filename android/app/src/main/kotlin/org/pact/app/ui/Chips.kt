package org.pact.app.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

/**
 * The only input control in the request flow.
 *
 * `values` is (code, label): the code is what the codec encodes, the label is
 * what a person reads. Both come from the tables, so a chip can never offer a
 * choice the wire format cannot carry.
 *
 * Styling matches the console's `.chip`: a hairline outline when idle, the
 * --llm tint when chosen. The M3 default painted a filled tonal chip with a
 * tick, which on this screen -- twenty-odd chips, six groups -- read as a
 * screen of buttons rather than a set of answers.
 */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun ChipGrid(
    values: List<Pair<String, String>>,
    selected: Set<String>,
    multi: Boolean = false,
    onPick: (String) -> Unit,
) {
    FlowRow(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(Pact.Space2),
        verticalArrangement = Arrangement.spacedBy(Pact.Space2),
    ) {
        values.forEach { (code, label) ->
            val isOn = code in selected
            FilterChip(
                selected = isOn,
                onClick = { onPick(code) },
                modifier = Modifier.heightIn(min = 40.dp),
                shape = RoundedCornerShape(Pact.Radius),
                label = {
                    Text(
                        label,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                },
                colors = FilterChipDefaults.filterChipColors(
                    containerColor = Pact.Panel,
                    labelColor = Pact.Dim,
                    selectedContainerColor = Pact.LlmFill,
                    selectedLabelColor = Pact.Llm,
                ),
                // Multi-select chips read as toggles, single-select as a
                // choice. Same control, and the border weight is the only cue
                // that separates them -- worth keeping consistent.
                border = BorderStroke(
                    width = 1.dp,
                    color = if (isOn) Pact.Llm.copy(alpha = if (multi) 0.8f else 0.55f)
                            else Pact.Line,
                ),
            )
        }
    }
}
