package com.bytestreamdevelopment.applauncher.ui

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.bytestreamdevelopment.applauncher.data.AppEntry
import com.bytestreamdevelopment.applauncher.data.Catalog
import com.bytestreamdevelopment.applauncher.data.InstallState
import com.bytestreamdevelopment.applauncher.data.StoreApp
import com.bytestreamdevelopment.applauncher.data.StoreSettings
import com.bytestreamdevelopment.applauncher.install.ApkInstaller
import com.bytestreamdevelopment.applauncher.install.InstallEvent
import com.bytestreamdevelopment.applauncher.install.InstallEvents
import com.bytestreamdevelopment.applauncher.work.UpdateCheckWorker
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

sealed interface Task {
    /** progress = 0..1, null = unbekannt */
    data class Downloading(val progress: Float?) : Task
    data object Installing : Task
}

sealed interface Screen {
    data object Home : Screen
    data class Detail(val fullName: String) : Screen
    data object Settings : Screen
}

enum class Tab { Discover, Updates, Installed }

data class UiState(
    val loading: Boolean = false,
    val loadedOnce: Boolean = false,
    val error: String? = null,
    val entries: List<AppEntry> = emptyList(),
    val tasks: Map<String, Task> = emptyMap(),
    val screen: Screen = Screen.Home,
    val tab: Tab = Tab.Discover,
    val query: String = "",
    val message: String? = null,
    val needsInstallPermission: Boolean = false,
) {
    val updates get() = entries.filter { it.state is InstallState.UpdateAvailable }
    val installed get() = entries.filter { it.state !is InstallState.NotInstalled }
    fun entry(fullName: String) = entries.firstOrNull { it.app.fullName == fullName }
}

class StoreViewModel(application: Application) : AndroidViewModel(application) {
    private val context get() = getApplication<Application>()
    val settings = StoreSettings(application)
    private val catalog = Catalog(application, settings)

    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    private var apps: List<StoreApp> = emptyList()
    private val jobs = mutableMapOf<String, Job>()
    private var loadJob: Job? = null

    init {
        viewModelScope.launch { InstallEvents.events.collect(::onInstallEvent) }
        refresh()
    }

    fun refresh() {
        loadJob?.cancel()
        loadJob = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                apps = catalog.load()
                _state.update { it.copy(entries = catalog.entries(apps), loading = false, loadedOnce = true) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update {
                    it.copy(loading = false, loadedOnce = true, error = e.message ?: e.javaClass.simpleName)
                }
            }
        }
    }

    /** Nach Rückkehr in die App (z. B. nach Deinstallation) Status neu bestimmen. */
    fun refreshInstallStates() {
        if (apps.isNotEmpty()) _state.update { it.copy(entries = catalog.entries(apps)) }
    }

    fun navigate(screen: Screen) = _state.update { it.copy(screen = screen) }
    fun selectTab(tab: Tab) = _state.update { it.copy(tab = tab, screen = Screen.Home) }
    fun setQuery(q: String) = _state.update { it.copy(query = q) }
    fun consumeMessage() = _state.update { it.copy(message = null) }
    fun dismissPermissionDialog() = _state.update { it.copy(needsInstallPermission = false) }
    private fun toast(msg: String) = _state.update { it.copy(message = msg) }

    fun back(): Boolean {
        if (_state.value.screen == Screen.Home) return false
        navigate(Screen.Home)
        return true
    }

    fun install(app: StoreApp) {
        if (_state.value.tasks.containsKey(app.fullName)) return
        if (!context.packageManager.canRequestPackageInstalls()) {
            _state.update { it.copy(needsInstallPermission = true) }
            return
        }
        jobs[app.fullName] = viewModelScope.launch {
            setTask(app.fullName, Task.Downloading(0f))
            try {
                val file = ApkInstaller.download(context, catalog.api(), app) { p ->
                    setTask(app.fullName, Task.Downloading(p))
                }
                val info = ApkInstaller.inspect(context, file)
                    ?: throw IllegalStateException("Heruntergeladene Datei ist keine gültige APK")
                settings.rememberPackage(app.fullName, info.packageName)
                setTask(app.fullName, Task.Installing)
                ApkInstaller.install(context, file, app.fullName, info.packageName)
            } catch (e: CancellationException) {
                setTask(app.fullName, null)
                throw e
            } catch (e: Exception) {
                setTask(app.fullName, null)
                toast("${app.name}: ${e.message ?: "Fehler"}")
            }
        }
    }

    fun cancel(fullName: String) {
        jobs.remove(fullName)?.cancel()
        setTask(fullName, null)
    }

    fun updateAll() = _state.value.updates.forEach { install(it.app) }

    fun open(entry: AppEntry) {
        val pkg = entry.packageName ?: return
        val intent = context.packageManager.getLaunchIntentForPackage(pkg)
        if (intent == null) {
            toast("${entry.app.name} hat keine startbare Oberfläche")
            return
        }
        context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    fun uninstall(entry: AppEntry) {
        val pkg = entry.packageName ?: return
        val intent = Intent(Intent.ACTION_DELETE, Uri.parse("package:$pkg"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    fun openUrl(url: String) {
        runCatching {
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    }

    fun openInstallPermissionSettings() {
        dismissPermissionDialog()
        val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    fun saveSettings(server: String, token: String, owners: String, updateCheck: Boolean) {
        settings.serverUrl = server
        settings.token = token
        settings.ownerFilter = owners
        settings.updateCheckEnabled = updateCheck
        UpdateCheckWorker.schedule(context, updateCheck)
        navigate(Screen.Home)
        toast("Einstellungen gespeichert")
        refresh()
    }

    private fun onInstallEvent(event: InstallEvent) {
        val name = apps.firstOrNull { it.fullName == event.fullName }?.name ?: event.fullName
        when (event) {
            is InstallEvent.WaitingForUser -> Unit
            is InstallEvent.Success -> {
                setTask(event.fullName, null)
                refreshInstallStates()
                toast("$name wurde installiert")
            }
            is InstallEvent.Aborted -> {
                setTask(event.fullName, null)
                toast("Installation von $name abgebrochen")
            }
            is InstallEvent.Failure -> {
                setTask(event.fullName, null)
                toast("$name: ${event.message}")
            }
        }
    }

    private fun setTask(fullName: String, task: Task?) = _state.update {
        it.copy(tasks = if (task == null) it.tasks - fullName else it.tasks + (fullName to task))
    }
}
