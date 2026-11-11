package com.bytestreamdevelopment.bytedroide.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Create
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.bytestreamdevelopment.bytedroide.data.AppEntry
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import com.bytestreamdevelopment.bytedroide.data.InstallState

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(state: UiState, vm: StoreViewModel, snackbar: SnackbarHostState) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("ByteDroide") },
                actions = {
                    if (state.user?.isAdmin == true) {
                        IconButton(onClick = { vm.navigate(Screen.Admin) }) { Icon(Icons.Default.Build, "Admin-Bereich") }
                    }
                    if (state.user?.isDeveloper == true) {
                        IconButton(onClick = { vm.navigate(Screen.Dev) }) { Icon(Icons.Default.Create, "Entwickler-Bereich") }
                    }
                    IconButton(onClick = { vm.navigate(Screen.Account) }) {
                        if (state.unreadMessages > 0) {
                            BadgedBox(badge = { Badge { Text("${state.unreadMessages}") } }) {
                                Icon(Icons.Default.AccountCircle, "Konto, ${state.unreadMessages} neue Nachrichten")
                            }
                        } else {
                            Icon(if (state.user != null) Icons.Default.AccountCircle else Icons.Default.Person, "Konto")
                        }
                    }
                    IconButton(onClick = vm::refresh) { Icon(Icons.Default.Refresh, "Aktualisieren") }
                    IconButton(onClick = { vm.navigate(Screen.Settings) }) {
                        Icon(Icons.Default.Settings, "Einstellungen")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(snackbar) },
    ) { padding ->
        Column(Modifier.padding(padding).fillMaxSize()) {
            TabRow(selectedTabIndex = state.tab.ordinal) {
                Tab(state.tab == Tab.Discover, onClick = { vm.selectTab(Tab.Discover) }, text = { Text("Entdecken") })
                Tab(state.tab == Tab.Updates, onClick = { vm.selectTab(Tab.Updates) }, text = {
                    val n = state.updates.size
                    if (n > 0) {
                        BadgedBox(badge = { Badge { Text("$n") } }) { Text("Updates") }
                    } else {
                        Text("Updates")
                    }
                })
                Tab(state.tab == Tab.Installed, onClick = { vm.selectTab(Tab.Installed) }, text = { Text("Installiert") })
            }

            PullToRefreshBox(
                isRefreshing = state.loading && state.loadedOnce,
                onRefresh = vm::refresh,
                modifier = Modifier.fillMaxSize(),
            ) {
                when {
                    !state.loadedOnce -> Centered { CircularProgressIndicator() }
                    state.error != null && state.entries.isEmpty() -> Centered {
                        Text("Katalog konnte nicht geladen werden", style = MaterialTheme.typography.titleMedium)
                        Text(state.error, textAlign = TextAlign.Center, modifier = Modifier.padding(8.dp))
                        Button(onClick = vm::refresh) { Text("Erneut versuchen") }
                    }
                    else -> AppList(state, vm)
                }
            }
        }
    }
}

@Composable
private fun AppList(state: UiState, vm: StoreViewModel) {
    val list: List<AppEntry> = when (state.tab) {
        Tab.Discover -> state.entries.filter {
            (state.category == null || it.app.category == state.category) && (
                state.query.isBlank() ||
                    it.app.name.contains(state.query, ignoreCase = true) ||
                    it.app.description.contains(state.query, ignoreCase = true) ||
                    it.app.owner.contains(state.query, ignoreCase = true)
                )
        }
        Tab.Updates -> state.updates
        Tab.Installed -> state.installed
    }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(vertical = 8.dp),
    ) {
        if (state.tab == Tab.Discover) {
            item {
                TextField(
                    value = state.query,
                    onValueChange = vm::setQuery,
                    placeholder = { Text("Apps suchen") },
                    leadingIcon = { Icon(Icons.Default.Search, null) },
                    singleLine = true,
                    shape = RoundedCornerShape(28.dp),
                    colors = TextFieldDefaults.colors(
                        focusedIndicatorColor = Color.Transparent,
                        unfocusedIndicatorColor = Color.Transparent,
                        focusedContainerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
                        unfocusedContainerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
                    ),
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
                )
            }
            if (state.categories.isNotEmpty()) {
                item {
                    Row(
                        Modifier.horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        FilterChip(state.category == null, onClick = { vm.setCategory(null) }, label = { Text("Für dich") })
                        state.categories.forEach { c ->
                            FilterChip(state.category == c, onClick = { vm.setCategory(c) }, label = { Text(c) })
                        }
                    }
                }
            }
            if (state.query.isBlank() && state.category == null && list.size >= 3) {
                val newest = list.sortedByDescending { it.app.release.publishedAt }.take(15)
                val popular = list.sortedByDescending { popularity(it) }
                item { Shelf("Neu im Store", newest, vm) }
                if (list.any { it.app.ratingCount > 0 || it.app.downloads > 0 }) {
                    item { Shelf("Beliebt", popular.take(15), vm) }
                }
                list.groupBy { it.app.category }
                    .filter { (c, apps) -> c.isNotBlank() && apps.size >= 3 }
                    .entries.sortedByDescending { it.value.size }.take(4)
                    .forEach { (c, apps) ->
                        item(key = "shelf-$c") {
                            Shelf(c, apps.sortedByDescending { popularity(it) }, vm) { vm.setCategory(c) }
                        }
                    }
                item { SectionTitle("Top-Charts") }
                itemsIndexed(popular, key = { _, e -> "chart-" + e.app.fullName }) { i, entry ->
                    AppRow(entry, state.tasks[entry.app.fullName], vm, rank = i + 1)
                }
                return@LazyColumn
            }
        }
        if (state.tab == Tab.Updates && list.size > 1) {
            item {
                Button(
                    onClick = vm::updateAll,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                ) { Text("Alle aktualisieren (${list.size})") }
            }
        }
        if (list.isEmpty()) {
            item {
                Text(
                    text = when (state.tab) {
                        Tab.Discover -> if (state.query.isBlank()) {
                            "Keine Apps gefunden."
                        } else {
                            "Keine Treffer für „${state.query}“"
                        }
                        Tab.Updates -> "Alles aktuell ✓"
                        Tab.Installed -> "Noch keine Apps über den Store installiert."
                    },
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.bodyLarge,
                    modifier = Modifier.fillMaxWidth().padding(32.dp),
                )
            }
        }
        items(list, key = { it.app.fullName }) { entry ->
            AppRow(entry, state.tasks[entry.app.fullName], vm)
        }
    }
}

