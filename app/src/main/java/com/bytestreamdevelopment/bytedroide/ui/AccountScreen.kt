package com.bytestreamdevelopment.bytedroide.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.bytestreamdevelopment.bytedroide.data.Purchase
import com.bytestreamdevelopment.bytedroide.data.UserInfo

private enum class AccountDialog { None, Email, Password, Developer, Delete, Forgot }

@Composable
fun AccountScreen(state: UiState, vm: StoreViewModel, snackbar: SnackbarHostState) {
    var dialog by rememberSaveable { mutableStateOf(AccountDialog.None) }
    Scaffold(
        topBar = {
            BackTopBar("Konto", onBack = { vm.back() }) {
                IconButton(onClick = { vm.navigate(Screen.Settings) }) { Icon(Icons.Default.Settings, "Einstellungen") }
            }
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
                Profile(user, state, vm) { dialog = it }
            } else {
                LoginForm(state, vm) { dialog = AccountDialog.Forgot }
            }
        }
    }

    val close = { dialog = AccountDialog.None }
    when (dialog) {
        AccountDialog.None -> Unit
        AccountDialog.Forgot -> InputDialog(
            title = "Passwort vergessen",
            text = "Wir schicken dir einen Link zum Zurücksetzen an die E-Mail-Adresse deines Kontos.",
            label = "Benutzername oder E-Mail",
            confirm = "Link senden",
            onConfirm = vm::forgotPassword,
            onDismiss = close,
        )
        AccountDialog.Email -> InputDialog(
            title = "E-Mail-Adresse ändern",
            text = "Du bekommst eine Bestätigungs-E-Mail an die neue Adresse.",
            label = "Neue E-Mail-Adresse",
            initial = state.user?.email.orEmpty(),
            keyboardType = KeyboardType.Email,
            confirm = "Speichern",
            onConfirm = vm::changeEmail,
            onDismiss = close,
        )
        AccountDialog.Password -> PasswordDialog(vm, close)
        AccountDialog.Developer -> InputDialog(
            title = "Entwickler werden",
            text = "Als Entwickler kannst du eigene Apps veröffentlichen. Ein Admin muss das freigeben.",
            label = "Was möchtest du veröffentlichen? (optional)",
            singleLine = false,
            allowEmpty = true,
            confirm = "Anfrage senden",
            onConfirm = vm::requestDeveloper,
            onDismiss = close,
        )
        AccountDialog.Delete -> InputDialog(
            title = "Konto endgültig löschen?",
            text = "Dein Konto, Freischaltungen und Beta-Teilnahmen werden gelöscht. Gekaufte Apps sind danach nicht " +
                "mehr freigeschaltet. Eigene Apps werden versteckt und vom Admin übernommen. Zur Bestätigung dein Passwort:",
            label = "Passwort",
            password = true,
            confirm = "Endgültig löschen",
            onConfirm = vm::deleteAccount,
            onDismiss = close,
        )
    }
}

@Composable
private fun Profile(user: UserInfo, state: UiState, vm: StoreViewModel, open: (AccountDialog) -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text("Angemeldet als", style = MaterialTheme.typography.labelMedium)
            Text(user.username, style = MaterialTheme.typography.headlineSmall)
            Text(user.email, style = MaterialTheme.typography.bodyMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Badge(user.role.label, MaterialTheme.colorScheme.primary)
                if (user.devRequested) Badge("Entwickler-Anfrage läuft", MaterialTheme.colorScheme.tertiary)
            }
        }
    }
    if (!user.emailVerified) {
        Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("E-Mail-Adresse noch nicht bestätigt", style = MaterialTheme.typography.titleSmall)
                Text("Erst danach bekommst du Benachrichtigungen und kannst dein Passwort zurücksetzen.",
                    style = MaterialTheme.typography.bodySmall)
                Row {
                    TextButton(onClick = vm::resendVerification, enabled = !state.busy) { Text("Erneut senden") }
                    TextButton(onClick = { open(AccountDialog.Email) }) { Text("Adresse ändern") }
                }
            }
        }
    }

    Button(onClick = { vm.requestRedeem() }, modifier = Modifier.fillMaxWidth()) { Text("Freischalt-Code einlösen") }
    if (user.isDeveloper) {
        OutlinedButton(onClick = { vm.navigate(Screen.Dev) }, modifier = Modifier.fillMaxWidth()) { Text("Entwickler-Bereich") }
    } else if (!user.devRequested) {
        OutlinedButton(onClick = { open(AccountDialog.Developer) }, modifier = Modifier.fillMaxWidth()) {
            Text("Entwickler werden")
        }
    }
    if (user.isAdmin) {
        OutlinedButton(onClick = { vm.navigate(Screen.Admin) }, modifier = Modifier.fillMaxWidth()) { Text("Admin-Bereich") }
    }
    OutlinedButton(onClick = { vm.navigate(Screen.Purchases) }, modifier = Modifier.fillMaxWidth()) { Text("Meine Käufe") }

    HorizontalDivider()
    SectionTitle("Benachrichtigungen per E-Mail")
    SwitchRow("Updates meiner Apps", "Wenn eine App, die du geladen hast, eine neue Version bekommt", user.notifyUpdates) {
        vm.setNotifications(updates = it)
    }
    SwitchRow("Neuigkeiten", "Gelegentliche Ankündigungen rund um ByteDroide", user.notifyNews) {
        vm.setNotifications(news = it)
    }

    HorizontalDivider()
    SectionTitle("Konto")
    TextButton(onClick = { open(AccountDialog.Email) }) { Text("E-Mail-Adresse ändern") }
    TextButton(onClick = { open(AccountDialog.Password) }) { Text("Passwort ändern") }
    TextButton(onClick = vm::exportData) { Text("Meine Daten exportieren") }
    TextButton(onClick = vm::logout) { Text("Abmelden") }
    TextButton(onClick = { open(AccountDialog.Delete) }) {
        Text("Konto löschen", color = MaterialTheme.colorScheme.error)
    }
}

