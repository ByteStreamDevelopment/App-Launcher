package com.bytestreamdevelopment.applauncher.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
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
import androidx.compose.ui.unit.dp
import com.bytestreamdevelopment.applauncher.BuildConfig
import com.bytestreamdevelopment.applauncher.data.StoreSettings

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(vm: StoreViewModel, snackbar: SnackbarHostState) {
    val s = vm.settings
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
            Text(
                "ByteDroide ${BuildConfig.VERSION_NAME} · ${StoreSettings.SERVER_URL.removePrefix("https://")}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