private fun popularity(e: AppEntry): Double =
    e.app.ratingAverage * minOf(e.app.ratingCount, 20) + minOf(e.app.downloads, 1000) / 50.0

@Composable
private fun SectionTitle(title: String, onMore: (() -> Unit)? = null) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .then(if (onMore != null) Modifier.clickable(onClick = onMore) else Modifier)
            .padding(start = 16.dp, end = 8.dp, top = 18.dp, bottom = 8.dp),
    ) {
        Text(title, style = MaterialTheme.typography.titleLarge, modifier = Modifier.weight(1f))
        if (onMore != null) Icon(Icons.AutoMirrored.Filled.ArrowForward, "Alle anzeigen")
    }
}

/** Horizontale Reihe mit Icon-Kacheln (wie im Play Store). */
@Composable
private fun Shelf(title: String, apps: List<AppEntry>, vm: StoreViewModel, onMore: (() -> Unit)? = null) {
    Column {
        SectionTitle(title, onMore)
        LazyRow(
            contentPadding = PaddingValues(horizontal = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            items(apps, key = { it.app.fullName }) { entry -> AppTile(entry, vm) }
        }
    }
}

@Composable
private fun AppTile(entry: AppEntry, vm: StoreViewModel) {
    Column(
        Modifier
            .width(112.dp)
            .clip(RoundedCornerShape(16.dp))
            .clickable { vm.navigate(Screen.Detail(entry.app.fullName)) }
            .padding(6.dp),
    ) {
        AppIcon(entry, 100.dp)
        Spacer(Modifier.height(6.dp))
        Text(
            entry.app.name,
            style = MaterialTheme.typography.bodyMedium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        val meta = when {
            entry.state is InstallState.UpdateAvailable -> "Update"
            entry.state is InstallState.UpToDate -> "Installiert"
            entry.app.ratingCount > 0 -> "%.1f ★".format(entry.app.ratingAverage)
            entry.app.isPaid -> entry.app.price
            else -> entry.app.category
        }
        Text(
            meta,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun AppRow(entry: AppEntry, task: Task?, vm: StoreViewModel, rank: Int? = null) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .clickable { vm.navigate(Screen.Detail(entry.app.fullName)) }
            .padding(horizontal = 16.dp, vertical = 8.dp),
    ) {
        if (rank != null) {
            Text(
                "$rank",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
                modifier = Modifier.width(28.dp),
            )
        }
        AppIcon(entry, 56.dp)
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(1.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    entry.app.name,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )
                AppBadges(entry.app)
            }
            Text(
                listOf(entry.app.owner, entry.app.category).filter { it.isNotBlank() }.joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            val meta = buildList {
                if (entry.app.ratingCount > 0) add("%.1f ★".format(entry.app.ratingAverage))
                if (entry.app.downloads > 0) add("${entry.app.downloadsLabel} Downloads")
            }.joinToString(" · ")
            val status = statusText(entry, task)
            Text(
                if (meta.isBlank()) status else "$meta · $status",
                style = MaterialTheme.typography.labelMedium,
                color = if (entry.state is InstallState.UpdateAvailable) {
                    MaterialTheme.colorScheme.primary
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant
                },
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Spacer(Modifier.width(8.dp))
        ActionButton(entry, task, vm)
    }
}

@Composable
private fun Centered(content: @Composable () -> Unit) {
    Box(Modifier.fillMaxSize().padding(24.dp), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) { content() }
    }
}