@Composable
private fun SwitchRow(title: String, subtitle: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.bodyLarge)
            Hint(subtitle)
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@Composable
private fun PasswordDialog(vm: StoreViewModel, onDismiss: () -> Unit) {
    var old by rememberSaveable { mutableStateOf("") }
    var new by rememberSaveable { mutableStateOf("") }
    androidx.compose.material3.AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Passwort ändern") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                PasswordField(old, { old = it }, "Aktuelles Passwort")
                PasswordField(new, { new = it }, "Neues Passwort (mind. 8 Zeichen)")
            }
        },
        confirmButton = {
            TextButton(enabled = old.isNotBlank() && new.length >= 8, onClick = {
                vm.changePassword(old, new)
                onDismiss()
            }) { Text("Ändern") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}

@Composable
private fun PasswordField(value: String, onChange: (String) -> Unit, label: String, isError: Boolean = false,
                          supporting: String? = null) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        label = { Text(label) },
        isError = isError,
        supportingText = supporting?.let { { Text(it) } },
        singleLine = true,
        visualTransformation = PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
        modifier = Modifier.fillMaxWidth(),
    )
}

@Composable
private fun LoginForm(state: UiState, vm: StoreViewModel, onForgot: () -> Unit) {
    var mode by rememberSaveable { mutableIntStateOf(0) } // 0 = Anmelden, 1 = Registrieren
    var username by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var password2 by rememberSaveable { mutableStateOf("") }
    var developer by rememberSaveable { mutableStateOf(false) }
    var devNote by rememberSaveable { mutableStateOf("") }
    var terms by rememberSaveable { mutableStateOf(false) }

    Text(
        "Ohne Konto siehst du alle offenen Apps. Für Apps mit Code, Käufe, Betas und Update-Mails brauchst du ein Konto.",
        style = MaterialTheme.typography.bodyMedium,
    )
    TabRow(selectedTabIndex = mode) {
        Tab(mode == 0, onClick = { mode = 0 }, text = { Text("Anmelden") })
        Tab(mode == 1, onClick = { mode = 1 }, text = { Text("Registrieren") })
    }
    OutlinedTextField(
        value = username,
        onValueChange = { username = it },
        label = { Text(if (mode == 0) "Benutzername oder E-Mail" else "Benutzername") },
        supportingText = if (mode == 1) ({ Text("3–32 Zeichen: Buchstaben, Zahlen, _ . -") }) else null,
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
    if (mode == 1) {
        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("E-Mail-Adresse") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email),
            modifier = Modifier.fillMaxWidth(),
        )
    }
    PasswordField(password, { password = it }, "Passwort", supporting = if (mode == 1) "Mindestens 8 Zeichen" else null)
    if (mode == 0) {
        TextButton(onClick = onForgot) { Text("Passwort vergessen?") }
    } else {
        PasswordField(password2, { password2 = it }, "Passwort wiederholen", isError = password2.isNotEmpty() && password2 != password)
        CheckRow(developer, { developer = it }) {
            Column {
                Text("Ich möchte Entwickler werden", style = MaterialTheme.typography.bodyLarge)
                Hint("Eigene Apps veröffentlichen – ein Admin gibt das frei.")
            }
        }
        if (developer) {
            OutlinedTextField(
                value = devNote,
                onValueChange = { devNote = it.take(500) },
                label = { Text("Was möchtest du veröffentlichen? (optional)") },
                minLines = 2,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        CheckRow(terms, { terms = it }) {
            Column {
                Text("Ich akzeptiere die Nutzungsbedingungen.", style = MaterialTheme.typography.bodyMedium)
                Row {
                    TextButton(onClick = { vm.openLegal("agb") }, contentPadding = PaddingValues(0.dp)) {
                        Text("Nutzungsbedingungen")
                    }
                    Text(" · ", modifier = Modifier.align(Alignment.CenterVertically))
                    TextButton(onClick = { vm.openLegal("datenschutz") }, contentPadding = PaddingValues(0.dp)) {
                        Text("Datenschutz")
                    }
                }
            }
        }
    }
    Button(
        onClick = {
            if (mode == 0) vm.login(username, password)
            else vm.register(username, email, password, developer, devNote)
        },
        enabled = !state.busy && username.isNotBlank() && password.isNotBlank() &&
            (mode == 0 || (password == password2 && email.contains('@') && terms)),
        modifier = Modifier.fillMaxWidth(),
    ) { Text(if (mode == 0) "Anmelden" else "Konto erstellen") }
}

@Composable
fun CheckRow(checked: Boolean, onChange: (Boolean) -> Unit, content: @Composable () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.clickable { onChange(!checked) }) {
        Checkbox(checked = checked, onCheckedChange = onChange)
        content()
    }
}

