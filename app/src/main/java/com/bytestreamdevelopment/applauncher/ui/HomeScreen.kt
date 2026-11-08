package com.bytestreamdevelopment.applauncher.ui

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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountCircle
import androidx.compose.material.icons.filled.Build
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
import androidx.compose.material3.OutlinedTextField
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
import com.bytestreamdevelopment.applauncher.data.AppEntry

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
                    IconButton(onClick = { vm.navigate(Screen.Account) }) {
                        Icon(if (state.user != null) Icons.Default.AccountCircle else Icons.Default.Person, "Konto")
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
            state.query.isBlank() ||
                it.app.name.contains(state.query, ignoreCase = true) ||
                it.app.description.contains(state.query, ignoreCase = true) ||
                it.app.owner.contains(state.query, ignoreCase = true)
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
                OutlinedTextField(
                    value = state.query,
                    onValueChange = vm::setQuery,
                    placeholder = { Text("Apps durchsuchen") },
                    leadingIcon = { Icon(Icons.Default.Search, null) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                )
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

@Composable
private fun AppRow(entry: AppEntry, task: Task?, vm: StoreViewModel) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier
            .fillMaxWidth()
            .clickable { vm.navigate(Screen.Detail(entry.app.fullName)) }
            .padding(horizontal = 16.dp, vertical = 10.dp),
    ) {
        AppIcon(entry, 52.dp)
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    entry.app.name,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )
                AccessBadge(entry.app.access)
            }
            Text(
                entry.app.description.ifBlank { entry.app.owner },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                statusText(entry, task),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
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
