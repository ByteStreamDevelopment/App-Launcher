package com.bytestreamdevelopment.bytedroide.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Email
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bytestreamdevelopment.bytedroide.data.AdminOverview
import com.bytestreamdevelopment.bytedroide.data.AdminPurchase
import com.bytestreamdevelopment.bytedroide.data.AdminUser
import com.bytestreamdevelopment.bytedroide.data.DevApp
import com.bytestreamdevelopment.bytedroide.data.Role
import com.bytestreamdevelopment.bytedroide.data.UserInfo
import com.bytestreamdevelopment.bytedroide.data.formatCents

@Composable
fun AdminScreen(me: UserInfo?, admin: AdminViewModel, vm: StoreViewModel, snackbar: SnackbarHostState) {
    val state by admin.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { admin.load() }
    var announce by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            BackTopBar("Admin-Bereich", onBack = { vm.back() }) {
                IconButton(onClick = { announce = true }) { Icon(Icons.Default.Email, "Rundmail") }
                IconButton(onClick = { admin.load(refreshCatalog = true) }) { Icon(Icons.Default.Refresh, "Neu laden") }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            val requests = state.users.count { it.user.devRequested } + state.apps.count { it.review == "pending" } +
                state.pendingReleases.size
            ScrollableTabRow(selectedTabIndex = state.tab.ordinal, edgePadding = 8.dp) {
                AdminTab.entries.forEach { tab ->
                    Tab(state.tab == tab, onClick = { admin.selectTab(tab) }, text = {
                        Text(when (tab) {
                            AdminTab.Requests -> if (requests > 0) "Anfragen ($requests)" else tab.label
                            AdminTab.Apps -> "Apps (${state.apps.size})"
                            AdminTab.Users -> "Benutzer (${state.users.size})"
                            AdminTab.Purchases -> tab.label
                        })
                    })
                }
            }
            if (state.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            LazyColumn(contentPadding = PaddingValues(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                when (state.tab) {
                    AdminTab.Requests -> requests(state, admin, vm)
                    AdminTab.Apps -> apps(state.apps, vm)
                    AdminTab.Users -> users(state.users, me, admin)
                    AdminTab.Purchases -> purchases(state.purchases, admin)
                }
            }
        }
    }
    if (announce) AnnounceDialog(admin) { announce = false }
}

// --- Anfragen ----------------------------------------------------------------

private fun LazyListScope.requests(state: AdminState, admin: AdminViewModel, vm: StoreViewModel) {
    state.overview?.let { item { OverviewCard(it) } }
    val devRequests = state.users.filter { it.user.devRequested }
    val pendingApps = state.apps.filter { it.review == "pending" }
    item { SectionTitle("Entwickler-Anfragen (${devRequests.size})") }
    if (devRequests.isEmpty()) item { Hint("Keine offenen Anfragen.") }
    items(devRequests, key = { "u${it.user.id}" }) { u -> DevRequestCard(u, admin) }
    item { SectionTitle("Neue Versionen in Prüfung (${state.pendingReleases.size})") }
    if (state.pendingReleases.isEmpty()) {
        item {
            Hint(if (state.overview?.reviewReleases == true) "Nichts zu prüfen."
            else "Versionsprüfung ist aus (REVIEW_RELEASES=1 in der .env schaltet sie ein).")
        }
    }
    items(state.pendingReleases, key = { "r${it.app}/${it.channel}/${it.version}" }) { r -> PendingReleaseCard(r, admin) }
    item { SectionTitle("Apps in Prüfung (${pendingApps.size})") }
    if (pendingApps.isEmpty()) item { Hint("Nichts zu prüfen.") }
    items(pendingApps, key = { "a${it.fullName}" }) { app ->
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            DevAppCard(app) { vm.navigate(Screen.DevApp(app.fullName)) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { admin.review(app, true) }) { Text("Freigeben") }
                OutlinedButton(onClick = { vm.navigate(Screen.DevApp(app.fullName)) }) { Text("Ansehen") }
            }
        }
    }
}

