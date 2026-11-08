package com.bytestreamdevelopment.applauncher.ui

import android.content.Intent
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bytestreamdevelopment.applauncher.data.Access
import com.bytestreamdevelopment.applauncher.data.AccessCode
import com.bytestreamdevelopment.applauncher.data.AdminApp
import com.bytestreamdevelopment.applauncher.data.AdminUser
import com.bytestreamdevelopment.applauncher.data.UserInfo

// ---------------------------------------------------------------------------
// Übersicht: Apps & Benutzer
// ---------------------------------------------------------------------------

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminScreen(me: UserInfo?, admin: AdminViewModel, vm: StoreViewModel, snackbar: SnackbarHostState) {
    val state by admin.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { admin.load() }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Admin-Bereich") },
                navigationIcon = {
                    IconButton(onClick = { vm.navigate(Screen.Home) }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Zurück")
                    }
                },
                actions = {
                    IconButton(onClick = { admin.load(refreshCatalog = true) }) {
                        Icon(Icons.Default.Refresh, "Neu von Forgejo laden")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            TabRow(selectedTabIndex = state.tab.ordinal) {
                Tab(state.tab == AdminTab.Apps, onClick = { admin.selectTab(AdminTab.Apps) },
                    text = { Text("Apps (${state.apps.size})") })
                Tab(state.tab == AdminTab.Users, onClick = { admin.selectTab(AdminTab.Users) },
                    text = { Text("Benutzer (${state.users.size})") })
            }
            if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            when (state.tab) {
                AdminTab.Apps -> AdminAppList(state.apps, admin, vm)
                AdminTab.Users -> AdminUserList(state.users, me, admin)
            }
        }
    }
}

@Composable
private fun AdminAppList(apps: List<AdminApp>, admin: AdminViewModel, vm: StoreViewModel) {
    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        item {
            Text(
                "Lege für jede App fest, wer sie sehen und laden darf. Tippe auf eine App für Einmal-Codes.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (apps.isEmpty()) item { EmptyText("Keine Apps gefunden.") }
        items(apps, key = { it.fullName }) { app ->
            Card(
                Modifier
                    .fillMaxWidth()
                    .clickable {
                        admin.openCodes(app.fullName)
                        vm.navigate(Screen.AdminApp(app.fullName))
                    },
            ) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(app.name, style = MaterialTheme.typography.titleMedium)
                            Text(
                                "${app.owner} · ${version(app.version)}" + if (app.isPrivate) " · privat" else "",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    AccessSelector(app.access) { admin.setAccess(app, it) }
                    if (app.access == Access.Code || app.codesOpen + app.codesUsed > 0) {
                        Text(
                            "Codes: ${app.codesOpen} offen · ${app.codesUsed} eingelöst · ${app.unlockedUsers} freigeschaltet",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }
        }
    }
}

@Composable
fun AccessSelector(current: Access, onSelect: (Access) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Access.entries.forEach { access ->
            FilterChip(
                selected = current == access,
                onClick = { if (current != access) onSelect(access) },
                label = { Text(access.label) },
            )
        }
    }
}

@OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class)
@Composable
private fun AdminUserList(users: List<AdminUser>, me: UserInfo?, admin: AdminViewModel) {
    var toDelete by remember { mutableStateOf<AdminUser?>(null) }

    LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (users.isEmpty()) item { EmptyText("Noch keine Benutzer.") }
        items(users, key = { it.user.id }) { u ->
            val isMe = u.user.id == me?.id
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(
                                u.user.username + if (isMe) " (du)" else "",
                                style = MaterialTheme.typography.titleMedium,
                            )
                            Text(
                                when {
                                    u.user.isOwner -> "Haupt-Admin"
                                    u.user.isAdmin -> "Admin"
                                    else -> "Benutzer"
                                } + " · seit " + formatEpoch(u.createdAt).substringBefore(' '),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Text("Admin", style = MaterialTheme.typography.labelMedium)
                        Spacer(Modifier.width(6.dp))
                        Switch(
                            checked = u.user.isAdmin,
                            enabled = !u.user.isOwner,
                            onCheckedChange = { admin.setAdmin(u, it) },
                        )
                        IconButton(onClick = { toDelete = u }, enabled = !u.user.isOwner && !isMe) {
                            Icon(Icons.Default.Delete, "Benutzer löschen")
                        }
                    }
                    if (u.unlocked.isNotEmpty()) {
                        Text("Freigeschaltet:", style = MaterialTheme.typography.labelMedium)
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            u.unlocked.forEach { (fullName, name) ->
                                AssistChip(
                                    onClick = { admin.revokeUnlock(u, fullName, name) },
                                    label = { Text(name) },
                                    trailingIcon = { Icon(Icons.Default.Close, "Zugriff entziehen") },
                                )
                            }
                        }
                    }
                }
            }
        }
    }

    toDelete?.let { u ->
        AlertDialog(
            onDismissRequest = { toDelete = null },
            title = { Text("${u.user.username} löschen?") },
            text = { Text("Das Konto und alle Freischaltungen werden entfernt.") },
            confirmButton = {
                TextButton(onClick = {
                    admin.deleteUser(u)
                    toDelete = null
                }) { Text("Löschen") }
            },
            dismissButton = { TextButton(onClick = { toDelete = null }) { Text("Abbrechen") } },
        )
    }
}