// ---------------------------------------------------------------------------
// Meine Käufe (mit Widerruf)
// ---------------------------------------------------------------------------

@Composable
fun PurchasesScreen(state: UiState, vm: StoreViewModel, snackbar: SnackbarHostState) {
    LaunchedEffect(Unit) { vm.loadPurchases() }
    var withdraw by rememberSaveable { mutableStateOf<Long?>(null) }
    Scaffold(
        topBar = { BackTopBar("Meine Käufe", onBack = { vm.back() }) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (state.purchases.isEmpty()) item { EmptyText("Noch keine Käufe.") }
            items(state.purchases, key = { it.id }) { p -> PurchaseCard(p) { withdraw = p.id } }
            item {
                Row {
                    TextButton(onClick = { vm.openLegal("widerruf") }) { Text("Widerrufsbelehrung") }
                    TextButton(onClick = { vm.openLegal("agb") }) { Text("Nutzungsbedingungen") }
                }
            }
        }
    }
    val purchase = state.purchases.firstOrNull { it.id == withdraw }
    if (purchase != null) {
        ConfirmDialog(
            title = "Widerruf bestätigen",
            text = "Hiermit widerrufe ich den Vertrag über den Kauf von „${purchase.appName}“ " +
                "(${purchase.price}, gekauft am ${formatEpoch(purchase.createdAt)}). " +
                "Du bekommst sofort eine Eingangsbestätigung per E-Mail.",
            confirm = "Widerruf bestätigen",
            onConfirm = { vm.withdraw(purchase) },
            onDismiss = { withdraw = null },
        )
    }
}

@Composable
private fun PurchaseCard(p: Purchase, onWithdraw: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(p.appName, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                Text(p.price, style = MaterialTheme.typography.titleMedium)
            }
            Hint("Beleg BD-%06d · %s".format(p.id, formatEpoch(p.createdAt)))
            Text(p.statusLabel, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
            if (p.canWithdraw) {
                OutlinedButton(onClick = onWithdraw) { Text("Vertrag widerrufen") }
            }
        }
    }
}

/** Kauf-Dialog mit Hinweis zum Widerrufsrecht (§ 356 Abs. 5 BGB). */
@Composable
fun BuyDialog(state: UiState, vm: StoreViewModel) {
    val app = state.buyFor?.let { state.entry(it)?.app } ?: return
    var consent by rememberSaveable { mutableStateOf(false) }
    androidx.compose.material3.AlertDialog(
        onDismissRequest = vm::dismissBuy,
        title = { Text("${app.name} kaufen") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Preis: ${app.price} (einmalig, inklusive aller Updates). Bezahlt wird sicher über Stripe.",
                    style = MaterialTheme.typography.bodyMedium)
                CheckRow(consent, { consent = it }) {
                    Text(
                        "Ich stimme ausdrücklich zu, dass vor Ablauf der Widerrufsfrist mit der Ausführung des " +
                            "Vertrags begonnen wird (sofortige Freischaltung). Mir ist bekannt, dass ich dadurch mein " +
                            "Widerrufsrecht verliere.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                Row {
                    TextButton(onClick = { vm.openLegal("widerruf") }, contentPadding = PaddingValues(0.dp)) {
                        Text("Widerrufsbelehrung")
                    }
                    Text(" · ", modifier = Modifier.align(Alignment.CenterVertically))
                    TextButton(onClick = { vm.openLegal("agb") }, contentPadding = PaddingValues(0.dp)) { Text("AGB") }
                }
            }
        },
        confirmButton = {
            Button(onClick = { vm.buy(app) }, enabled = consent && !state.busy) { Text("Zahlungspflichtig kaufen") }
        },
        dismissButton = { TextButton(onClick = vm::dismissBuy) { Text("Abbrechen") } },
    )
}
