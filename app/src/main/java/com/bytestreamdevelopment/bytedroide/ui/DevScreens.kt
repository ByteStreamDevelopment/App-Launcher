package com.bytestreamdevelopment.bytedroide.ui

import android.content.Intent
import android.text.format.Formatter
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExtendedFloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.bytestreamdevelopment.bytedroide.data.Access
import com.bytestreamdevelopment.bytedroide.data.AccessCode
import com.bytestreamdevelopment.bytedroide.data.BetaMode
import com.bytestreamdevelopment.bytedroide.data.DevApp
import com.bytestreamdevelopment.bytedroide.data.StoreSettings
import com.bytestreamdevelopment.bytedroide.data.UserInfo
import com.bytestreamdevelopment.bytedroide.data.formatCents
import org.json.JSONObject

val ROLLOUT_STEPS = listOf(10, 25, 50, 100)

// ---------------------------------------------------------------------------
// Übersicht: meine Apps
// ---------------------------------------------------------------------------

@Composable
fun DevScreen(dev: DevViewModel, vm: StoreViewModel, snackbar: SnackbarHostState) {
    val state by dev.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { dev.loadApps() }
    Scaffold(
        topBar = {
            BackTopBar("Entwickler-Bereich", onBack = { vm.back() }) {
                IconButton(onClick = { dev.loadApps() }) { Icon(Icons.Default.Refresh, "Aktualisieren") }
            }
        },
        floatingActionButton = {
            ExtendedFloatingActionButton(
                onClick = { vm.navigate(Screen.DevCreate) },
                icon = { Icon(Icons.Default.Add, null) },
                text = { Text("Neue App") },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(start = 12.dp, end = 12.dp, top = 12.dp, bottom = 96.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            item {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("Tipp: Entwickler-Portal", style = MaterialTheme.typography.titleSmall)
                        Text(
                            "Am PC hochladen oder per CI automatisch veröffentlichen: " +
                                StoreSettings.SERVER_URL.removePrefix("https://") + "/portal",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        TextButton(onClick = { vm.openUrl("${StoreSettings.SERVER_URL}/portal") },
                            contentPadding = PaddingValues(0.dp)) { Text("Portal öffnen") }
                    }
                }
            }
            if (state.apps.isEmpty() && !state.loading) item { EmptyText("Noch keine eigenen Apps. Lege deine erste an!") }
            items(state.apps, key = { it.fullName }) { app ->
                DevAppCard(app) { vm.navigate(Screen.DevApp(app.fullName)) }
            }
        }
    }
}

@Composable
fun DevAppCard(app: DevApp, onClick: () -> Unit) {
    Card(Modifier.fillMaxWidth().clickable(onClick = onClick)) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            LetterIcon(app.name, app.fullName, app.avatarUrl, 48.dp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(app.name, style = MaterialTheme.typography.titleMedium)
                Hint(app.fullName + (app.developer?.let { " · $it" } ?: ""))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    ReviewBadge(app.review)
                    if (app.priceCents > 0) Badge(formatCents(app.priceCents.toLong()), MaterialTheme.colorScheme.primary)
                    if (app.access != Access.Open) Badge(app.access.label, MaterialTheme.colorScheme.tertiary)
                    if (app.beta != BetaMode.Off) Badge("Beta", MaterialTheme.colorScheme.secondary)
                }
                Hint("Version ${app.stable?.let(::version) ?: "–"}" +
                    (app.betaVersion?.let { " · Beta ${version(it)}" } ?: "") + " · ${app.downloads} Downloads")
            }
        }
    }
}

@Composable
fun ReviewBadge(review: String) = when (review) {
    "approved" -> Badge("Veröffentlicht", MaterialTheme.colorScheme.primary)
    "rejected" -> Badge("Abgelehnt", MaterialTheme.colorScheme.error)
    else -> Badge("In Prüfung", MaterialTheme.colorScheme.tertiary)
}

// ---------------------------------------------------------------------------
// Neue App
// ---------------------------------------------------------------------------

private fun slugify(name: String) = name.lowercase()
    .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    .replace(Regex("[^a-z0-9]+"), "-").trim('-').take(40)

