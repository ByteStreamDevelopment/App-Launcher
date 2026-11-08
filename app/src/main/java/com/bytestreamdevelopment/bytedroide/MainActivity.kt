package com.bytestreamdevelopment.bytedroide

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
import androidx.compose.material3.LocalTextStyle
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
import com.bytestreamdevelopment.bytedroide.ui.AccountScreen
import com.bytestreamdevelopment.bytedroide.ui.AdminScreen
import com.bytestreamdevelopment.bytedroide.ui.AdminViewModel
import com.bytestreamdevelopment.bytedroide.ui.BuyDialog
import com.bytestreamdevelopment.bytedroide.ui.CodesScreen
import com.bytestreamdevelopment.bytedroide.ui.DetailScreen
import com.bytestreamdevelopment.bytedroide.ui.DevAppScreen
import com.bytestreamdevelopment.bytedroide.ui.DevCreateScreen
import com.bytestreamdevelopment.bytedroide.ui.DevScreen
import com.bytestreamdevelopment.bytedroide.ui.DevViewModel
import com.bytestreamdevelopment.bytedroide.ui.HomeScreen
import com.bytestreamdevelopment.bytedroide.ui.PurchasesScreen
import com.bytestreamdevelopment.bytedroide.ui.Screen
import com.bytestreamdevelopment.bytedroide.ui.SettingsScreen
import com.bytestreamdevelopment.bytedroide.ui.StoreTheme
import com.bytestreamdevelopment.bytedroide.ui.StoreViewModel
import com.bytestreamdevelopment.bytedroide.ui.Tab
import com.bytestreamdevelopment.bytedroide.ui.UiState

class MainActivity : ComponentActivity() {
    private val vm: StoreViewModel by viewModels()
    private val admin: AdminViewModel by viewModels()
    private val dev: DevViewModel by viewModels()

    private val notificationPermission =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        admin.onMessage = vm::toast
        admin.onCatalogChanged = vm::refresh
        dev.onMessage = vm::toast
        dev.onCatalogChanged = vm::refresh
        if (Build.VERSION.SDK_INT >= 33 && savedInstanceState == null) {
            notificationPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (savedInstanceState == null) handleIntent(intent)

        setContent {
            StoreTheme {
                val state by vm.state.collectAsStateWithLifecycle()
                val snackbar = remember { SnackbarHostState() }

                LifecycleEventEffect(Lifecycle.Event.ON_RESUME) { vm.onResume() }
                LaunchedEffect(state.message) {
                    state.message?.let {
                        vm.consumeMessage()
                        snackbar.showSnackbar(it)
                    }
                }
                BackHandler(enabled = state.stack.size > 1) { vm.back() }

                val user = state.user
                // Bereiche nur mit passender Rolle
                val screen = when (val s = state.screen) {
                    Screen.Admin -> if (user?.isAdmin == true) s else Screen.Home
                    Screen.Dev, Screen.DevCreate, is Screen.DevApp, is Screen.Codes ->
                        if (user?.isDeveloper == true) s else Screen.Home
                    Screen.Purchases -> if (user != null) s else Screen.Account
                    else -> s
                }
                when (screen) {
                    Screen.Home -> HomeScreen(state, vm, snackbar)
                    is Screen.Detail -> DetailScreen(
                        state.entry(screen.fullName),
                        state.tasks[state.entry(screen.fullName)?.app?.fullName ?: screen.fullName],
                        state,
                        vm,
                        snackbar,
                    )
                    Screen.Settings -> SettingsScreen(vm, snackbar)
                    Screen.Account -> AccountScreen(state, vm, snackbar)
                    Screen.Purchases -> PurchasesScreen(state, vm, snackbar)
                    Screen.Admin -> AdminScreen(user, admin, vm, snackbar)
                    Screen.Dev -> DevScreen(dev, vm, snackbar)
                    Screen.DevCreate -> DevCreateScreen(user, dev, vm, snackbar)
                    is Screen.DevApp -> DevAppScreen(screen.fullName, user, dev, vm, snackbar)
                    is Screen.Codes -> CodesScreen(screen.fullName, dev, vm, snackbar)
                }

                if (state.showRedeem) RedeemDialog(state, vm)
                if (state.buyFor != null) BuyDialog(state, vm)

                if (state.needsInstallPermission) {
                    AlertDialog(
                        onDismissRequest = vm::dismissPermissionDialog,
                        title = { Text("Berechtigung nötig") },
                        text = {
                            Text(
                                "Erlaube ByteDroide, unbekannte Apps zu installieren. " +
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
        if (intent == null) return
        if (intent.getBooleanExtra(EXTRA_OPEN_UPDATES, false)) {
            vm.selectTab(Tab.Updates)
            vm.refresh()
        }
        intent.data?.let(vm::openDeepLink)
    }

    companion object {
        const val EXTRA_OPEN_UPDATES = "open_updates"
    }
}

@Composable
private fun RedeemDialog(state: UiState, vm: StoreViewModel) {
    var code by rememberSaveable { mutableStateOf("") }
    val app = state.redeemFor?.let { state.entry(it)?.app }
    AlertDialog(
        onDismissRequest = vm::dismissRedeem,
        title = { Text(if (app?.isPaid == true) "Gutschein einlösen" else "Freischalt-Code einlösen") },
        text = {
            Column {
                Text(
                    when {
                        app == null -> "Gib den Code ein, den du bekommen hast."
                        app.isPaid -> "Du hast einen Gutschein-Code für „${app.name}“? Dann gib ihn hier ein."
                        else -> "„${app.name}“ ist nur mit Code verfügbar. Den Code bekommst du vom Entwickler."
                    },
                )
                OutlinedTextField(
                    value = code,
                    onValueChange = { v -> code = v.uppercase().take(12) },
                    placeholder = { Text("XXXX-XXXX") },
                    singleLine = true,
                    textStyle = LocalTextStyle.current.copy(fontFamily = FontFamily.Monospace),
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
