package com.bytestreamdevelopment.applauncher.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.Icon
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.drawable.toBitmap
import coil.compose.AsyncImage
import com.bytestreamdevelopment.applauncher.data.Access
import com.bytestreamdevelopment.applauncher.data.AppEntry
import com.bytestreamdevelopment.applauncher.data.InstallState
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import kotlin.math.abs

/** Icon: installiertes App-Icon > Repo-Avatar > farbiger Buchstabe. */
@Composable
fun AppIcon(entry: AppEntry, size: Dp, installedKey: Any? = entry.state) {
    val context = LocalContext.current
    val shape = RoundedCornerShape(size / 4.5f)
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
    val modifier = Modifier.size(size).clip(shape)
    when {
        bitmap != null -> Image(bitmap, contentDescription = null, modifier = modifier)
        entry.app.avatarUrl != null -> AsyncImage(
            model = entry.app.avatarUrl,
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = modifier,
        )
        else -> {
            val hue = (abs(entry.app.fullName.hashCode()) % 360).toFloat()
            Box(
                modifier = modifier.background(Color.hsv(hue, 0.45f, 0.75f)),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = entry.app.name.take(1).uppercase(),
                    color = Color.White,
                    fontWeight = FontWeight.Bold,
                    fontSize = (size.value * 0.45f).sp,
                )
            }
        }
    }
}

/** Haupt-Aktionsknopf je nach Status: Installieren / Aktualisieren / Öffnen / Fortschritt. */
@Composable
fun ActionButton(entry: AppEntry, task: Task?, vm: StoreViewModel, modifier: Modifier = Modifier) {
    when {
        task != null -> TaskIndicator(task, onCancel = { vm.cancel(entry.app.fullName) })
        !entry.app.unlocked && entry.state is InstallState.UpToDate ->
            FilledTonalButton(onClick = { vm.open(entry) }, modifier = modifier) { Text("Öffnen") }
        !entry.app.unlocked ->
            OutlinedButton(onClick = { vm.requestRedeem(entry.app.fullName) }, modifier = modifier) {
                Icon(Icons.Default.Lock, contentDescription = null, modifier = Modifier.size(18.dp))
                Spacer(Modifier.width(6.dp))
                Text("Code")
            }
        entry.state is InstallState.UpdateAvailable ->
            Button(onClick = { vm.install(entry.app) }, modifier = modifier) { Text("Aktualisieren") }
        entry.state is InstallState.UpToDate ->
            FilledTonalButton(onClick = { vm.open(entry) }, modifier = modifier) { Text("Öffnen") }
        else ->
            Button(onClick = { vm.install(entry.app) }, modifier = modifier) { Text("Installieren") }
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
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(0.dp),
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
    !entry.app.unlocked && entry.state is InstallState.NotInstalled -> "Freischalt-Code nötig"
    else -> when (val s = entry.state) {
        InstallState.NotInstalled -> "Version ${version(entry.app.release.tag)}"
        is InstallState.UpToDate -> "Installiert · ${s.installedVersion}"
        is InstallState.UpdateAvailable -> "Update: ${s.installedVersion} → ${s.latestVersion}"
    }
}

fun version(tag: String) = tag.removePrefix("v").removePrefix("V")

fun formatDate(iso: String): String = runCatching {
    OffsetDateTime.parse(iso).format(DateTimeFormatter.ofPattern("dd.MM.yyyy"))
}.getOrDefault(iso)

fun formatEpoch(seconds: Long): String = runCatching {
    java.time.Instant.ofEpochSecond(seconds).atZone(java.time.ZoneId.systemDefault())
        .format(DateTimeFormatter.ofPattern("dd.MM.yyyy HH:mm"))
}.getOrDefault("")

/** Kleines Etikett für die Freigabe (nur sichtbar, wenn nicht "offen"). */
@Composable
fun AccessBadge(access: Access) {
    if (access == Access.Open) return
    val color = if (access == Access.Hidden) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.tertiary
    Text(
        text = if (access == Access.Hidden) "Versteckt" else "🔒 Code",
        style = MaterialTheme.typography.labelSmall,
        color = color,
    )
}
