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
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bytestreamdevelopment.applauncher.ui.AccountScreen
import com.bytestreamdevelopment.applauncher.ui.AdminAppScreen
import com.bytestreamdevelopment.applauncher.ui.AdminScreen
import com.bytestreamdevelopment.applauncher.ui.AdminViewModel
import com.bytestreamdevelopment.applauncher.ui.DetailScreen
import com.bytestreamdevelopment.applauncher.ui.HomeScreen
import com.bytestreamdevelopment.applauncher.ui.Screen
import com.bytestreamdevelopment.applauncher.ui.SettingsScreen
import com.bytestreamdevelopment.applauncher.ui.StoreTheme
import com.bytestreamdevelopment.applauncher.ui.StoreViewModel
import com.bytestreamdevelopment.applauncher.ui.Tab
import com.bytestreamdevelopment.applauncher.ui.UiState

class MainActivity : ComponentActivity() {
    private val vm: StoreViewModel by viewModels()
    private val admin: AdminViewModel by viewModels()

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        admin.onMessage = vm::toast
        admin.onCatalogChanged = vm::refresh
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

                // Admin-Seiten nur für Admins
                val screen = state.screen.let {
                    if ((it is Screen.Admin || it is Screen.AdminApp) && state.user?.isAdmin != true) Screen.Home else it
                }
                when (screen) {
                    Screen.Home -> HomeScreen(state, vm, snackbar)
                    is Screen.Detail -> DetailScreen(
                        state.entry(screen.fullName),
                        state.tasks[screen.fullName],
                        vm,
                        snackbar,
                    )
                    Screen.Settings -> SettingsScreen(vm, snackbar)
                    Screen.Account -> AccountScreen(state, vm, snackbar)
                    Screen.Admin -> AdminScreen(state.user, admin, vm, snackbar)
                    is Screen.AdminApp -> AdminAppScreen(screen.fullName, admin, vm, snackbar)
                }

                if (state.showRedeem) RedeemDialog(state, vm)

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

@Composable
private fun RedeemDialog(state: UiState, vm: StoreViewModel) {
    var code by rememberSaveable { mutableStateOf("") }
    val appName = state.redeemFor?.let { state.entry(it)?.app?.name }
    AlertDialog(
        onDismissRequest = vm::dismissRedeem,
        title = { Text("Freischalt-Code einlösen") },
        text = {
            Column {
                Text(
                    if (appName != null) "„$appName“ ist nur mit Code verfügbar. Den Code bekommst du vom Admin."
                    else "Gib den Code ein, den du vom Admin bekommen hast.",
                )
                OutlinedTextField(
                    value = code,
                    onValueChange = { v -> code = v.uppercase().take(12) },
                    placeholder = { Text("XXXX-XXXX") },
                    singleLine = true,
                    textStyle = androidx.compose.material3.LocalTextStyle.current.copy(fontFamily = FontFamily.Monospace),
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { vm.redeem(code) }, enabled = code.isNotBlank() && !state.busy) { Text("Einlösen") }
        },
        dismissButton = { TextButton(onClick = vm::dismissRedeem) { Text("Abbrechen") } },
    )
}