// ---------------------------------------------------------------------------
// Einzelne App: Freigabe + Einmal-Codes
// ---------------------------------------------------------------------------

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminAppScreen(fullName: String, admin: AdminViewModel, vm: StoreViewModel, snackbar: SnackbarHostState) {
    val state by admin.state.collectAsStateWithLifecycle()
    val app = state.apps.firstOrNull { it.fullName == fullName }
    LaunchedEffect(fullName) { if (state.codesFor != fullName) admin.openCodes(fullName) }

    var note by rememberSaveable { mutableStateOf("") }
    var count by rememberSaveable { mutableStateOf("1") }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(app?.name ?: fullName) },
                navigationIcon = {
                    IconButton(onClick = { vm.navigate(Screen.Admin) }) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, "Zurück")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
              Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Freigabe", style = MaterialTheme.typography.titleMedium)
                if (app != null) AccessSelector(app.access) { admin.setAccess(app, it) }
                Text(
                    when (app?.access) {
                        Access.Open -> "Jeder kann die App sehen und installieren – auch ohne Konto."
                        Access.Code -> "Jeder sieht die App, installieren kann sie nur, wer einen Einmal-Code eingelöst hat."
                        Access.Hidden -> "Nur Admins sehen die App."
                        null -> ""
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (app != null && !app.isPrivate && app.access != Access.Open) {
                    Text(
                        "Hinweis: Das Repo ist auf Forgejo öffentlich – dort kann die APK jeder direkt laden. " +
                            "Für echten Schutz das Repo auf privat stellen.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
              }
            }
            item { HorizontalDivider() }
            item {
                Column {
                    Text("Einmal-Codes", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Jeder Code schaltet die App für genau ein Konto frei – dauerhaft, inklusive Updates.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(
                        value = note,
                        onValueChange = { note = it.take(100) },
                        label = { Text("Notiz (z. B. für wen)") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = count,
                        onValueChange = { v -> count = v.filter(Char::isDigit).take(2) },
                        label = { Text("Anzahl") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.width(90.dp),
                    )
                }
            }
            item {
                Button(
                    onClick = { admin.createCodes(fullName, (count.toIntOrNull() ?: 1).coerceIn(1, 50), note) },
                    enabled = !state.loading,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Code erzeugen") }
            }
            if (state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            if (state.codes.isEmpty() && !state.loading) item { EmptyText("Noch keine Codes für diese App.") }
            items(state.codes, key = { it.code }) { code ->
                CodeRow(code, fresh = code.code in state.freshCodes, appName = app?.name ?: fullName) {
                    admin.deleteCode(fullName, code.code)
                }
            }
        }
    }
}

@Composable
private fun CodeRow(code: AccessCode, fresh: Boolean, appName: String, onDelete: () -> Unit) {
    val context = LocalContext.current
    val clipboard = LocalClipboardManager.current
    val used = code.usedAt != null
    Card(
        colors = if (fresh) {
            CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
        } else {
            CardDefaults.cardColors()
        },
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(start = 12.dp, top = 8.dp, bottom = 8.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(
                Modifier
                    .weight(1f)
                    .clickable(enabled = !used) { clipboard.setText(AnnotatedString(code.code)) },
            ) {
                Text(
                    code.code,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium,
                    color = if (used) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                )
                if (code.note.isNotBlank()) Text(code.note, style = MaterialTheme.typography.bodySmall)
                Text(
                    if (used) {
                        "Eingelöst von ${code.usedBy ?: "gelöschtem Konto"} am ${formatEpoch(code.usedAt ?: 0)}"
                    } else {
                        "Frei · erstellt ${formatEpoch(code.createdAt)} · Tippen zum Kopieren"
                    },
                    style = MaterialTheme.typography.labelSmall,
                    color = if (used) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.primary,
                )
            }
            if (!used) {
                IconButton(onClick = {
                    val text = "Dein Freischalt-Code für $appName: ${code.code}\n" +
                        "In ByteDroide: Konto → „Freischalt-Code einlösen“."
                    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
                    context.startActivity(Intent.createChooser(send, "Code teilen"))
                }) { Icon(Icons.Default.Share, "Teilen") }
            }
            IconButton(onClick = onDelete) { Icon(Icons.Default.Delete, "Code löschen") }
        }
    }
}

@Composable
private fun EmptyText(text: String) {
    Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
        Text(text, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
