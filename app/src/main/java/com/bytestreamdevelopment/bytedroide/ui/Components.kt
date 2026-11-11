package com.bytestreamdevelopment.bytedroide.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.drawable.toBitmap
import coil.compose.AsyncImage
import com.bytestreamdevelopment.bytedroide.data.Access
import com.bytestreamdevelopment.bytedroide.data.AppEntry
import com.bytestreamdevelopment.bytedroide.data.InstallState
import com.bytestreamdevelopment.bytedroide.data.StoreApp
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import kotlin.math.abs

/** Icon: installiertes App-Icon > Store-Icon > farbiger Buchstabe. */
@Composable
fun AppIcon(entry: AppEntry, size: Dp, installedKey: Any? = entry.state) {
    val context = LocalContext.current
    val bitmap = remember(entry.packageName, installedKey) {
        val pkg = entry.packageName
        if (pkg != null && entry.state !is InstallState.NotInstalled) {
            runCatching {
                context.packageManager.getApplicationIcon(pkg).toBitmap(192, 192).asImageBitmap()
            }.getOrNull()
        } else {
            null
        }
    }
    if (bitmap != null) {
        Image(bitmap, contentDescription = null, modifier = Modifier.size(size).clip(RoundedCornerShape(size / 4.5f)))
    } else {
        LetterIcon(entry.app.name, entry.app.fullName, entry.app.avatarUrl, size)
    }
}

@Composable
fun LetterIcon(name: String, key: String, url: String?, size: Dp) {
    val modifier = Modifier.size(size).clip(RoundedCornerShape(size / 4.5f))
    if (url != null) {
        AsyncImage(model = url, contentDescription = null, contentScale = ContentScale.Crop, modifier = modifier)
        return
    }
    val hue = (abs(key.hashCode()) % 360).toFloat()
    Box(modifier = modifier.background(Color.hsv(hue, 0.45f, 0.75f)), contentAlignment = Alignment.Center) {
        Text(
            text = name.take(1).uppercase(),
            color = Color.White,
            fontWeight = FontWeight.Bold,
            fontSize = (size.value * 0.45f).sp,
        )
    }
}

/** Haupt-Aktionsknopf je nach Status: Kaufen / Code / Installieren / Aktualisieren / Öffnen / Fortschritt. */
@Composable
fun ActionButton(entry: AppEntry, task: Task?, vm: StoreViewModel, modifier: Modifier = Modifier) {
    val app = entry.app
    when {
        task != null -> TaskIndicator(task, onCancel = { vm.cancel(app.fullName) })
        !app.unlocked && entry.state is InstallState.UpToDate ->
            FilledTonalButton(onClick = { vm.open(entry) }, modifier = modifier) { Text("Öffnen") }
        !app.unlocked && app.isPaid ->
            Button(onClick = { vm.requestBuy(app) }, modifier = modifier) { Text(app.price) }
        !app.unlocked ->
            OutlinedButton(onClick = { vm.requestRedeem(app.fullName) }, modifier = modifier) {
                Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("Code")
            }
        entry.state is InstallState.UpdateAvailable ->
            Button(onClick = { vm.install(app) }, modifier = modifier) { Text("Aktualisieren") }
        entry.state is InstallState.UpToDate ->
            FilledTonalButton(onClick = { vm.open(entry) }, modifier = modifier) { Text("Öffnen") }
        else ->
            Button(onClick = { vm.install(app) }, modifier = modifier) { Text("Installieren") }
    }
}

@Composable
fun TaskIndicator(task: Task, onCancel: () -> Unit) {
    Box(contentAlignment = Alignment.Center) {
        when (task) {
            is Task.Downloading -> {
                if (task.progress != null) {
                    CircularProgressIndicator(progress = { task.progress }, modifier = Modifier.size(40.dp))
                } else {
                    CircularProgressIndicator(modifier = Modifier.size(40.dp))
                }
                OutlinedButton(
                    onClick = onCancel,
                    modifier = Modifier.size(40.dp),
                    contentPadding = PaddingValues(0.dp),
                    border = null,
                ) {
                    Text("✕", style = MaterialTheme.typography.labelLarge)
                }
            }
            Task.Installing -> CircularProgressIndicator(modifier = Modifier.size(40.dp))
        }
    }
}

