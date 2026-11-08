package com.bytestreamdevelopment.applauncher.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AccountScreen(state: UiState, vm: StoreViewModel, snackbar: SnackbarHostState) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Konto") },
                navigationIcon = {
                    IconButton(onClick = { vm.navigate(Screen.Home) }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Zurück")
                    }
                },
                actions = {
                    IconButton(onClick = { vm.navigate(Screen.Settings) }) { Icon(Icons.Default.Settings, "Einstellungen") }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            val user = state.user
            if (user != null) {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Angemeldet als", style = MaterialTheme.typography.labelMedium)
                        Text(user.username, style = MaterialTheme.typography.headlineSmall)
                        Text(
                            when {
                                user.isOwner -> "Haupt-Admin"
                                user.isAdmin -> "Admin"
                                else -> "Benutzer"
                            },
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
                Button(onClick = { vm.requestRedeem() }, modifier = Modifier.fillMaxWidth()) {
                    Text("Freischalt-Code einlösen")
                }
                if (user.isAdmin) {
                    OutlinedButton(onClick = { vm.navigate(Screen.Admin) }, modifier = Modifier.fillMaxWidth()) {
                        Text("Admin-Bereich")
                    }
                }
                HorizontalDivider()
                TextButton(onClick = vm::logout, modifier = Modifier.fillMaxWidth()) { Text("Abmelden") }
            } else {
                LoginForm(state, vm)
            }
        }
    }
}

@Composable
private fun LoginForm(state: UiState, vm: StoreViewModel) {
    var mode by rememberSaveable { mutableIntStateOf(0) } // 0 = Anmelden, 1 = Registrieren
    var username by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var password2 by rememberSaveable { mutableStateOf("") }
    var adminPassword by rememberSaveable { mutableStateOf("") }

    Text(
        "Ohne Konto siehst du alle offenen Apps. Für Apps mit Freischalt-Code brauchst du ein Konto.",
        style = MaterialTheme.typography.bodyMedium,
    )
    TabRow(selectedTabIndex = mode) {
        Tab(mode == 0, onClick = { mode = 0 }, text = { Text("Anmelden") })
        Tab(mode == 1, onClick = { mode = 1 }, text = { Text("Registrieren") })
    }
    OutlinedTextField(
        value = username,
        onValueChange = { username = it },
        label = { Text("Benutzername") },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    OutlinedTextField(
        value = password,
        onValueChange = { password = it },
        label = { Text("Passwort") },
        supportingText = if (mode == 1) ({ Text("Mindestens 8 Zeichen") }) else null,
        singleLine = true,
        visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
        modifier = Modifier.fillMaxWidth(),
    )
    if (mode == 1) {
        OutlinedTextField(
            value = password2,
            onValueChange = { password2 = it },
            label = { Text("Passwort wiederholen") },
            isError = password2.isNotEmpty() && password2 != password,
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            value = adminPassword,
            onValueChange = { adminPassword = it },
            label = { Text("Admin-Passwort (nur für das Admin-Konto)") },
            supportingText = { Text("Für normale Konten leer lassen.") },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )
    }
    Button(
        onClick = {
            if (mode == 0) vm.login(username, password) else vm.register(username, password, adminPassword)
        },
        enabled = !state.busy && username.isNotBlank() && password.isNotBlank() &&
            (mode == 0 || password == password2),
        modifier = Modifier.fillMaxWidth(),
    ) { Text(if (mode == 0) "Anmelden" else "Konto erstellen") }
}