@Composable
fun DevCreateScreen(me: UserInfo?, dev: DevViewModel, vm: StoreViewModel, snackbar: SnackbarHostState) {
    val state by dev.state.collectAsStateWithLifecycle()
    var name by rememberSaveable { mutableStateOf("") }
    var slug by rememberSaveable { mutableStateOf("") }
    var slugTouched by rememberSaveable { mutableStateOf(false) }
    var description by rememberSaveable { mutableStateOf("") }
    var category by rememberSaveable { mutableStateOf("") }
    var fromRepo by rememberSaveable { mutableStateOf(false) }
    var repoUrl by rememberSaveable { mutableStateOf("") }
    var repoToken by rememberSaveable { mutableStateOf("") }
    var price by rememberSaveable { mutableStateOf("0") }

    Scaffold(
        topBar = { BackTopBar("Neue App", onBack = { vm.back() }) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                OutlinedTextField(name, {
                    name = it.take(60)
                    if (!slugTouched) slug = slugify(it)
                }, label = { Text("Name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            }
            item {
                OutlinedTextField(slug, {
                    slug = it.lowercase().take(40)
                    slugTouched = true
                }, label = { Text("Kurzname") }, singleLine = true,
                    supportingText = { Text("Adresse im Store: ${me?.username ?: "du"}/$slug") },
                    modifier = Modifier.fillMaxWidth())
            }
            item {
                OutlinedTextField(description, { description = it.take(4000) }, label = { Text("Beschreibung") },
                    minLines = 3, modifier = Modifier.fillMaxWidth())
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(category, { category = it.take(40) }, label = { Text("Kategorie") },
                        singleLine = true, modifier = Modifier.weight(1f))
                    OutlinedTextField(price, { price = it.filter { c -> c.isDigit() || c == ',' || c == '.' }.take(7) },
                        label = { Text("Preis €") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.weight(0.6f))
                }
            }
            item {
                SectionTitle("Woher kommen die Versionen?")
                ChoiceChips(listOf(false, true), fromRepo, { if (it) "Repository" else "APK hochladen" }) { fromRepo = it }
            }
            if (fromRepo) {
                item {
                    OutlinedTextField(repoUrl, { repoUrl = it.trim() }, label = { Text("Repository-Adresse") },
                        placeholder = { Text("https://github.com/name/app") }, singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri), modifier = Modifier.fillMaxWidth())
                }
                item {
                    OutlinedTextField(repoToken, { repoToken = it.trim() }, label = { Text("Token (nur private Repos)") },
                        singleLine = true, modifier = Modifier.fillMaxWidth())
                    Hint("GitHub, Forgejo, Gitea und Codeberg. Es zählt das neueste Release mit .apk-Datei, " +
                        "Pre-Releases werden zur Beta.")
                }
            }
            item { Hint("Neue Apps werden vor der Veröffentlichung von einem Admin geprüft.") }
            if (state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            item {
                Button(
                    enabled = name.isNotBlank() && slug.length >= 2 && (!fromRepo || repoUrl.isNotBlank()) && !state.loading,
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        val fields = JSONObject()
                            .put("name", name.trim()).put("slug", slug).put("description", description.trim())
                            .put("category", category.trim()).put("price_cents", parsePrice(price))
                        if (fromRepo) fields.put("source_url", repoUrl).put("source_token", repoToken)
                        dev.create(fields) { id ->
                            vm.back()
                            vm.navigate(Screen.DevApp(id))
                        }
                    },
                ) { Text("App anlegen") }
            }
        }
    }
}

private fun parsePrice(text: String): Int =
    ((text.replace(',', '.').toDoubleOrNull() ?: 0.0) * 100).toInt()

private fun priceText(cents: Int) = if (cents == 0) "0" else "%d,%02d".format(cents / 100, cents % 100)

// ---------------------------------------------------------------------------
// App verwalten
// ---------------------------------------------------------------------------

@Composable
fun DevAppScreen(fullName: String, me: UserInfo?, dev: DevViewModel, vm: StoreViewModel, snackbar: SnackbarHostState) {
    val state by dev.state.collectAsStateWithLifecycle()
    LaunchedEffect(fullName) { dev.open(fullName) }
    val app = state.current?.takeIf { it.fullName == fullName }
    var confirmDelete by remember { mutableStateOf(false) }
    var rejectDialog by remember { mutableStateOf(false) }
    var testerDialog by remember { mutableStateOf(false) }
    var rolloutFor by remember { mutableStateOf<com.bytestreamdevelopment.bytedroide.data.DevRelease?>(null) }
    val shotPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) dev.addScreenshot(fullName, uri)
    }

    Scaffold(
        topBar = {
            BackTopBar(app?.name ?: fullName, onBack = { vm.back() }) {
                IconButton(onClick = { dev.open(fullName) }) { Icon(Icons.Default.Refresh, "Aktualisieren") }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            if (app == null) return@LazyColumn

            item { Header(app) }
            if (me?.isAdmin == true && app.review != "approved") {
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.tertiaryContainer)) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text("Prüfung (Admin)", style = MaterialTheme.typography.titleSmall)
                            Hint("Erst nach der Freigabe sehen Benutzer die App. Der Entwickler bekommt eine E-Mail.")
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(onClick = { dev.review(fullName, "approved") }) { Text("Freigeben") }
                                if (app.review != "rejected") {
                                    OutlinedButton(onClick = { rejectDialog = true }) { Text("Ablehnen") }
                                }
                            }
                        }
                    }
                }
            } else if (me?.isAdmin == true) {
                item {
                    TextButton(onClick = { rejectDialog = true }) { Text("Veröffentlichung zurückziehen (Admin)") }
                }
            }

            if (app.isUpload) {
                item { UploadCard(app, state, dev) }
                if (state.releases.isNotEmpty()) {
                    item { SectionTitle("Versionen") }
                    items(state.releases, key = { it.id }) { r ->
                        val context = LocalContext.current
                        Card(Modifier.fillMaxWidth()) {
                            Row(Modifier.padding(start = 12.dp, top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f).clickable(enabled = r.channel == "stable" && r.status == "approved") {
                                    rolloutFor = r
                                }) {
                                    Text(version(r.version) + if (r.channel == "beta") " (Beta)" else "",
                                        style = MaterialTheme.typography.titleSmall)
                                    Hint("Code ${r.versionCode ?: "?"} · ${Formatter.formatShortFileSize(context, r.size)} · " +
                                        formatEpoch(r.createdAt))
                                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                        when (r.status) {
                                            "pending" -> Badge("Wartet auf Prüfung", MaterialTheme.colorScheme.tertiary)
                                            "rejected" -> Badge("Abgelehnt", MaterialTheme.colorScheme.error)
                                        }
                                        if (r.channel == "stable" && r.status == "approved" && r.rollout < 100) {
                                            Badge("Rollout ${r.rollout} % · tippen zum Ändern", MaterialTheme.colorScheme.primary)
                                        }
                                        if (r.scan == "clean") Badge("Virenscan ✓", MaterialTheme.colorScheme.secondary)
                                    }
                                    if (r.status == "rejected" && r.reviewNote.isNotBlank()) {
                                        Hint("Begründung: ${r.reviewNote}", MaterialTheme.colorScheme.error)
                                    }
                                }
                                IconButton(onClick = { dev.deleteRelease(fullName, r) }) {
                                    Icon(Icons.Default.Delete, "Version löschen")
                                }
                            }
                        }
                    }
                }
            } else {
                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text("Quelle", style = MaterialTheme.typography.titleSmall)
                            Text(app.sourceUrl, style = MaterialTheme.typography.bodySmall)
                            Hint("Neue Versionen: dort ein Release mit .apk anlegen. Pre-Releases werden zur Beta.")
                            app.sourceError?.let { Hint("Fehler: $it", MaterialTheme.colorScheme.error) }
                            if (app.pendingVersions.isNotEmpty()) {
                                Hint("Wartet auf Admin-Prüfung: ${app.pendingVersions.joinToString()}",
                                    MaterialTheme.colorScheme.tertiary)
                            }
                            if (app.blockedVersions.isNotEmpty()) {
                                Hint("Gesperrt (abgelehnt oder Virenfund): ${app.blockedVersions.joinToString()}",
                                    MaterialTheme.colorScheme.error)
                            }
                        }
                    }
                }
            }

            item { HorizontalDivider() }
            item {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        SectionTitle("Screenshots (${app.screenshots.size}/8)")
                        Spacer(Modifier.weight(1f))
                        TextButton(onClick = { shotPicker.launch("image/*") }, enabled = app.screenshots.size < 8) {
                            Text("Hinzufügen")
                        }
                    }
                    if (app.screenshots.isEmpty()) Hint("Screenshots erscheinen auf der App-Seite in ByteDroide und im Web-Store.")
                    androidx.compose.foundation.lazy.LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(app.screenshots, key = { it.id }) { shot ->
                            Box {
                                coil.compose.AsyncImage(
                                    model = shot.url,
                                    contentDescription = null,
                                    modifier = Modifier.height(160.dp).clip(RoundedCornerShape(10.dp)),
                                )
                                IconButton(
                                    onClick = { dev.deleteScreenshot(fullName, shot.id) },
                                    modifier = Modifier.align(Alignment.TopEnd),
                                ) { Icon(Icons.Default.Delete, "Screenshot löschen") }
                            }
                        }
                    }
                }
            }
            item { HorizontalDivider() }
            item { SettingsCard(app, dev) }

            item { HorizontalDivider() }
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        SectionTitle("Freischalt-Codes")
                        Hint("${app.codesOpen} offen · ${app.codesUsed} eingelöst – auch als Gutschein für Kauf-Apps")
                    }
                    OutlinedButton(onClick = { vm.navigate(Screen.Codes(fullName)) }) { Text("Verwalten") }
                }
            }

            if (app.beta != BetaMode.Off) {
                item { HorizontalDivider() }
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        SectionTitle("Beta-Tester (${state.testers.size})")
                        Spacer(Modifier.weight(1f))
                        TextButton(onClick = { testerDialog = true }) { Text("Einladen") }
                    }
                }
                if (state.testers.isEmpty()) item { Hint("Noch keine Tester.") }
                items(state.testers, key = { "t${it.id}" }) { t ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(t.username, modifier = Modifier.weight(1f))
                        Hint("seit ${formatEpoch(t.joinedAt).substringBefore(' ')}")
                        IconButton(onClick = { dev.removeTester(fullName, t) }) { Icon(Icons.Default.Delete, "Entfernen") }
                    }
                }
            }

            item { HorizontalDivider() }
            item {
                TextButton(onClick = { confirmDelete = true }) {
                    Text("App löschen", color = MaterialTheme.colorScheme.error)
                }
            }
        }
    }

    if (confirmDelete && app != null) {
        ConfirmDialog(
            title = "„${app.name}“ löschen?",
            text = "Alle hochgeladenen Versionen, Codes, Freischaltungen und Beta-Tester werden entfernt.",
            confirm = "Löschen",
            onConfirm = { dev.delete(fullName) { vm.back() } },
            onDismiss = { confirmDelete = false },
        )
    }
    if (rejectDialog) {
        InputDialog(
            title = "App ablehnen",
            text = "Der Entwickler bekommt die Begründung per E-Mail.",
            label = "Begründung",
            singleLine = false,
            confirm = "Ablehnen",
            onConfirm = { dev.review(fullName, "rejected", it) },
            onDismiss = { rejectDialog = false },
        )
    }
    rolloutFor?.let { r ->
        var value by remember { mutableStateOf(r.rollout) }
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { rolloutFor = null },
            title = { Text("Rollout von ${version(r.version)}") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Wie viel Prozent der Nutzer sollen diese Version bekommen? Die anderen behalten die vorherige.")
                    ChoiceChips(ROLLOUT_STEPS, value, { "$it %" }) { value = it }
                    Hint("Bei 100 % bekommen alle das Update und eine Benachrichtigung.")
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    dev.setRollout(fullName, r, value)
                    rolloutFor = null
                }) { Text("Übernehmen") }
            },
            dismissButton = { TextButton(onClick = { rolloutFor = null }) { Text("Abbrechen") } },
        )
    }
    if (testerDialog) {
        InputDialog(
            title = "Beta-Tester einladen",
            text = "Die Person bekommt eine E-Mail und ab sofort die Beta-Versionen.",
            label = "Benutzername",
            confirm = "Einladen",
            onConfirm = { dev.addTester(fullName, it) },
            onDismiss = { testerDialog = false },
        )
    }
}