@Composable
private fun OverviewCard(o: AdminOverview) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            StatRow(
                "${o.users}" to "Konten",
                "${o.developers}" to "Entwickler",
                "${o.apps}" to "Apps",
                "${o.downloads30d}" to "Downloads (30 T.)",
                formatCents(o.revenueCents) to "Umsatz",
            )
            if (!o.mailEnabled) Hint("⚠ E-Mail-Versand ist nicht eingerichtet (SMTP_* in der .env des Servers).",
                MaterialTheme.colorScheme.error)
            if (o.legalMissing.isNotEmpty()) Hint("⚠ Impressum unvollständig: ${o.legalMissing.joinToString()}",
                MaterialTheme.colorScheme.error)
            if (!o.paymentsEnabled) Hint("Bezahlung nicht eingerichtet – Kauf-Apps nur per Code (STRIPE_* in der .env).")
            if (o.scannerEnabled) Hint("✓ Virenscan aktiv (ClamAV)")
            if (o.withdrawalsOpen > 0) Hint("${o.withdrawalsOpen} Widerruf(e) offen – siehe Tab „Käufe“.",
                MaterialTheme.colorScheme.error)
        }
    }
}

@Composable
private fun PendingReleaseCard(r: com.bytestreamdevelopment.bytedroide.data.PendingRelease, admin: AdminViewModel) {
    var reject by remember { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("${r.name} ${version(r.version)}" + if (r.channel == "beta") " (Beta)" else "",
                style = MaterialTheme.typography.titleMedium)
            Hint(r.app + (r.developer?.let { " · von $it" } ?: ""))
            if (r.notes.isNotBlank()) Text(r.notes.take(400), style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { admin.decideRelease(r, true) }) { Text("Freigeben") }
                OutlinedButton(onClick = { reject = true }) { Text("Ablehnen") }
            }
        }
    }
    if (reject) {
        InputDialog(
            title = "Version ablehnen",
            text = "Der Entwickler bekommt die Begründung per E-Mail. Nutzer behalten die bisherige Version.",
            label = "Begründung",
            singleLine = false,
            allowEmpty = true,
            confirm = "Ablehnen",
            onConfirm = { admin.decideRelease(r, false, it) },
            onDismiss = { reject = false },
        )
    }
}

@Composable
private fun DevRequestCard(u: AdminUser, admin: AdminViewModel) {
    var reject by remember { mutableStateOf(false) }
    Card(Modifier.fillMaxWidth(), colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(u.user.username, style = MaterialTheme.typography.titleMedium)
            Hint(u.user.email + if (u.user.emailVerified) " ✓" else " (unbestätigt)")
            if (u.devNote.isNotBlank()) Text("„${u.devNote}“", style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { admin.decideDeveloper(u, true) }) { Text("Annehmen") }
                OutlinedButton(onClick = { reject = true }) { Text("Ablehnen") }
            }
        }
    }
    if (reject) {
        InputDialog(
            title = "Anfrage ablehnen",
            text = "${u.user.username} bekommt die Begründung per E-Mail.",
            label = "Begründung (optional)",
            allowEmpty = true,
            singleLine = false,
            confirm = "Ablehnen",
            onConfirm = { admin.decideDeveloper(u, false, it) },
            onDismiss = { reject = false },
        )
    }
}

// --- Apps --------------------------------------------------------------------

private fun LazyListScope.apps(apps: List<DevApp>, vm: StoreViewModel) {
    item { Hint("Tippe auf eine App, um Freigabe, Preis, Beta, Codes und Prüfung zu verwalten.") }
    if (apps.isEmpty()) item { EmptyText("Keine Apps.") }
    items(apps, key = { it.fullName }) { app -> DevAppCard(app) { vm.navigate(Screen.DevApp(app.fullName)) } }
}

// --- Benutzer ----------------------------------------------------------------

