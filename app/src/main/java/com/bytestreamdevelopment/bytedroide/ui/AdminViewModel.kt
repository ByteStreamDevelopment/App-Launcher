package com.bytestreamdevelopment.bytedroide.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.bytestreamdevelopment.bytedroide.data.AdminOverview
import com.bytestreamdevelopment.bytedroide.data.AdminPurchase
import com.bytestreamdevelopment.bytedroide.data.AdminUser
import com.bytestreamdevelopment.bytedroide.data.DevApp
import com.bytestreamdevelopment.bytedroide.data.PendingRelease
import com.bytestreamdevelopment.bytedroide.data.Role
import com.bytestreamdevelopment.bytedroide.data.StoreApi
import com.bytestreamdevelopment.bytedroide.data.StoreSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

enum class AdminTab(val label: String) { Requests("Anfragen"), Apps("Apps"), Users("Benutzer"), Purchases("Käufe") }

data class AdminState(
    val tab: AdminTab = AdminTab.Requests,
    val loading: Boolean = false,
    val overview: AdminOverview? = null,
    val apps: List<DevApp> = emptyList(),
    val users: List<AdminUser> = emptyList(),
    val purchases: List<AdminPurchase> = emptyList(),
    val pendingReleases: List<PendingRelease> = emptyList(),
)

class AdminViewModel(application: Application) : AndroidViewModel(application) {
    private val settings = StoreSettings(application)
    private val _state = MutableStateFlow(AdminState())
    val state: StateFlow<AdminState> = _state

    /** Meldungen an die Oberfläche (Snackbar über das Haupt-ViewModel). */
    var onMessage: (String) -> Unit = {}
    /** Wird nach Änderungen aufgerufen, damit der Store-Katalog neu lädt. */
    var onCatalogChanged: () -> Unit = {}

    private fun api() = StoreApi(settings.serverUrl, settings.sessionToken.ifBlank { null }, settings.installId)

    fun selectTab(tab: AdminTab) {
        _state.update { it.copy(tab = tab) }
        if (tab == AdminTab.Purchases) loadPurchases()
    }

    fun load(refreshCatalog: Boolean = false) = run(showLoading = true) {
        val api = api()
        val overview = api.overview()
        val apps = api.adminApps(refreshCatalog)
        val users = api.users()
        val pending = runCatching { api.pendingReleases() }.getOrDefault(emptyList())
        _state.update { it.copy(overview = overview, apps = apps, users = users, pendingReleases = pending) }
        if (refreshCatalog) onCatalogChanged()
    }

    private fun loadPurchases() = run(showLoading = true) {
        val purchases = api().adminPurchases()
        _state.update { it.copy(purchases = purchases) }
    }

    fun review(app: DevApp, approve: Boolean, note: String = "") = run {
        api().adminUpdateApp(app.fullName, JSONObject().put("review", if (approve) "approved" else "rejected")
            .put("review_note", note))
        refreshQuietly()
        onMessage(if (approve) "${app.name} freigegeben" else "${app.name} abgelehnt")
        onCatalogChanged()
    }

    fun decideRelease(release: PendingRelease, approve: Boolean, note: String = "") = run {
        api().decideRelease(release, approve, note)
        refreshQuietly()
        onMessage("${release.name} ${release.version}: " + if (approve) "freigegeben" else "abgelehnt")
        onCatalogChanged()
    }

    fun decideDeveloper(user: AdminUser, approve: Boolean, note: String = "") = run {
        api().decideDeveloper(user.user.id, approve, note)
        refreshQuietly()
        onMessage(if (approve) "${user.user.username} ist jetzt Entwickler" else "Anfrage von ${user.user.username} abgelehnt")
    }

    fun setRole(user: AdminUser, role: Role) = run {
        api().setRole(user.user.id, role)
        refreshQuietly()
        onMessage("${user.user.username} ist jetzt ${role.label}")
    }

    fun deleteUser(user: AdminUser) = run {
        api().deleteUser(user.user.id)
        refreshQuietly()
        onMessage("${user.user.username} gelöscht")
    }

    fun revokeUnlock(user: AdminUser, fullName: String, appName: String) = run {
        api().revokeUnlock(user.user.id, fullName)
        refreshQuietly()
        onMessage("Zugriff auf $appName für ${user.user.username} entzogen")
    }

    fun refund(purchase: AdminPurchase) = run(showLoading = true) {
        api().refund(purchase.id)
        _state.update { it.copy(purchases = api().adminPurchases()) }
        onMessage("${purchase.price} an ${purchase.username} erstattet")
    }

    fun announce(subject: String, message: String) = run(showLoading = true) {
        val n = api().announce(subject.trim(), message.trim())
        onMessage("Rundmail an $n Empfänger verschickt")
    }

    private fun refreshQuietly() {
        runCatching {
            val api = api()
            val overview = api.overview()
            val apps = api.adminApps(false)
            val users = api.users()
            val pending = api.pendingReleases()
            _state.update { it.copy(overview = overview, apps = apps, users = users, pendingReleases = pending) }
        }
    }

    private fun run(showLoading: Boolean = false, block: suspend () -> Unit) {
        viewModelScope.launch {
            if (showLoading) _state.update { it.copy(loading = true) }
            try {
                withContext(Dispatchers.IO) { block() }
            } catch (e: Exception) {
                onMessage(e.message ?: "Fehler")
            } finally {
                _state.update { it.copy(loading = false) }
            }
        }
    }
}
