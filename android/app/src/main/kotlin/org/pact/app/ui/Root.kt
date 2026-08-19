package org.pact.app.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import org.pact.app.MainActivity

/**
 * Navigation, such as it is. Four screens and no back stack worth managing, so
 * a sealed class and a single `screen` variable beats adding a navigation
 * library -- see the dependency policy in app/build.gradle.kts.
 */
sealed interface Screen {
    data object Signup : Screen
    data object Request : Screen
    data object Sent : Screen
    data object Assignments : Screen
}

@Composable
fun RootScreen(activity: MainActivity) {
    val session = activity.session

    var screen by remember {
        mutableStateOf<Screen>(
            when {
                !session.signedIn -> Screen.Signup
                session.role == "helper" -> Screen.Assignments
                else -> Screen.Request
            }
        )
    }
    var lastTrace by remember { mutableStateOf<String?>(null) }
    var lastDetail by remember { mutableStateOf("") }

    when (screen) {
        Screen.Signup -> SignupScreen(activity) {
            screen = if (session.role == "helper") Screen.Assignments else Screen.Request
        }

        Screen.Request -> RequestScreen(activity) { detail, trace ->
            lastDetail = detail
            lastTrace = trace
            screen = Screen.Sent
        }

        Screen.Sent -> SentScreen(
            activity = activity,
            detail = lastDetail,
            traceId = lastTrace,
            onAgain = { screen = Screen.Request },
        )

        Screen.Assignments -> AssignmentsScreen(activity) { screen = Screen.Signup }
    }
}
