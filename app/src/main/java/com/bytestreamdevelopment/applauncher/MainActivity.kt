package com.bytestreamdevelopment.applauncher

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.viewModels
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bytestreamdevelopment.applauncher.ui.DetailScreen
import com.bytestreamdevelopment.applauncher.ui.HomeScreen
import com.bytestreamdevelopment.applauncher.ui.Screen
import com.bytestreamdevelopment.applauncher.ui.SettingsScreen
import com.bytestreamdevelopment.applauncher.ui.StoreTheme
import com.bytestreamdevelopment.applauncher.ui.StoreViewModel
import com.bytestreamdevelopment.applauncher.ui.Tab

class MainActivity : ComponentActivity() {
    private val vm: StoreViewModel by viewModels()

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        if (Build.VERSION.SDK_INT >= 33 && savedInstanceState == null) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        handleIntent(intent)

        setContent {
            StoreTheme {
                val state by vm.state.collectAsStateWithLifecycle()
                val snackbar = remember { SnackbarHostState() }

                LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { vm.refreshInstallStates() }
                LaunchedEffect(state.message) {
                    state.message?.let {
                        vm.consumeMessage()
                        snackbar.showSnackbar(it)
                    }
                }
                BackHandler(enabled = state.screen != Screen.Home) { vm.back() }

                when (val screen = state.screen) {
                    Screen.Home -> HomeScreen(state, vm, snackbar)
                    is Screen.Detail -> DetailScreen(
                        state.entry(screen.fullName),
                        state.tasks[screen.fullName],
                        vm,
                        snackbar,
                    )
                    Screen.Settings -> SettingsScreen(vm)
                }

                if (state.needsInstallPermission) {
                    AlertDialog(
                        onDismissRequest = vm::dismissPermissionDialog,
                        title = { Text("Berechtigung nötig") },
                        text = {
                            Text(
                                "Erlaube dem App Store, unbekannte Apps zu installieren. " +
                                    "Danach zurückkehren und erneut tippen.",
                            )
                        },
                        confirmButton = {
                            TextButton(onClick = vm::openInstallPermissionSettings) { Text("Einstellungen öffnen") }
                        },
                        dismissButton = {
                            TextButton(onClick = vm::dismissPermissionDialog) { Text("Abbrechen") }
                        },
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun handleIntent(intent: Intent?) {
        if (intent?.getBooleanExtra(EXTRA_OPEN_UPDATES, false) == true) {
            vm.selectTab(Tab.Updates)
            vm.refresh()
        }
    }

    companion object {
        const val EXTRA_OPEN_UPDATES = "open_updates"
    }
}