fun statusText(entry: AppEntry, task: Task?): String = when {
    task is Task.Downloading ->
        task.progress?.let { "Lädt herunter … ${(it * 100).toInt()} %" } ?: "Lädt herunter …"
    task is Task.Installing -> "Wird installiert …"
    !entry.app.unlocked && entry.state is InstallState.NotInstalled ->
        if (entry.app.isPaid) "Kostenpflichtig · ${entry.app.price}" else "Freischalt-Code nötig"
    else -> when (val s = entry.state) {
        InstallState.NotInstalled -> (if (entry.app.isBetaRelease) "Beta " else "Version ") + version(entry.app.release.tag)
        is InstallState.UpToDate -> "Installiert · ${s.installedVersion}"
        is InstallState.UpdateAvailable -> "Update: ${s.installedVersion} → ${s.latestVersion}"
    }
}

fun version(tag: String) = com.bytestreamdevelopment.bytedroide.data.Versions.normalize(tag)

fun formatDate(iso: String): String = runCatching {
    OffsetDateTime.parse(iso).format(DateTimeFormatter.ofPattern("dd.MM.yyyy"))
}.getOrDefault(iso)

fun formatEpoch(seconds: Long): String = runCatching {
    java.time.Instant.ofEpochSecond(seconds).atZone(java.time.ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
}.getOrDefault("")

/** Kleine Etiketten: Code, versteckt, Beta, nicht geprüft. */
@Composable
fun AppBadges(app: StoreApp) {
    if (app.access == Access.Code && !app.isPaid) Badge("🔒 Code", MaterialTheme.colorScheme.tertiary)
    if (app.access == Access.Hidden) Badge("Versteckt", MaterialTheme.colorScheme.error)
    if (app.isBetaRelease) Badge("Beta", MaterialTheme.colorScheme.secondary)
    if (app.review != "approved") Badge("In Prüfung", MaterialTheme.colorScheme.error)
}

@Composable
fun Badge(text: String, color: Color) {
    Surface(color = color.copy(alpha = 0.12f), shape = RoundedCornerShape(50)) {
        Text(
            text,
            style = MaterialTheme.typography.labelSmall,
            color = color,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
        )
    }
}

// --- Allgemeine Bausteine ---------------------------------------------------

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun BackTopBar(title: String, onBack: () -> Unit, actions: @Composable RowScope.() -> Unit = {}) {
    TopAppBar(
        title = { Text(title, maxLines = 1) },
        navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Zurück") } },
        actions = actions,
    )
}

@Composable
fun SectionTitle(text: String) {
    Text(text, style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 4.dp))
}

@Composable
fun Hint(text: String, color: Color = MaterialTheme.colorScheme.onSurfaceVariant, modifier: Modifier = Modifier) {
    Text(text, style = MaterialTheme.typography.bodySmall, color = color, modifier = modifier)
}

@Composable
fun EmptyText(text: String) {
    Box(Modifier.fillMaxWidth().padding(24.dp), contentAlignment = Alignment.Center) {
        Text(text, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** Auswahl über Chips (statt Dropdown). */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun <T> ChoiceChips(options: List<T>, selected: T, label: (T) -> String, enabled: Boolean = true, onSelect: (T) -> Unit) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { option ->
            FilterChip(
                selected = option == selected,
                enabled = enabled,
                onClick = { if (option != selected) onSelect(option) },
                label = { Text(label(option)) },
            )
        }
    }
}

@Composable
fun ConfirmDialog(title: String, text: String, confirm: String, onConfirm: () -> Unit, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(text) },
        confirmButton = {
            TextButton(onClick = {
                onConfirm()
                onDismiss()
            }) { Text(confirm) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}

/** Dialog mit einem Eingabefeld. */
@Composable
fun InputDialog(
    title: String,
    label: String,
    confirm: String,
    text: String? = null,
    initial: String = "",
    password: Boolean = false,
    keyboardType: KeyboardType = KeyboardType.Text,
    singleLine: Boolean = true,
    allowEmpty: Boolean = false,
    onConfirm: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var value by rememberSaveable { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                text?.let { Text(it) }
                OutlinedTextField(
                    value = value,
                    onValueChange = { value = it },
                    label = { Text(label) },
                    singleLine = singleLine,
                    minLines = if (singleLine) 1 else 3,
                    visualTransformation = if (password) PasswordVisualTransformation()
                    else androidx.compose.ui.text.input.VisualTransformation.None,
                    keyboardOptions = KeyboardOptions(keyboardType = if (password) KeyboardType.Password else keyboardType),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(enabled = allowEmpty || value.isNotBlank(), onClick = {
                onConfirm(value)
                onDismiss()
            }) { Text(confirm) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun StatRow(vararg stats: Pair<String, String>) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(20.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        stats.forEach { (value, label) ->
            Column {
                Text(value, style = MaterialTheme.typography.titleLarge)
                Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
