package org.pact.app

import android.Manifest
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.pact.app.ui.PactTheme
import org.pact.app.ui.RootScreen

class MainActivity : ComponentActivity() {

    lateinit var session: Session
    lateinit var api: Api
    lateinit var outbox: Outbox
    lateinit var transport: Transport
    lateinit var loc: Loc

    /** Set once the permission dialog has been answered, so the UI can stop
     *  claiming GPS is unavailable while the prompt is still open. */
    var permissionsAnswered by mutableStateOf(false)
        private set

    private val permissionLauncher = registerForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissionsAnswered = true }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Loads shared/codec/pact_tables.v1.json out of assets. Everything the
        // UI offers as a choice comes from that file.
        Options.load(this)

        session = Session(this)
        api = Api(BuildConfig.API_BASE, session)
        outbox = Outbox(this)
        transport = Transport(this, api, outbox)
        loc = Loc(this)

        setContent {
            PactTheme {
                RootScreen(this)
            }
        }

        requestPermissions()
    }

    private fun requestPermissions() {
        val wanted = listOf(
            Manifest.permission.ACCESS_FINE_LOCATION,
            Manifest.permission.ACCESS_COARSE_LOCATION,
            Manifest.permission.SEND_SMS,
        )
        // Ask up front rather than at the moment of sending. Someone reporting
        // a collapsed building should not meet a permission dialog between
        // pressing Send and the message leaving.
        permissionLauncher.launch(wanted.toTypedArray())
    }
}
