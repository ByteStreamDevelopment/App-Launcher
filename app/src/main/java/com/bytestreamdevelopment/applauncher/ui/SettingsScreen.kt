package com.bytestreamdevelopment.applauncher.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.bytestreamdevelopment.applauncher.BuildConfig
import com.bytestreamdevelopment.applauncher.data.StoreSettings

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(vm: StoreViewModel) {
    val s = vm.settings
    var server by rememberSaveable { mutableStateOf(s.serverUrl) }
    var token by rememberSaveable { mutableStateOf(s.token) }
    var owners by rememberSaveable { mutableStateOf(s.ownerFilter) }
    var updateCheck by rememberSaveable { mutableStateOf(s.updateCheckEnabled) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Einstellungen") },
                navigationIcon = {
                    IconButton(onClick = { vm.navigate(Screen.Home) }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Zurück")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Quelle", style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(
                value = server,
                onValueChange = { server = it },
                label = { Text("Forgejo-Server") },
                placeholder = { Text(StoreSettings.DEFAULT_SERVER) },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = owners,
                onValueChange = { owners = it },
                label = { Text("Nur diese Benutzer/Organisationen") },
                placeholder = { Text("z. B. Manhunt, Mrcoolgamer11") },
                supportingText = { Text("Kommagetrennt. Leer = alle Repos auf dem Server.") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = token,
                onValueChange = { token = it },
                label = { Text("Zugangstoken (optional)") },
                supportingText = { Text("Nur für private Repos nötig. Forgejo → Einstellungen → Anwendungen, Recht „read:repository“.") },
                singleLine = true,
                visualTransformation = PasswordVisualTransformation(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                modifier = Modifier.fillMaxWidth(),
            )

            HorizontalDivider()
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Automatisch nach Updates suchen", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "Alle 6 Stunden, mit Benachrichtigung",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(checked = updateCheck, onCheckedChange = { updateCheck = it })
            }

            Button(
                onClick = { vm.saveSettings(server, token, owners, updateCheck) },
                modifier = Modifier.fillMaxWidth(),
            ) { Text("Speichern") }

            HorizontalDivider()
            Text("Berechtigungen", style = MaterialTheme.typography.titleMedium)
            Text(
                "Damit der Store Apps installieren darf, muss „Unbekannte Apps installieren“ für ihn erlaubt sein.",
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedButton(onClick = vm::openInstallPermissionSettings, modifier = Modifier.fillMaxWidth()) {
                Text("Installationsberechtigung öffnen")
            }

            HorizontalDivider()
            Text(
                "App Store ${BuildConfig.VERSION_NAME}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
