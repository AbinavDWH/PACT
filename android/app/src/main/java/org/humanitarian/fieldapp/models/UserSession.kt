package org.humanitarian.fieldapp.models

enum class UserRole {
    ADMIN,
    DONOR_GROUP,
    INDIVIDUAL
}

data class UserSession(
    val role: UserRole,
    val organizationId: String,
    val displayName: String
) {
    companion object {
        var current: UserSession? = null
    }
}