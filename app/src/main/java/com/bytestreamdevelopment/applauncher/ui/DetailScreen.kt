package com.bytestreamdevelopment.applauncher.ui

import android.text.format.Formatter
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.bytestreamdevelopment.applauncher.data.AppEntry
import com.bytestreamdevelopment.applauncher.data.InstallState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DetailScreen(entry: AppEntry?, task: Task?, vm: StoreViewModel, snackbar: SnackbarHostState) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(entry?.app?.name ?: "") },
                navigationIcon = {
                    IconButton(onClick = { vm.navigate(Screen.Home) }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Zurück")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        if (entry == null) {
            Box(Modifier.padding(padding).fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("App nicht mehr im Katalog")
            }
            return@Scaffold
        }
        val app = entry.app
        val context = LocalContext.current
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                AppIcon(entry, 80.dp)
                Spacer(Modifier.width(16.dp))
                Column {
                    Text(app.name, style = MaterialTheme.typography.headlineSmall)
                    Text(app.owner, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                    Text(statusText(entry, task), style = MaterialTheme.typography.labelMedium)
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                ActionButton(entry, task, vm, Modifier.weight(1f))
                if (entry.state is InstallState.UpdateAvailable && task == null) {
                    OutlinedButton(onClick = { vm.open(entry) }, modifier = Modifier.weight(1f)) { Text("Öffnen") }
                }
                if (entry.state !is InstallState.NotInstalled && task == null) {
                    OutlinedButton(onClick = { vm.uninstall(entry) }, modifier = Modifier.weight(1f)) {
                        Text("Deinstallieren")
                    }
                }
            }

            if (app.description.isNotBlank()) {
                Text(app.description, style = MaterialTheme.typography.bodyLarge)
            }

            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    InfoRow("Neueste Version", version(app.release.tag))
                    InfoRow("Veröffentlicht", formatDate(app.release.publishedAt))
                    InfoRow("Größe", Formatter.formatShortFileSize(context, app.release.apk.size))
                    InfoRow("Datei", app.release.apk.name)
                    when (val s = entry.state) {
                        is InstallState.UpToDate -> InfoRow("Installiert", s.installedVersion)
                        is InstallState.UpdateAvailable -> InfoRow("Installiert", s.installedVersion)
                        InstallState.NotInstalled -> Unit
                    }
                    entry.packageName?.let { InfoRow("Paket", it) }
                }
            }

            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Neuigkeiten – ${app.release.name}", style = MaterialTheme.typography.titleMedium)
                HorizontalDivider()
                Text(
                    app.release.notes.ifBlank { "Keine Release-Notizen." },
                    style = MaterialTheme.typography.bodyMedium,
                )
            }

            Row {
                TextButton(onClick = { vm.openUrl(app.htmlUrl) }) { Text("Repository") }
                TextButton(onClick = { vm.openUrl(app.release.htmlUrl) }) { Text("Release im Browser") }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(Modifier.fillMaxWidth()) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(0.4f))
        Text(value, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(0.6f))
    }
}
