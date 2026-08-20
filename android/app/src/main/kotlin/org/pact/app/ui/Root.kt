package org.pact.app.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import org.pact.app.MainActivity

/**
 * Navigation, such as it is. A handful of screens and no back stack worth
 * managing, so a sealed class and a single `screen` variable beats adding a
 * navigation library -- see the dependency policy in app/build.gradle.kts.
 */
sealed interface Screen {
    data object Signup : Screen
    data object Request : Screen
    data object Sent : Screen
    data object Status : Screen
    data object Assignments : Screen
    data object Gateway : Screen
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

    // Where Back goes from the status screen. It is reachable from two places
    // -- straight after sending, and from the request screen -- and dropping
    // someone onto a blank request form because the destination was hard-coded
    // is the kind of small wrongness that reads as a broken app.
    var statusFrom by remember { mutableStateOf<Screen>(Screen.Request) }

    when (screen) {
        Screen.Signup -> SignupScreen(
            activity,
            onGateway = { screen = Screen.Gateway },
        ) {
            screen = if (session.role == "helper") Screen.Assignments else Screen.Request
        }

        Screen.Gateway -> GatewayScreen(activity) {
            screen = if (!session.signedIn) Screen.Signup
                     else if (session.role == "helper") Screen.Assignments
                     else Screen.Request
        }

        Screen.Request -> RequestScreen(
            activity,
            onStatus = { statusFrom = Screen.Request; screen = Screen.Status },
        ) { detail, trace ->
            lastDetail = detail
            lastTrace = trace
            screen = Screen.Sent
        }

        Screen.Sent -> SentScreen(
            activity = activity,
            detail = lastDetail,
            traceId = lastTrace,
            onAgain = { screen = Screen.Request },
            onStatus = { statusFrom = Screen.Sent; screen = Screen.Status },
        )

        Screen.Status -> StatusScreen(activity) { screen = statusFrom }

        Screen.Assignments -> AssignmentsScreen(activity) { screen = Screen.Signup }
    }
}