@Composable
private fun Header(app: DevApp) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            LetterIcon(app.name, app.fullName, app.avatarUrl, 64.dp)
            Spacer(Modifier.width(14.dp))
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(app.name, style = MaterialTheme.typography.headlineSmall)
                Hint(app.fullName + (app.packageName?.let { " · $it" } ?: ""))
                ReviewBadge(app.review)
            }
        }
        if (app.review == "rejected" && app.reviewNote.isNotBlank()) {
            Hint("Begründung: ${app.reviewNote}", MaterialTheme.colorScheme.error)
        }
        StatRow(
            "${app.downloads}" to "Downloads",
            "${app.downloads30d}" to "30 Tage",
            "${app.sales}" to "Verkäufe",
            formatCents(app.revenueCents) to "Umsatz",
            "${app.unlockedUsers}" to "freigeschaltet",
        )
    }
}

@Composable
private fun UploadCard(app: DevApp, state: DevState, dev: DevViewModel) {
    var channel by rememberSaveable { mutableStateOf("stable") }
    var notes by rememberSaveable { mutableStateOf("") }
    var rollout by rememberSaveable { mutableStateOf(100) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            dev.uploadApk(app.fullName, uri, channel, notes, if (channel == "stable") rollout else 100)
            notes = ""
        }
    }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Neue Version hochladen", style = MaterialTheme.typography.titleSmall)
            ChoiceChips(listOf("stable", "beta"), channel, { if (it == "stable") "Stabil" else "Beta" }) { channel = it }
            if (channel == "stable") {
                Text("Gestaffelter Rollout", style = MaterialTheme.typography.labelLarge)
                ChoiceChips(ROLLOUT_STEPS, rollout, { "$it %" }) { rollout = it }
                if (rollout < 100) Hint("Erst $rollout % der Nutzer bekommen die Version. Später auf 100 % erhöhen.")
            }
            OutlinedTextField(notes, { notes = it.take(4000) }, label = { Text("Was ist neu?") }, minLines = 2,
                modifier = Modifier.fillMaxWidth())
            val progress = state.upload
            if (progress != null) {
                LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
                Hint("Lädt hoch … ${(progress * 100).toInt()} %")
            } else {
                Button(onClick = {
                    picker.launch(arrayOf("application/vnd.android.package-archive", "application/octet-stream"))
                }, modifier = Modifier.fillMaxWidth()) { Text("APK auswählen und hochladen") }
            }
            Hint("Version, Paketname und versionCode werden aus der APK gelesen und geprüft" +
                (if (app.reviewReleases) ". Neue Versionen werden vor der Veröffentlichung von einem Admin geprüft." else "."))
        }
    }
}

