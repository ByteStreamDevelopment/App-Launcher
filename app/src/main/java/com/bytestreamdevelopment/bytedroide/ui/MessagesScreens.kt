package com.bytestreamdevelopment.bytedroide.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.bytestreamdevelopment.bytedroide.data.AppEntry
import com.bytestreamdevelopment.bytedroide.data.ChatMessage

private val KIND_ICONS = mapOf("bug" to "🐞", "feedback" to "💡", "question" to "❓")

// ---------------------------------------------------------------------------
// Liste
// ---------------------------------------------------------------------------

@Composable
fun MessagesScreen(state: UiState, vm: StoreViewModel, snackbar: SnackbarHostState) {
    LaunchedEffect(Unit) { vm.loadThreads() }
    Scaffold(
        topBar = {
            BackTopBar("Nachrichten", onBack = { vm.back() }) {
                IconButton(onClick = { vm.loadThreads() }) { Icon(Icons.Default.Refresh, "Aktualisieren") }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        LazyColumn(Modifier.padding(padding).fillMaxSize(), contentPadding = PaddingValues(vertical = 8.dp)) {
            item {
                Hint(
                    "Gespräche mit Entwicklern – und als Entwickler mit deinen Nutzern. Neue Gespräche startest du auf " +
                        "der Seite einer App.",
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
                )
            }
            if (state.threads.isEmpty()) item { EmptyText("Noch keine Nachrichten.") }
            items(state.threads, key = { it.id }) { t ->
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clickable { vm.navigate(Screen.Thread(t.id)) }
                        .padding(horizontal = 16.dp, vertical = 10.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Text(KIND_ICONS[t.kind] ?: "💬")
                        Text(
                            t.subject,
                            style = MaterialTheme.typography.titleSmall,
                            fontWeight = if (t.unread) FontWeight.Bold else FontWeight.Normal,
                            color = if (t.unread) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.weight(1f),
                        )
                        if (t.unread) Badge("neu", MaterialTheme.colorScheme.error)
                        if (t.status == "closed") Badge("erledigt", MaterialTheme.colorScheme.secondary)
                    }
                    Hint("${t.appName} · ${if (t.role == "dev") "von ${t.with}" else "an den Entwickler"} · " +
                        formatEpoch(t.updatedAt))
                    Text(t.preview, style = MaterialTheme.typography.bodySmall, maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
                HorizontalDivider()
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Gespräch
// ---------------------------------------------------------------------------

@Composable
fun ThreadScreen(id: Long, state: UiState, vm: StoreViewModel, snackbar: SnackbarHostState) {
    LaunchedEffect(id) { vm.openThread(id) }
    val t = state.thread?.takeIf { it.id == id }
    var text by rememberSaveable(id) { mutableStateOf("") }
    val listState = rememberLazyListState()
    LaunchedEffect(t?.messages?.size) { t?.let { if (it.messages.isNotEmpty()) listState.animateScrollToItem(it.messages.size) } }

    Scaffold(
        topBar = {
            BackTopBar(t?.subject ?: "Gespräch", onBack = { vm.back() }) {
                if (t != null) {
                    TextButton(onClick = { vm.setThreadStatus(id, t.status == "open") }) {
                        Text(if (t.status == "open") "Erledigt" else "Öffnen")
                    }
                }
            }
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize().imePadding()) {
            LazyColumn(
                Modifier.weight(1f).fillMaxWidth(),
                state = listState,
                contentPadding = PaddingValues(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (t == null) {
                    item { EmptyText("Lädt …") }
                    return@LazyColumn
                }
                item {
                    Column(Modifier.padding(bottom = 6.dp)) {
                        TextButton(onClick = { vm.navigate(Screen.Detail(t.app)) }, contentPadding = PaddingValues(0.dp)) {
                            Text("${t.kindLabel} zu ${t.appName}")
                        }
                        Hint(if (t.role == "dev") "von ${t.user} · ${formatEpoch(t.createdAt)}" else "an ${t.developer}")
                        if (t.device.isNotBlank()) Hint("Gerät: ${t.device}")
                        if (t.status == "closed") Hint("Als erledigt markiert – eine neue Nachricht öffnet das Gespräch wieder.")
                    }
                }
                items(t.messages, key = { it.id }) { m -> MessageBubble(m) }
            }
            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it.take(5000) },
                    placeholder = { Text("Nachricht schreiben …") },
                    maxLines = 5,
                    modifier = Modifier.weight(1f),
                )
                IconButton(
                    enabled = text.isNotBlank() && !state.busy && t != null,
                    onClick = {
                        vm.sendMessage(id, text)
                        text = ""
                    },
                ) { Icon(Icons.AutoMirrored.Filled.Send, "Senden") }
            }
        }
    }
}

@Composable
private fun MessageBubble(m: ChatMessage) {
    Box(Modifier.fillMaxWidth(), contentAlignment = if (m.mine) Alignment.CenterEnd else Alignment.CenterStart) {
        Column(
            Modifier
                .widthIn(max = 320.dp)
                .background(
                    if (m.mine) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surfaceVariant,
                    RoundedCornerShape(16.dp),
                )
                .padding(horizontal = 12.dp, vertical = 8.dp),
        ) {
            val color = if (m.mine) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant
            Text(
                "${m.author}${if (m.fromDev) " (Entwickler)" else ""} · ${formatEpoch(m.createdAt)}",
                style = MaterialTheme.typography.labelSmall,
                color = color.copy(alpha = 0.75f),
            )
            Text(m.body, style = MaterialTheme.typography.bodyMedium, color = color)
        }
    }
}

// ---------------------------------------------------------------------------
// Neues Gespräch
// ---------------------------------------------------------------------------

@Composable
fun ContactDeveloperDialog(entry: AppEntry, initialKind: String, vm: StoreViewModel, onDismiss: () -> Unit) {
    var kind by rememberSaveable { mutableStateOf(initialKind) }
    var subject by rememberSaveable { mutableStateOf("") }
    var message by rememberSaveable { mutableStateOf("") }
    var withDevice by rememberSaveable { mutableStateOf(initialKind == "bug") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Nachricht an den Entwickler") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                ChoiceChips(listOf("bug", "feedback", "question"), kind, {
                    when (it) {
                        "bug" -> "🐞 Fehler"
                        "feedback" -> "💡 Feedback"
                        else -> "❓ Frage"
                    }
                }) {
                    kind = it
                    if (it == "bug") withDevice = true
                }
                OutlinedTextField(subject, { subject = it.take(120) }, label = { Text("Betreff") }, singleLine = true,
                    modifier = Modifier.fillMaxWidth())
                OutlinedTextField(
                    message,
                    { message = it.take(5000) },
                    label = { Text(if (kind == "bug") "Was ist passiert? Was hättest du erwartet?" else "Nachricht") },
                    minLines = 4,
                    modifier = Modifier.fillMaxWidth(),
                )
                CheckRow(withDevice, { withDevice = it }) {
                    Column {
                        Text("Geräteinfos mitsenden", style = MaterialTheme.typography.bodyMedium)
                        Hint(vm.deviceInfo(entry))
                    }
                }
                Spacer(Modifier.padding(0.dp))
            }
        },
        confirmButton = {
            TextButton(enabled = subject.isNotBlank() && message.isNotBlank(), onClick = {
                vm.contactDeveloper(entry, kind, subject, message, withDevice)
                onDismiss()
            }) { Text("Senden") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Abbrechen") } },
    )
}
