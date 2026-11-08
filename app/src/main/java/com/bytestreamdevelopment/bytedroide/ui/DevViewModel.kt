package com.bytestreamdevelopment.bytedroide.ui

import android.app.Application
import android.net.Uri
import android.provider.OpenableColumns
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.bytestreamdevelopment.bytedroide.data.AccessCode
import com.bytestreamdevelopment.bytedroide.data.DevApp
import com.bytestreamdevelopment.bytedroide.data.DevRelease
import com.bytestreamdevelopment.bytedroide.data.StoreApi
import com.bytestreamdevelopment.bytedroide.data.StoreSettings
import com.bytestreamdevelopment.bytedroide.data.Tester
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

data class DevState(
    val loading: Boolean = false,
    val apps: List<DevApp> = emptyList(),
    /** Gerade geöffnete App */
    val current: DevApp? = null,
    val releases: List<DevRelease> = emptyList(),
    val testers: List<Tester> = emptyList(),
    val codesFor: String? = null,
    val codes: List<AccessCode> = emptyList(),
    /** Zuletzt erzeugte Codes (zum Hervorheben) */
    val freshCodes: List<String> = emptyList(),
    /** Upload-Fortschritt 0..1, null = kein Upload */
    val upload: Float? = null,
)

/** Entwickler-Bereich: eigene Apps (Admins: alle Apps) verwalten. */
class DevViewModel(application: Application) : AndroidViewModel(application) {
    private val context get() = getApplication<Application>()
    private val settings = StoreSettings(application)
    private val _state = MutableStateFlow(DevState())
    val state: StateFlow<DevState> = _state

    var onMessage: (String) -> Unit = {}
    var onCatalogChanged: () -> Unit = {}

    private fun api() = StoreApi(settings.serverUrl, settings.sessionToken.ifBlank { null })

    fun loadApps() = run(showLoading = true) {
        val apps = api().devApps()
        _state.update { it.copy(apps = apps) }
    }

    fun open(fullName: String) {
        if (_state.value.current?.fullName != fullName) {
            _state.update { it.copy(current = null, releases = emptyList(), testers = emptyList()) }
        }
        run(showLoading = true) { reload(fullName) }
    }

    private fun reload(fullName: String) {
        val api = api()
        val app = api.devApp(fullName)
        val releases = if (app.isUpload) api.releases(fullName) else emptyList()
        val testers = if (app.beta != com.bytestreamdevelopment.bytedroide.data.BetaMode.Off) api.testers(fullName) else emptyList()
        _state.update { s ->
            s.copy(current = app, releases = releases, testers = testers,
                apps = s.apps.map { if (it.fullName == app.fullName) app else it })
        }
    }

    fun create(fields: JSONObject, onCreated: (String) -> Unit) = run(showLoading = true) {
        val app = api().createApp(fields)
        _state.update { it.copy(apps = it.apps + app, current = app, releases = emptyList(), testers = emptyList()) }
        withContext(Dispatchers.Main) { onCreated(app.fullName) }
        onMessage(if (app.review == "pending") "App angelegt – ein Admin prüft sie vor der Veröffentlichung" else "App angelegt")
    }

    fun update(fullName: String, fields: JSONObject, message: String = "Gespeichert") = run(showLoading = true) {
        api().updateApp(fullName, fields)
        reload(fullName)
        onMessage(message)
        onCatalogChanged()
    }

    /** Nur für Admins: Prüfung (approved / rejected) und andere Admin-Felder. */
    fun review(fullName: String, review: String, note: String = "") = run(showLoading = true) {
        api().adminUpdateApp(fullName, JSONObject().put("review", review).put("review_note", note))
        reload(fullName)
        onMessage(if (review == "approved") "App freigegeben" else "App abgelehnt")
        onCatalogChanged()
    }

    fun delete(fullName: String, onDone: () -> Unit) = run(showLoading = true) {
        api().deleteApp(fullName)
        _state.update { s -> s.copy(apps = s.apps.filterNot { it.fullName == fullName }, current = null) }
        withContext(Dispatchers.Main) { onDone() }
        onMessage("App gelöscht")
        onCatalogChanged()
    }

    fun uploadApk(fullName: String, uri: Uri, channel: String, notes: String) {
        if (_state.value.upload != null) return
        viewModelScope.launch {
            _state.update { it.copy(upload = 0f) }
            try {
                val version = withContext(Dispatchers.IO) {
                    val size = fileSize(uri) ?: throw IllegalStateException("Dateigröße unbekannt")
                    val input = context.contentResolver.openInputStream(uri)
                        ?: throw IllegalStateException("Datei nicht lesbar")
                    input.use { stream ->
                        api().uploadRelease(fullName, stream, size, channel, notes.trim()) { p ->
                            _state.update { it.copy(upload = p) }
                        }
                    }
                }
                onMessage("Version $version veröffentlicht")
                withContext(Dispatchers.IO) { reload(fullName) }
                onCatalogChanged()
            } catch (e: Exception) {
                onMessage(e.message ?: "Upload fehlgeschlagen")
            } finally {
                _state.update { it.copy(upload = null) }
            }
        }
    }

    fun uploadIcon(fullName: String, uri: Uri) = run(showLoading = true) {
        val size = fileSize(uri) ?: 0
        if (size > 1024 * 1024) throw IllegalStateException("Icon ist größer als 1 MB")
        val data = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
            ?: throw IllegalStateException("Datei nicht lesbar")
        api().uploadIcon(fullName, data)
        reload(fullName)
        onMessage("Icon gespeichert")
        onCatalogChanged()
    }

    fun deleteRelease(fullName: String, release: DevRelease) = run(showLoading = true) {
        api().deleteRelease(fullName, release.id)
        reload(fullName)
        onMessage("Version ${release.version} gelöscht")
        onCatalogChanged()
    }

    fun addTester(fullName: String, username: String) = run(showLoading = true) {
        api().addTester(fullName, username.trim())
        _state.update { it.copy(testers = api().testers(fullName)) }
        onMessage("${username.trim()} eingeladen")
    }

    fun removeTester(fullName: String, tester: Tester) = run {
        api().removeTester(fullName, tester.id)
        _state.update { s -> s.copy(testers = s.testers.filterNot { it.id == tester.id }) }
    }

    // --- Codes ---------------------------------------------------------------

    fun openCodes(fullName: String) {
        _state.update { it.copy(codesFor = fullName, codes = emptyList(), freshCodes = emptyList()) }
        run(showLoading = true) {
            val codes = api().codes(fullName)
            _state.update { if (it.codesFor == fullName) it.copy(codes = codes) else it }
        }
    }

    fun createCodes(fullName: String, count: Int, note: String) = run(showLoading = true) {
        val created = api().createCodes(fullName, count, note.trim())
        _state.update { it.copy(codes = api().codes(fullName), freshCodes = created) }
        onMessage(if (created.size == 1) "Code erstellt: ${created.first()}" else "${created.size} Codes erstellt")
    }

    fun deleteCode(code: String) = run {
        api().deleteCode(code)
        _state.update { s -> s.copy(codes = s.codes.filterNot { it.code == code }, freshCodes = s.freshCodes - code) }
    }

    private fun fileSize(uri: Uri): Long? =
        context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { c ->
            if (c.moveToFirst() && !c.isNull(0)) c.getLong(0) else null
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