@Composable
private fun SettingsCard(app: DevApp, dev: DevViewModel) {
    var name by rememberSaveable(app.fullName) { mutableStateOf(app.name) }
    var description by rememberSaveable(app.fullName) { mutableStateOf(app.description) }
    var category by rememberSaveable(app.fullName) { mutableStateOf(app.category) }
    var homepage by rememberSaveable(app.fullName) { mutableStateOf(app.homepage) }
    var price by rememberSaveable(app.fullName) { mutableStateOf(priceText(app.priceCents)) }
    var access by rememberSaveable(app.fullName) { mutableStateOf(app.access) }
    var beta by rememberSaveable(app.fullName) { mutableStateOf(app.beta) }
    val iconPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) dev.uploadIcon(app.fullName, uri)
    }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionTitle("Einstellungen")
        OutlinedTextField(name, { name = it.take(60) }, label = { Text("Name") }, singleLine = true,
            modifier = Modifier.fillMaxWidth())
        OutlinedTextField(description, { description = it.take(4000) }, label = { Text("Beschreibung") }, minLines = 3,
            modifier = Modifier.fillMaxWidth())
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(category, { category = it.take(40) }, label = { Text("Kategorie") }, singleLine = true,
                modifier = Modifier.weight(1f))
            OutlinedTextField(price, { price = it.filter { c -> c.isDigit() || c == ',' || c == '.' }.take(7) },
                label = { Text("Preis €") }, singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal), modifier = Modifier.weight(0.6f))
        }
        OutlinedTextField(homepage, { homepage = it.trim().take(300) }, label = { Text("Webseite (optional)") },
            singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            modifier = Modifier.fillMaxWidth())
        Text("Freigabe", style = MaterialTheme.typography.labelLarge)
        ChoiceChips(Access.entries, access, { it.label }) { access = it }
        Hint(when (access) {
            Access.Open -> "Jeder sieht die App und kann sie installieren" + if (parsePrice(price) > 0) " (nach dem Kauf)." else "."
            Access.Code -> "Jeder sieht die App, installieren nur mit eingelöstem Freischalt-Code."
            Access.Hidden -> "Nur du und die Admins sehen die App."
        })
        Text("Beta-Programm", style = MaterialTheme.typography.labelLarge)
        ChoiceChips(BetaMode.entries, beta, { it.label }) { beta = it }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = {
                dev.update(app.fullName, JSONObject()
                    .put("name", name.trim()).put("description", description.trim()).put("category", category.trim())
                    .put("homepage", homepage).put("price_cents", parsePrice(price))
                    .put("access", access.apiValue).put("beta", beta.apiValue))
            }) { Text("Speichern") }
            OutlinedButton(onClick = { iconPicker.launch("image/*") }) { Text("Icon ändern") }
        }
    }
}

