package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.humanitarian.fieldapp.network.ApiClient
import org.humanitarian.fieldapp.network.ApiResult
import org.humanitarian.fieldapp.ui.theme.*

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SmsFallbackScreen(onBack: () -> Unit) {
    val context = LocalContext.current
    val clipboardManager = LocalClipboardManager.current
    val coroutineScope = rememberCoroutineScope()
    
    // FIX: Use a simple List<String> to avoid type inference errors.
    var queuedPayloads by remember { mutableStateOf<List<String>>(emptyList()) }
    var statusMessage by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        // TODO: REPLACE THIS with your actual OfflineQueue reading logic.
        // Example: If your OfflineQueue has a method like getPayloads(context):
        // queuedPayloads = OfflineQueue.getPayloads(context)
        // For now, it starts empty so the app compiles perfectly.
        queuedPayloads = emptyList() 
    }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = { Text("SMS Fallback Queue", fontWeight = FontWeight.SemiBold, color = PactTextPrimary) },
                navigationIcon = { TextButton(onClick = onBack) { Text("Back", color = PactPrimary) } },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = PactSurface)
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            if (queuedPayloads.isEmpty()) {
                Text("No pending SMS reports in queue.", color = PactTextSecondary)
            } else {
                // FIX: .size is a property, not a function
                Text("Pending Reports: ${queuedPayloads.size}", style = MaterialTheme.typography.titleMedium, color = PactTextPrimary)
                
                // FIX: Use a standard `for` loop instead of `forEachIndexed`.
                // Jetpack Compose DOES NOT allow @Composable functions (like Surface) 
                // inside standard Kotlin lambdas like `.forEachIndexed { }`.
                for ((index, payload) in queuedPayloads.withIndex()) {
                    Surface(
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(16.dp),
                        color = PactSurface,
                        border = BorderStroke(1.dp, PactAccent)
                    ) {
                        Column(modifier = Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                            Text("Report #${index + 1}", fontWeight = FontWeight.Bold, color = PactTextPrimary)
                            
                            Text(
                                text = payload,
                                fontFamily = FontFamily.Monospace,
                                color = PactPrimary,
                                modifier = Modifier.fillMaxWidth()
                            )

                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(
                                    onClick = { clipboardManager.setText(AnnotatedString(payload)) },
                                    colors = ButtonDefaults.buttonColors(containerColor = PactAccent, contentColor = PactTextPrimary)
                                ) { Text("Copy") }

                                Button(
                                    onClick = {
                                        coroutineScope.launch {
                                            statusMessage = "Sending to SMS Gateway..."
                                            when (val result = ApiClient.postSmsWebhook(payload)) {
                                                is ApiResult.Success -> {
                                                    statusMessage = "Success! SMS parsed by backend."
                                                }
                                                is ApiResult.Error -> {
                                                    statusMessage = "Failed: ${result.message}"
                                                }
                                            }
                                        }
                                    },
                                    colors = ButtonDefaults.buttonColors(containerColor = PactPrimary, contentColor = PactOnPrimary)
                                ) { Text("Simulate SMS Send") }
                            }
                        }
                    }
                }
            }
            
            if (statusMessage.isNotBlank()) {
                Text(statusMessage, color = PactPrimary, fontWeight = FontWeight.Bold)
            }
        }
    }
}