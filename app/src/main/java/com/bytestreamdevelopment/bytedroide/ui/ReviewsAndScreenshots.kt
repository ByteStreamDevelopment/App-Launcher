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
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Star
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import coil.compose.AsyncImage
import com.bytestreamdevelopment.bytedroide.data.Review
import com.bytestreamdevelopment.bytedroide.data.StoreApp

private val StarColor = Color(0xFFF59E0B)

fun stars(rating: Double): String {
    val full = Math.round(rating).toInt().coerceIn(0, 5)
    return "★".repeat(full) + "☆".repeat(5 - full)
}

// ---------------------------------------------------------------------------
// Screenshots
// ---------------------------------------------------------------------------

@Composable
fun ScreenshotGallery(urls: List<String>) {
    if (urls.isEmpty()) return
    var open by rememberSaveable { mutableStateOf<Int?>(null) }
    LazyRow(horizontalArrangement = Arrangement.spacedBy(10.dp), contentPadding = PaddingValues(vertical = 4.dp)) {
        itemsIndexed(urls) { index, url ->
            AsyncImage(
                model = url,
                contentDescription = "Screenshot ${index + 1}",
                contentScale = ContentScale.Fit,
                modifier = Modifier
                    .height(240.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .clickable { open = index },
            )
        }
    }
    open?.let { start ->
        Dialog(onDismissRequest = { open = null }, properties = DialogProperties(usePlatformDefaultWidth = false)) {
            val pager = rememberPagerState(initialPage = start) { urls.size }
            Box(Modifier.fillMaxSize().background(Color.Black)) {
                HorizontalPager(state = pager, modifier = Modifier.fillMaxSize()) { page ->
                    AsyncImage(
                        model = urls[page],
                        contentDescription = "Screenshot ${page + 1}",
                        contentScale = ContentScale.Fit,
                        modifier = Modifier.fillMaxSize().padding(8.dp),
                    )
                }
                IconButton(onClick = { open = null }, modifier = Modifier.align(Alignment.TopEnd).padding(8.dp)) {
                    Icon(Icons.Default.Close, "Schließen", tint = Color.White)
                }
                Text(
                    "${pager.currentPage + 1} / ${urls.size}",
                    color = Color.White,
                    modifier = Modifier.align(Alignment.BottomCenter).padding(16.dp),
                )
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Bewertungen
// ---------------------------------------------------------------------------

@Composable
fun ReviewsSection(app: StoreApp, state: UiState, vm: StoreViewModel) {
    LaunchedEffect(app.fullName) { vm.loadReviews(app.fullName) }
    val list = state.reviews[app.fullName]
    var editing by remember { mutableStateOf(false) }
    var replyTo by remember { mutableStateOf<Review?>(null) }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("Bewertungen", style = MaterialTheme.typography.titleMedium)
        HorizontalDivider()
        if (list == null) {
            Hint("Lädt …")
            return@Column
        }
        if (list.count > 0) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.width(96.dp)) {
                    Text("%.1f".format(list.average), style = MaterialTheme.typography.displaySmall)
                    Text(stars(list.average), color = StarColor)
                    Hint("${list.count} Bewertung" + if (list.count != 1) "en" else "")
                }
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    list.distribution.forEachIndexed { i, n ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("${5 - i}", style = MaterialTheme.typography.labelSmall, modifier = Modifier.width(12.dp))
                            LinearProgressIndicator(
                                progress = { if (list.count == 0) 0f else n.toFloat() / list.count },
                                color = StarColor,
                                modifier = Modifier.weight(1f).height(6.dp).clip(RoundedCornerShape(3.dp)),
                            )
                        }
                    }
                }
            }
        } else {
            Hint("Noch keine Bewertungen.")
        }

        when {
            list.canReview -> OutlinedButton(onClick = { editing = true }) {
                Text(if (list.mine != null) "Deine Bewertung bearbeiten" else "App bewerten")
            }
            state.user == null -> Hint("Zum Bewerten bitte anmelden und die App installieren.")
            !app.canManage -> Hint("Bewerten kannst du, nachdem du die App über ByteDroide geladen hast.")
        }

        list.reviews.take(30).forEach { r ->
            ReviewItem(
                review = r,
                canReply = list.canReply,
                canDelete = state.user?.isAdmin == true,
                onReply = { replyTo = r },
                onDelete = { vm.adminDeleteReview(app.fullName, r.userId) },
            )
        }
    }

    if (editing) {
        ReviewDialog(
            initial = list?.mine,
            onSave = { rating, text -> vm.setReview(app.fullName, rating, text) },
            onDelete = if (list?.mine != null) ({ vm.deleteReview(app.fullName) }) else null,
            onDismiss = { editing = false },
        )
    }
    replyTo?.let { r ->
        InputDialog(
            title = "Antwort an ${r.username}",
            text = "Die Antwort ist öffentlich sichtbar. ${r.username} bekommt eine Benachrichtigung.",
            label = "Antwort (leer = Antwort entfernen)",
            initial = r.reply,
            singleLine = false,
            allowEmpty = true,
            confirm = "Speichern",
            onConfirm = { vm.replyReview(app.fullName, r.userId, it) },
            onDismiss = { replyTo = null },
        )
    }
}