@OptIn(ExperimentalLayoutApi::class)
private fun LazyListScope.users(users: List<AdminUser>, me: UserInfo?, admin: AdminViewModel) {
    if (users.isEmpty()) item { EmptyText("Noch keine Benutzer.") }
    items(users, key = { it.user.id }) { u ->
        var confirmDelete by remember { mutableStateOf(false) }
        val isMe = u.user.id == me?.id
        Card(Modifier.fillMaxWidth()) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(u.user.username + if (isMe) " (du)" else "", style = MaterialTheme.typography.titleMedium)
                        Hint(u.user.email + (if (u.user.emailVerified) " ✓" else "") + " · seit " +
                            formatEpoch(u.createdAt).substringBefore(' ') + if (u.apps > 0) " · ${u.apps} Apps" else "")
                    }
                    IconButton(onClick = { confirmDelete = true }, enabled = !isMe) {
                        Icon(Icons.Default.Delete, "Benutzer löschen")
                    }
                }
                ChoiceChips(Role.entries, u.user.role, { it.label }) { admin.setRole(u, it) }
                if (u.user.devRequested) Hint("Möchte Entwickler werden", MaterialTheme.colorScheme.tertiary)
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
        if (confirmDelete) {
            ConfirmDialog(
                title = "${u.user.username} löschen?",
                text = "Das Konto und alle Freischaltungen werden entfernt. Eigene Apps werden versteckt und von den Admins verwaltet.",
                confirm = "Löschen",
                onConfirm = { admin.deleteUser(u) },
                onDismiss = { confirmDelete = false },
            )
        }
    }
}

// --- Käufe -------------------------------------------------------------------

private fun LazyListScope.purchases(purchases: List<AdminPurchase>, admin: AdminViewModel) {
    if (purchases.isEmpty()) item { EmptyText("Noch keine Käufe.") }
    items(purchases, key = { it.id }) { p ->
        var confirm by remember { mutableStateOf(false) }
        val withdrawn = p.status == "withdrawal_requested"
        Card(
            Modifier.fillMaxWidth(),
            colors = if (withdrawn) CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)
            else CardDefaults.cardColors(),
        ) {
            Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row {
                    Text(p.appName, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                    Text(p.price, style = MaterialTheme.typography.titleMedium)
                }
                Hint("BD-%06d · %s · %s · %s".format(p.id, p.username, p.email, formatEpoch(p.createdAt)))
                Text(
                    when (p.status) {
                        "paid" -> "Bezahlt"
                        "withdrawal_requested" -> "Widerruf eingegangen"
                        "refunded" -> "Erstattet"
                        else -> p.status
                    },
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
                if (p.status != "refunded") {
                    TextButton(onClick = { confirm = true }) { Text("Erstatten") }
                }
            }
        }
        if (confirm) {
            ConfirmDialog(
                title = "${p.price} erstatten?",
                text = "Der Betrag wird über Stripe an ${p.username} zurückgezahlt und die App für das Konto gesperrt.",
                confirm = "Erstatten",
                onConfirm = { admin.refund(p) },
                onDismiss = { confirm = false },
            )
        }
    }
}

@Composable
private fun AnnounceDialog(admin: AdminViewModel, onDismiss: () -> Unit) {
    var subject by rememberSaveable { mutableStateOf("") }
    var message by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Rundmail") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Hint("Geht an alle mit bestätigter E-Mail, die „Neuigkeiten“ eingeschaltet haben.")
                OutlinedTextField(subject, { subject = it.take(120) }, label = { Text("Betreff") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())
                OutlinedTextField(message, { message = it.take(5000) }, label = { Text("Nachricht") }, minLines = 5,
                    modifier = Modifier.fillMaxWidth())
            }
        },
        confirmButton = {
            TextButton(enabled = subject.isNotBlank() && message.isNotBlank(), onClick = {
                admin.announce(subject, message)
                onDismiss()
            }) { Text("Senden") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}
