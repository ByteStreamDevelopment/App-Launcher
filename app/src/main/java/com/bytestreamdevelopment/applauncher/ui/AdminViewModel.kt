package com.bytestreamdevelopment.applauncher.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.bytestreamdevelopment.applauncher.data.Access
import com.bytestreamdevelopment.applauncher.data.AccessCode
import com.bytestreamdevelopment.applauncher.data.AdminApp
import com.bytestreamdevelopment.applauncher.data.AdminUser
import com.bytestreamdevelopment.applauncher.data.StoreApi
import com.bytestreamdevelopment.applauncher.data.StoreSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

enum class AdminTab { Apps, Users }

data class AdminState(
    val tab: AdminTab = AdminTab.Apps,
    val loading: Boolean = false,
    val apps: List<AdminApp> = emptyList(),
    val users: List<AdminUser> = emptyList(),
    /** Codes der gerade geöffneten App */
    val codesFor: String? = null,
    val codes: List<AccessCode> = emptyList(),
    /** Zuletzt erzeugte Codes (zum Hervorheben / Teilen) */
    val freshCodes: List<String> = emptyList(),
    val error: String? = null,
)

class AdminViewModel(application: Application) : AndroidViewModel(application) {
    private val settings = StoreSettings(application)
    private val _state = MutableStateFlow(AdminState())
    val state: StateFlow<AdminState> = _state

    /** Meldungen an die Oberfläche (Snackbar über das Haupt-ViewModel). */
    var onMessage: (String) -> Unit = {}
    /** Wird nach Änderungen aufgerufen, damit der Store-Katalog neu lädt. */
    var onCatalogChanged: () -> Unit = {}

    private fun api() = StoreApi(settings.serverUrl, settings.sessionToken.ifBlank { null })

    fun selectTab(tab: AdminTab) {
        _state.update { it.copy(tab = tab) }
        load()
    }

    fun load(refreshCatalog: Boolean = false) = run(showLoading = true) {
        val apps = api().adminApps(refreshCatalog)
        val users = api().users()
        _state.update { it.copy(apps = apps, users = users) }
        if (refreshCatalog) onCatalogChanged()
    }

    fun setAccess(app: AdminApp, access: Access) = run {
        api().setAccess(app.fullName, access)
        _state.update { s -> s.copy(apps = s.apps.map { if (it.fullName == app.fullName) it.copy(access = access) else it }) }
        onMessage("${app.name}: ${access.label}")
        onCatalogChanged()
    }

    fun openCodes(fullName: String) {
        _state.update { it.copy(codesFor = fullName, codes = emptyList(), freshCodes = emptyList()) }
        loadCodes(fullName)
    }

    private fun loadCodes(fullName: String) = run(showLoading = true) {
        val codes = api().codes(fullName)
        _state.update { if (it.codesFor == fullName) it.copy(codes = codes) else it }
    }

    fun createCodes(fullName: String, count: Int, note: String) = run(showLoading = true) {
        val created = api().createCodes(fullName, count, note.trim())
        val codes = api().codes(fullName)
        _state.update { it.copy(codes = codes, freshCodes = created) }
        refreshAppsQuietly()
        onMessage(if (created.size == 1) "Code erstellt: ${created.first()}" else "${created.size} Codes erstellt")
    }

    fun deleteCode(fullName: String, code: String) = run {
        api().deleteCode(code)
        _state.update { s -> s.copy(codes = s.codes.filterNot { it.code == code }, freshCodes = s.freshCodes - code) }
        refreshAppsQuietly()
    }

    fun setAdmin(user: AdminUser, admin: Boolean) = run {
        api().setAdmin(user.user.id, admin)
        _state.update { it.copy(users = api().users()) }
        onMessage(if (admin) "${user.user.username} ist jetzt Admin" else "${user.user.username} ist kein Admin mehr")
    }

    fun deleteUser(user: AdminUser) = run {
        api().deleteUser(user.user.id)
        _state.update { s -> s.copy(users = s.users.filterNot { it.user.id == user.user.id }) }
        onMessage("${user.user.username} gelöscht")
    }

    fun revokeUnlock(user: AdminUser, fullName: String, appName: String) = run {
        api().revokeUnlock(user.user.id, fullName)
        _state.update { it.copy(users = api().users()) }
        refreshAppsQuietly()
        onMessage("Zugriff auf $appName für ${user.user.username} entzogen")
    }

    private fun refreshAppsQuietly() {
        runCatching { api().adminApps(false) }.onSuccess { apps -> _state.update { it.copy(apps = apps) } }
    }

    private fun run(showLoading: Boolean = false, block: suspend () -> Unit) {
        viewModelScope.launch {
            if (showLoading) _state.update { it.copy(loading = true) }
            try {
                withContext(Dispatchers.IO) { block() }
                _state.update { it.copy(loading = false, error = null) }
            } catch (e: Exception) {
                _state.update { it.copy(loading = false, error = e.message) }
                onMessage(e.message ?: "Fehler")
            }
        }
    }
}
