package com.bytestreamdevelopment.bytedroide.ui

import android.text.format.Formatter
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
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
import androidx.compose.material.icons.filled.Create
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
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
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.bytestreamdevelopment.bytedroide.data.AppEntry
import com.bytestreamdevelopment.bytedroide.data.BetaMode
import com.bytestreamdevelopment.bytedroide.data.InstallState

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DetailScreen(entry: AppEntry?, task: Task?, state: UiState, vm: StoreViewModel, snackbar: SnackbarHostState) {
    Scaffold(
        topBar = {
            BackTopBar(entry?.app?.name ?: "", onBack = { vm.back() }) {
                if (entry?.app?.canManage == true && state.user?.isDeveloper == true) {
                    IconButton(onClick = { vm.navigate(Screen.DevApp(entry.app.fullName)) }) {
                        Icon(Icons.Default.Create, "App verwalten")
                    }
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        if (entry == null) {
            Box(Modifier.padding(padding).fillMaxSize(), contentAlignment = Alignment.Center) {
                Text(if (state.loadedOnce) "App nicht (mehr) im Katalog" else "Lädt …")
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
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(app.name, style = MaterialTheme.typography.headlineSmall)
                    Text(app.owner, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
                    Text(statusText(entry, task), style = MaterialTheme.typography.labelMedium)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        AppBadges(app)
                        if (app.category.isNotBlank()) Badge(app.category, MaterialTheme.colorScheme.primary)
                    }
                }
            }

            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                ActionButton(entry, task, vm, Modifier.weight(1f))
                if (entry.state is InstallState.UpdateAvailable && task == null && app.unlocked) {
                    OutlinedButton(onClick = { vm.open(entry) }, modifier = Modifier.weight(1f)) { Text("Öffnen") }
                }
                if (entry.state !is InstallState.NotInstalled && task == null) {
                    OutlinedButton(onClick = { vm.uninstall(entry) }, modifier = Modifier.weight(1f)) {
                        Text("Deinstallieren")
                    }
                }
            }
            if (!app.unlocked && app.isPaid) {
                TextButton(onClick = { vm.requestRedeem(app.fullName) }) { Text("Ich habe einen Gutschein-Code") }
            }

            if (app.ratingCount > 0) {
                Text(
                    "${stars(app.ratingAverage)}  %.1f · %d Bewertung%s".format(
                        app.ratingAverage, app.ratingCount, if (app.ratingCount != 1) "en" else "",
                    ),
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            ScreenshotGallery(app.screenshots)

            if (app.description.isNotBlank()) {
                Text(app.description, style = MaterialTheme.typography.bodyLarge)
            }

            BetaCard(entry, state, vm)

            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    InfoRow(if (app.isBetaRelease) "Beta-Version" else "Neueste Version", version(app.release.tag))
                    InfoRow("Veröffentlicht", formatDate(app.release.publishedAt))
                    InfoRow("Größe", Formatter.formatShortFileSize(context, app.release.apk.size))
                    InfoRow("Entwickler", app.owner)
                    if (app.isPaid) InfoRow("Preis", app.price)
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

            ReviewsSection(app, state, vm)

            FlowRow {
                if (app.homepage.isNotBlank()) TextButton(onClick = { vm.openUrl(app.homepage) }) { Text("Webseite") }
                if (app.htmlUrl.isNotBlank() && app.htmlUrl != app.homepage) {
                    TextButton(onClick = { vm.openUrl(app.htmlUrl) }) { Text("Quellcode") }
                }
                if (app.release.htmlUrl.isNotBlank()) {
                    TextButton(onClick = { vm.openUrl(app.release.htmlUrl) }) { Text("Release im Browser") }
                }
            }
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun BetaCard(entry: AppEntry, state: UiState, vm: StoreViewModel) {
    val app = entry.app
    val beta = app.beta
    if (beta.mode == BetaMode.Off || (!beta.available && !beta.joined)) return
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("🧪 Beta-Programm", style = MaterialTheme.typography.titleMedium)
            if (beta.joined) {
                Text(
                    "Du bist Beta-Tester und bekommst Vorabversionen" +
                        (if (beta.version.isNotBlank()) " (aktuell ${version(beta.version)})" else "") +
                        ". Sie können Fehler enthalten.",
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedButton(onClick = { vm.setBeta(app, false) }, enabled = !state.busy) { Text("Beta verlassen") }
                Hint("Nach dem Verlassen bekommst du wieder die stabile Version, sobald sie neuer ist.")
            } else if (beta.mode == BetaMode.Open) {
                Text(
                    "Teste neue Funktionen vor allen anderen" +
                        (if (beta.version.isNotBlank()) " – aktuell Version ${version(beta.version)}" else "") + ".",
                    style = MaterialTheme.typography.bodyMedium,
                )
                OutlinedButton(onClick = { vm.setBeta(app, true) }, enabled = !state.busy) { Text("Beta-Tester werden") }
            } else {
                Text("Das Beta-Programm ist nur auf Einladung des Entwicklers.", style = MaterialTheme.typography.bodyMedium)
            }
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
