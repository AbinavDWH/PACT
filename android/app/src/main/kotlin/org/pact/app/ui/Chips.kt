package org.pact.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
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
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        values.forEach { (code, label) ->
            val isOn = code in selected
            FilterChip(
                selected = isOn,
                onClick = { onPick(code) },
                label = { Text(label) },
                colors = FilterChipDefaults.filterChipColors(),
                // Multi-select chips read as toggles, single-select as a
                // choice. Same control, and the border is the only cue that
                // separates them -- worth keeping consistent.
                border = FilterChipDefaults.filterChipBorder(
                    enabled = true, selected = isOn),
            )
        }
    }
}