// ---------------------------------------------------------------------------
// Einmal-Codes einer App
// ---------------------------------------------------------------------------

@Composable
fun CodesScreen(fullName: String, dev: DevViewModel, vm: StoreViewModel, snackbar: SnackbarHostState) {
    val state by dev.state.collectAsStateWithLifecycle()
    LaunchedEffect(fullName) { if (state.codesFor != fullName) dev.openCodes(fullName) }
    val appName = state.current?.takeIf { it.fullName == fullName }?.name
        ?: vm.state.value.entry(fullName)?.app?.name ?: fullName
    var note by rememberSaveable { mutableStateOf("") }
    var count by rememberSaveable { mutableStateOf("1") }

    Scaffold(
        topBar = { BackTopBar("Codes · $appName", onBack = { vm.back() }) },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(
            Modifier.padding(padding).fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                Hint("Jeder Code schaltet die App für genau ein Konto frei – dauerhaft, inklusive Updates. " +
                    "Bei kostenpflichtigen Apps wirkt er wie ein Gutschein.")
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(note, { note = it.take(100) }, label = { Text("Notiz (z. B. für wen)") },
                        singleLine = true, modifier = Modifier.weight(1f))
                    OutlinedTextField(count, { v -> count = v.filter(Char::isDigit).take(2) }, label = { Text("Anzahl") },
                        singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                        modifier = Modifier.width(90.dp))
                }
            }
            item {
                Button(
                    onClick = { dev.createCodes(fullName, (count.toIntOrNull() ?: 1).coerceIn(1, 50), note) },
                    enabled = !state.loading,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Code erzeugen") }
            }
            if (state.loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
            if (state.codes.isEmpty() && !state.loading) item { EmptyText("Noch keine Codes für diese App.") }
            items(state.codes, key = { it.code }) { code ->
                CodeRow(code, fresh = code.code in state.freshCodes, appName = appName) { dev.deleteCode(code.code) }
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
        colors = if (fresh) CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer)
        else CardDefaults.cardColors(),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(start = 12.dp, top = 8.dp, bottom = 8.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f).clickable(enabled = !used) { clipboard.setText(AnnotatedString(code.code)) }) {
                Text(
                    code.code,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.titleMedium,
                    color = if (used) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface,
                )
                if (code.note.isNotBlank()) Text(code.note, style = MaterialTheme.typography.bodySmall)
                Text(
                    if (used) "Eingelöst von ${code.usedBy ?: "gelöschtem Konto"} am ${formatEpoch(code.usedAt ?: 0)}"
                    else "Frei · erstellt ${formatEpoch(code.createdAt)} · Tippen zum Kopieren",
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
