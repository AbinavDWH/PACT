package org.humanitarian.fieldapp.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AdminPanelSettings
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import org.humanitarian.fieldapp.models.UserRole
import org.humanitarian.fieldapp.models.UserSession
import org.humanitarian.fieldapp.ui.theme.PactAccent
import org.humanitarian.fieldapp.ui.theme.PactBackground
import org.humanitarian.fieldapp.ui.theme.PactOnPrimary
import org.humanitarian.fieldapp.ui.theme.PactPrimary
import org.humanitarian.fieldapp.ui.theme.PactSurface
import org.humanitarian.fieldapp.ui.theme.PactTextPrimary
import org.humanitarian.fieldapp.ui.theme.PactTextSecondary

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LoginScreen(onLoginSuccess: () -> Unit) {
    var selectedRole by remember { mutableStateOf<UserRole?>(null) }
    var orgId by remember { mutableStateOf("") }
    var displayName by remember { mutableStateOf("") }
    var showError by remember { mutableStateOf(false) }

    Scaffold(
        containerColor = PactBackground,
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        text = "Welcome to PACT",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.SemiBold,
                        color = PactTextPrimary
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = PactSurface,
                    titleContentColor = PactTextPrimary
                )
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
            Text(
                text = "Select your role to continue",
                style = MaterialTheme.typography.bodyLarge,
                color = PactTextSecondary
            )

            // Role Selection Cards
            RoleCard(
                title = "Administrator",
                description = "Coordinate resources and manage the network",
                icon = Icons.Filled.AdminPanelSettings,
                isSelected = selectedRole == UserRole.ADMIN,
                onClick = { selectedRole = UserRole.ADMIN }
            )

            RoleCard(
                title = "Donor Group",
                description = "Organization providing resources and aid",
                icon = Icons.Filled.Groups,
                isSelected = selectedRole == UserRole.DONOR_GROUP,
                onClick = { selectedRole = UserRole.DONOR_GROUP }
            )

            RoleCard(
                title = "Individual",
                description = "Field worker or person in need of assistance",
                icon = Icons.Filled.Person,
                isSelected = selectedRole == UserRole.INDIVIDUAL,
                onClick = { selectedRole = UserRole.INDIVIDUAL }
            )

            if (selectedRole != null) {
                Spacer(modifier = Modifier.height(8.dp))

                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(24.dp),
                    color = PactSurface,
                    border = BorderStroke(1.dp, PactAccent)
                ) {
                    Column(
                        modifier = Modifier.padding(20.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Text(
                            text = when (selectedRole) {
                                UserRole.ADMIN -> "Admin Setup"
                                UserRole.DONOR_GROUP -> "Donor Group Setup"
                                UserRole.INDIVIDUAL -> "Individual Setup"
                                else -> ""
                            },
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = PactTextPrimary
                        )

                        OutlinedTextField(
                            value = displayName,
                            onValueChange = { displayName = it },
                            label = { Text("Display Name") },
                            supportingText = {
                                Text(
                                    when (selectedRole) {
                                        UserRole.ADMIN -> "Your name as coordinator"
                                        UserRole.DONOR_GROUP -> "Organization or group name"
                                        UserRole.INDIVIDUAL -> "Your name"
                                        else -> ""
                                    }
                                )
                            },
                            singleLine = true,
                            shape = RoundedCornerShape(16.dp),
                            modifier = Modifier.fillMaxWidth()
                        )

                        OutlinedTextField(
                            value = orgId,
                            onValueChange = { orgId = it.uppercase() },
                            label = { Text("Organization ID") },
                            supportingText = {
                                Text(
                                    when (selectedRole) {
                                        UserRole.ADMIN -> "Admin coordinator ID (e.g., ADMIN01)"
                                        UserRole.DONOR_GROUP -> "Your organization ID (e.g., NGO01, CSR02)"
                                        UserRole.INDIVIDUAL -> "Your individual ID (e.g., WORKER01)"
                                        else -> ""
                                    }
                                )
                            },
                            singleLine = true,
                            shape = RoundedCornerShape(16.dp),
                            modifier = Modifier.fillMaxWidth()
                        )
                    }
                }

                if (showError) {
                    Text(
                        text = "Please fill in all fields",
                        color = PactPrimary,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium
                    )
                }

                Button(
                    onClick = {
                        if (orgId.isBlank() || displayName.isBlank()) {
                            showError = true
                        } else {
                            UserSession.current = UserSession(
                                role = selectedRole!!,
                                organizationId = orgId.trim().uppercase(),
                                displayName = displayName.trim()
                            )
                            onLoginSuccess()
                        }
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(56.dp),
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = PactPrimary,
                        contentColor = PactOnPrimary
                    )
                ) {
                    Text(
                        text = "Continue",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
        }
    }
}

@Composable
private fun RoleCard(
    title: String,
    description: String,
    icon: ImageVector,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isSelected) PactSurface else PactBackground
        ),
        border = BorderStroke(
            width = if (isSelected) 2.dp else 1.dp,
            color = if (isSelected) PactPrimary else PactAccent
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            Surface(
                modifier = Modifier.size(48.dp),
                shape = CircleShape,
                color = if (isSelected) PactPrimary else PactAccent
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = title,
                    modifier = Modifier.padding(12.dp),
                    tint = if (isSelected) PactOnPrimary else PactTextSecondary
                )
            }

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = PactTextPrimary
                )
                Text(
                    text = description,
                    style = MaterialTheme.typography.bodySmall,
                    color = PactTextSecondary
                )
            }
        }
    }
}