@Composable
private fun ReviewItem(review: Review, canReply: Boolean, canDelete: Boolean, onReply: () -> Unit, onDelete: () -> Unit) {
    Card(
        Modifier.fillMaxWidth(),
        colors = if (review.mine) CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.secondaryContainer)
        else CardDefaults.cardColors(),
    ) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(stars(review.rating.toDouble()), color = StarColor)
                Spacer(Modifier.width(8.dp))
                Text(review.username + if (review.mine) " (du)" else "", style = MaterialTheme.typography.titleSmall,
                    modifier = Modifier.weight(1f))
                if (canDelete) {
                    IconButton(onClick = onDelete, modifier = Modifier.size(32.dp)) {
                        Icon(Icons.Default.Delete, "Bewertung entfernen", modifier = Modifier.size(18.dp))
                    }
                }
            }
            Hint("${formatEpoch(review.updatedAt).substringBefore(' ')} · Version ${version(review.version)}")
            if (review.text.isNotBlank()) Text(review.text, style = MaterialTheme.typography.bodyMedium)
            if (review.reply.isNotBlank()) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(8.dp))
                        .background(MaterialTheme.colorScheme.surfaceVariant)
                        .padding(10.dp),
                ) {
                    Text("Antwort des Entwicklers", style = MaterialTheme.typography.labelMedium)
                    Text(review.reply, style = MaterialTheme.typography.bodySmall)
                }
            }
            if (canReply) {
                TextButton(onClick = onReply, contentPadding = PaddingValues(0.dp)) {
                    Text(if (review.reply.isBlank()) "Antworten" else "Antwort bearbeiten")
                }
            }
        }
    }
}

@Composable
private fun ReviewDialog(
    initial: Review?,
    onSave: (Int, String) -> Unit,
    onDelete: (() -> Unit)?,
    onDismiss: () -> Unit,
) {
    var rating by rememberSaveable { mutableIntStateOf(initial?.rating ?: 0) }
    var text by rememberSaveable { mutableStateOf(initial?.text.orEmpty()) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("App bewerten") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Row(horizontalArrangement = Arrangement.Center, modifier = Modifier.fillMaxWidth()) {
                    (1..5).forEach { i ->
                        IconButton(onClick = { rating = i }) {
                            Icon(
                                Icons.Default.Star,
                                contentDescription = "$i Sterne",
                                tint = if (i <= rating) StarColor else MaterialTheme.colorScheme.outlineVariant,
                                modifier = Modifier.size(36.dp),
                            )
                        }
                    }
                }
                OutlinedTextField(
                    value = text,
                    onValueChange = { text = it.take(2000) },
                    label = { Text("Was gefällt dir, was nicht? (optional)") },
                    minLines = 3,
                    modifier = Modifier.fillMaxWidth(),
                )
                Hint("Deine Bewertung ist mit deinem Benutzernamen öffentlich sichtbar.")
            }
        },
        confirmButton = {
            TextButton(enabled = rating > 0, onClick = {
                onSave(rating, text)
                onDismiss()
            }) { Text("Veröffentlichen") }
        },
        dismissButton = {
            Row {
                if (onDelete != null) {
                    TextButton(onClick = {
                        onDelete()
                        onDismiss()
                    }) { Text("Löschen", color = MaterialTheme.colorScheme.error) }
                }
                TextButton(onClick = onDismiss) { Text("Abbrechen") }
            }
        },
    )
}
