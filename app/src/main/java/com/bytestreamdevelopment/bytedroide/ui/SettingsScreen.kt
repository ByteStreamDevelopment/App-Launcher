package com.bytestreamdevelopment.bytedroide.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.bytestreamdevelopment.bytedroide.BuildConfig
import com.bytestreamdevelopment.bytedroide.data.StoreSettings

@Composable
fun SettingsScreen(vm: StoreViewModel, snackbar: SnackbarHostState) {
    val s = vm.settings
    var updateCheck by rememberSaveable { mutableStateOf(s.updateCheckEnabled) }

    Scaffold(
        topBar = {
            BackTopBar("Einstellungen", onBack = { vm.back() })
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
            Text("Updates", style = MaterialTheme.typography.titleMedium)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Automatisch nach Updates suchen", style = MaterialTheme.typography.bodyLarge)
                    Text(
                        "Alle 6 Stunden, mit Benachrichtigung",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Switch(checked = updateCheck, onCheckedChange = {
                    updateCheck = it
                    vm.setUpdateCheck(it)
                })
            }

            HorizontalDivider()
            Text("Berechtigungen", style = MaterialTheme.typography.titleMedium)
            Text(
                "Damit ByteDroide Apps installieren darf, muss „Unbekannte Apps installieren“ dafür erlaubt sein.",
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedButton(onClick = vm::openInstallPermissionSettings, modifier = Modifier.fillMaxWidth()) {
                Text("Installationsberechtigung öffnen")
            }

            HorizontalDivider()
            Text("Rechtliches", style = MaterialTheme.typography.titleMedium)
            Column {
                TextButton(onClick = { vm.openLegal("impressum") }) { Text("Impressum") }
                TextButton(onClick = { vm.openLegal("datenschutz") }) { Text("Datenschutzerklärung") }
                TextButton(onClick = { vm.openLegal("agb") }) { Text("Nutzungsbedingungen") }
                TextButton(onClick = { vm.openLegal("widerruf") }) { Text("Widerrufsbelehrung") }
            }

            HorizontalDivider()
            Text("Für Entwickler", style = MaterialTheme.typography.titleMedium)
            Text(
                "Eigene Apps veröffentlichen: Konto → „Entwickler werden“. Hochladen geht auch am PC im Entwickler-Portal.",
                style = MaterialTheme.typography.bodyMedium,
            )
            OutlinedButton(onClick = { vm.openLegal("portal") }, modifier = Modifier.fillMaxWidth()) {
                Text("Entwickler-Portal öffnen")
            }

            HorizontalDivider()
            Text(
                "ByteDroide ${BuildConfig.VERSION_NAME} · ${StoreSettings.SERVER_URL.removePrefix("https://")}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
