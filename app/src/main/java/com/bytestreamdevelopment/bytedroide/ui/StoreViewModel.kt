package com.bytestreamdevelopment.bytedroide.ui

import android.app.Application
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.bytestreamdevelopment.bytedroide.data.AppEntry
import com.bytestreamdevelopment.bytedroide.data.Catalog
import com.bytestreamdevelopment.bytedroide.data.InstallState
import com.bytestreamdevelopment.bytedroide.data.Purchase
import com.bytestreamdevelopment.bytedroide.data.ReviewList
import com.bytestreamdevelopment.bytedroide.data.ThreadDetail
import com.bytestreamdevelopment.bytedroide.data.ThreadSummary
import com.bytestreamdevelopment.bytedroide.data.StoreApp
import com.bytestreamdevelopment.bytedroide.data.StoreSettings
import com.bytestreamdevelopment.bytedroide.data.UserInfo
import com.bytestreamdevelopment.bytedroide.install.ApkInstaller
import com.bytestreamdevelopment.bytedroide.install.InstallEvent
import com.bytestreamdevelopment.bytedroide.install.InstallEvents
import com.bytestreamdevelopment.bytedroide.work.UpdateCheckWorker
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject

sealed interface Task {
    /** progress = 0..1, null = unbekannt */
    data class Downloading(val progress: Float?) : Task
    data object Installing : Task
}

sealed interface Screen {
    data object Home : Screen
    data class Detail(val fullName: String) : Screen
    data object Settings : Screen
    data object Account : Screen
    data object Purchases : Screen
    data object Admin : Screen
    data object Dev : Screen
    data object DevCreate : Screen
    data class DevApp(val fullName: String) : Screen
    data class Codes(val fullName: String) : Screen
    data object Messages : Screen
    data class Thread(val id: Long) : Screen
}

enum class Tab { Discover, Updates, Installed }

data class UiState(
    val loading: Boolean = false,
    val loadedOnce: Boolean = false,
    val error: String? = null,
    val entries: List<AppEntry> = emptyList(),
    val tasks: Map<String, Task> = emptyMap(),
    /** Navigations-Stapel, letzter Eintrag = sichtbarer Bildschirm */
    val stack: List<Screen> = listOf(Screen.Home),
    val tab: Tab = Tab.Discover,
    val query: String = "",
    val category: String? = null,
    val message: String? = null,
    val needsInstallPermission: Boolean = false,
    val user: UserInfo? = null,
    /** Code-Dialog offen (optional mit vorgewählter App) */
    val redeemFor: String? = null,
    val showRedeem: Boolean = false,
    /** App, für die der Kauf-Dialog offen ist */
    val buyFor: String? = null,
    val purchases: List<Purchase> = emptyList(),
    /** Geladene Bewertungen je App */
    val reviews: Map<String, ReviewList> = emptyMap(),
    /** Adresse des ntfy-Themas (nach dem Einschalten zum Abonnieren) */
    val ntfyUrl: String = "",
    val threads: List<ThreadSummary> = emptyList(),
    val thread: ThreadDetail? = null,
    val unreadMessages: Int = 0,
    val busy: Boolean = false,
) {
    val screen: Screen get() = stack.last()
    val updates get() = entries.filter { it.state is InstallState.UpdateAvailable }
    val installed get() = entries.filter { it.state !is InstallState.NotInstalled }
    val categories get() = entries.map { it.app.category }.filter { it.isNotBlank() }.distinct().sorted()
    fun entry(fullName: String) = entries.firstOrNull { it.app.fullName.equals(fullName, ignoreCase = true) }
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
    /** Nach Rückkehr von der Bezahlseite den Katalog neu laden. */
    private var purchasePending = false

    init {
        viewModelScope.launch { InstallEvents.events.collect(::onInstallEvent) }
        refresh()
    }

    fun api() = catalog.api()

    fun refresh() {
        loadJob?.cancel()
        loadJob = viewModelScope.launch {
            _state.update { it.copy(loading = true, error = null) }
            try {
                val result = catalog.load()
                apps = result.apps
                _state.update {
                    it.copy(entries = catalog.entries(apps), user = result.user, unreadMessages = result.unreadMessages,
                        loading = false, loadedOnce = true)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                _state.update {
                    it.copy(loading = false, loadedOnce = true, error = e.message ?: e.javaClass.simpleName)
                }
            }
        }
    }

    /** Nach Rückkehr in die App (z. B. nach Deinstallation oder Kauf) Status neu bestimmen. */
    fun onResume() {
        if (purchasePending) {
            purchasePending = false
            refresh()
        } else if (apps.isNotEmpty()) {
            _state.update { it.copy(entries = catalog.entries(apps)) }
        }
    }

    // --- Navigation --------------------------------------------------------

    fun navigate(screen: Screen) = _state.update {
        if (screen == Screen.Home) it.copy(stack = listOf(Screen.Home))
        else it.copy(stack = it.stack.filterNot { s -> s == screen } + screen)
    }

    fun back(): Boolean {
        if (_state.value.stack.size <= 1) return false
        _state.update { it.copy(stack = it.stack.dropLast(1)) }
        return true
    }

    fun selectTab(tab: Tab) = _state.update { it.copy(tab = tab, stack = listOf(Screen.Home)) }
    fun setQuery(q: String) = _state.update { it.copy(query = q) }
    fun setCategory(c: String?) = _state.update { it.copy(category = c) }
    fun consumeMessage() = _state.update { it.copy(message = null) }
    fun dismissPermissionDialog() = _state.update { it.copy(needsInstallPermission = false) }
    fun toast(msg: String) = _state.update { it.copy(message = msg) }

    /** bytedroide://app/{owner}/{name} oder https://apps.nebendahl.eu/app/{owner}/{name} öffnet die Detailseite. */
    fun openDeepLink(uri: Uri) {
        val segments = when {
            uri.scheme == "bytedroide" && uri.host == "app" -> uri.pathSegments
            uri.scheme == "https" && uri.host == Uri.parse(StoreSettings.SERVER_URL).host &&
                uri.pathSegments.firstOrNull() == "app" -> uri.pathSegments.drop(1)
            else -> return
        }
        if (segments.size >= 2) navigate(Screen.Detail("${segments[0]}/${segments[1]}"))
    }

    /** Führt [block] im Hintergrund aus, zeigt [success] oder die Fehlermeldung. */
    private fun action(success: String? = null, after: () -> Unit = {}, block: () -> Unit) {
        if (_state.value.busy) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                withContext(Dispatchers.IO) { block() }
                _state.update { it.copy(busy = false) }
                success?.let(::toast)
                after()
            } catch (e: Exception) {
                _state.update { it.copy(busy = false) }
                toast(e.message ?: "Fehler")
            }
        }
    }

    private fun setUser(user: UserInfo) = _state.update { it.copy(user = user) }

    // --- Konto ---------------------------------------------------------------

    fun login(username: String, password: String) = authCall {
        api().login(username.trim(), password)
    }

    fun register(username: String, email: String, password: String, developer: Boolean, note: String) = authCall {
        api().register(username.trim(), email.trim(), password, developer, note.trim())
    }

    private fun authCall(call: () -> Pair<String, UserInfo>) {
        if (_state.value.busy) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                val (token, user) = withContext(Dispatchers.IO) { call() }
                settings.sessionToken = token
                _state.update { it.copy(user = user, busy = false) }
                toast(
                    when {
                        user.isAdmin -> "Angemeldet als ${user.username} (Admin)"
                        user.devRequested -> "Konto erstellt – deine Entwickler-Anfrage wird geprüft"
                        else -> "Angemeldet als ${user.username}"
                    },
                )
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(busy = false) }
                toast(e.message ?: "Fehler")
            }
        }
    }

    fun logout() {
        val api = api()
        viewModelScope.launch {
            withContext(Dispatchers.IO) { runCatching { api.logout() } }
            settings.sessionToken = ""
            _state.update { it.copy(user = null, stack = listOf(Screen.Home), purchases = emptyList()) }
            toast("Abgemeldet")
            refresh()
        }
    }

    fun forgotPassword(login: String) =
        action("Falls ein Konto existiert, ist eine E-Mail zum Zurücksetzen unterwegs.") { api().forgotPassword(login.trim()) }

    fun setNotifications(updates: Boolean? = null, news: Boolean? = null) = action {
        val changes = JSONObject()
        updates?.let { changes.put("notify_updates", it) }
        news?.let { changes.put("notify_news", it) }
        val user = api().updateMe(changes)
        setUser(user)
    }

    fun changeEmail(email: String) = action("Bestätigungs-E-Mail an ${email.trim()} gesendet") {
        setUser(api().updateMe(JSONObject().put("email", email.trim())))
    }

    fun resendVerification() = action("Bestätigungs-E-Mail gesendet") { api().resendVerification() }

    fun changePassword(old: String, new: String) = action("Passwort geändert") { api().changePassword(old, new) }

    fun requestDeveloper(note: String) = action("Anfrage gesendet – du bekommst eine E-Mail, sobald du freigeschaltet bist") {
        setUser(api().requestDeveloper(note.trim()))
    }

    fun deleteAccount(password: String) = action("Konto gelöscht", after = {
        settings.sessionToken = ""
        _state.update { it.copy(user = null, stack = listOf(Screen.Home)) }
        refresh()
    }) { api().deleteAccount(password) }

    /** Exportiert die eigenen Daten (DSGVO) und bietet sie zum Teilen/Speichern an. */
    fun exportData() = action {
        val json = api().exportData()
        val send = Intent(Intent.ACTION_SEND)
            .setType("application/json")
            .putExtra(Intent.EXTRA_SUBJECT, "Meine ByteDroide-Daten")
            .putExtra(Intent.EXTRA_TEXT, json)
        context.startActivity(Intent.createChooser(send, "Daten speichern oder teilen").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    fun loadPurchases() = viewModelScope.launch {
        runCatching { withContext(Dispatchers.IO) { api().purchases() } }
            .onSuccess { list -> _state.update { it.copy(purchases = list) } }
            .onFailure { toast(it.message ?: "Fehler") }
    }

    fun withdraw(purchase: Purchase) = action("Widerruf eingegangen – die Bestätigung kommt per E-Mail",
        after = { loadPurchases(); refresh() }) { api().withdraw(purchase.id) }

    // --- Bewertungen ----------------------------------------------------------

    fun loadReviews(fullName: String) = viewModelScope.launch {
        runCatching { withContext(Dispatchers.IO) { api().reviews(fullName) } }
            .onSuccess { list -> _state.update { it.copy(reviews = it.reviews + (fullName to list)) } }
    }

    private fun reviewAction(fullName: String, success: String, call: () -> ReviewList) = action(success, after = {
        refresh()
    }) {
        val list = call()
        _state.update { it.copy(reviews = it.reviews + (fullName to list)) }
    }

    fun setReview(fullName: String, rating: Int, text: String) =
        reviewAction(fullName, "Danke für deine Bewertung!") { api().setReview(fullName, rating, text.trim()) }

    fun deleteReview(fullName: String) =
        reviewAction(fullName, "Bewertung gelöscht") { api().deleteReview(fullName) }

    fun replyReview(fullName: String, userId: Long, text: String) =
        reviewAction(fullName, "Antwort gespeichert") { api().replyReview(fullName, userId, text.trim()) }

    fun adminDeleteReview(fullName: String, userId: Long) = action("Bewertung entfernt", after = {
        loadReviews(fullName)
        refresh()
    }) { api().adminDeleteReview(fullName, userId) }

    // --- Nachrichten an Entwickler ---------------------------------------------------

    fun loadThreads() = viewModelScope.launch {
        runCatching { withContext(Dispatchers.IO) { api().threads() } }
            .onSuccess { (list, unread) -> _state.update { it.copy(threads = list, unreadMessages = unread) } }
            .onFailure { toast(it.message ?: "Fehler") }
    }

    fun openThread(id: Long) = viewModelScope.launch {
        if (_state.value.thread?.id != id) _state.update { it.copy(thread = null) }
        runCatching { withContext(Dispatchers.IO) { api().thread(id) to api().threads() } }
            .onSuccess { (t, list) ->
                _state.update { it.copy(thread = t, threads = list.first, unreadMessages = list.second) }
            }
            .onFailure { toast(it.message ?: "Fehler") }
    }

    fun sendMessage(id: Long, text: String) = action {
        val t = api().postMessage(id, text.trim())
        _state.update { it.copy(thread = t) }
    }

    fun setThreadStatus(id: Long, closed: Boolean) = action(if (closed) "Als erledigt markiert" else "Wieder geöffnet") {
        val t = api().setThreadStatus(id, if (closed) "closed" else "open")
        _state.update { it.copy(thread = t) }
    }

    /** Neues Gespräch mit dem Entwickler; bei Fehlermeldungen mit Geräteangaben. */
    fun contactDeveloper(entry: AppEntry, kind: String, subject: String, message: String, withDevice: Boolean) {
        if (!requireLogin("Zum Schreiben bitte anmelden")) return
        val device = if (withDevice) deviceInfo(entry) else ""
        action("Gesendet – der Entwickler bekommt eine Benachrichtigung") {
            val t = api().createThread(entry.app.fullName, kind, subject.trim(), message.trim(), device)
            _state.update { it.copy(thread = t) }
            viewModelScope.launch { navigate(Screen.Thread(t.id)) }
        }
    }

    fun deviceInfo(entry: AppEntry): String {
        val installed = when (val s = entry.state) {
            is InstallState.UpToDate -> s.installedVersion
            is InstallState.UpdateAvailable -> s.installedVersion
            InstallState.NotInstalled -> "nicht installiert"
        }
        return "${android.os.Build.MANUFACTURER} ${android.os.Build.MODEL} · Android ${android.os.Build.VERSION.RELEASE} " +
            "(API ${android.os.Build.VERSION.SDK_INT}) · App-Version $installed · " +
            "ByteDroide ${com.bytestreamdevelopment.bytedroide.BuildConfig.VERSION_NAME}"
    }

    // --- Push über ntfy -------------------------------------------------------

    fun setNtfy(enable: Boolean) = action(if (enable) "Push eingeschaltet – jetzt in ntfy abonnieren" else "Push ausgeschaltet") {
        val (user, url) = api().setNtfy(enable)
        _state.update { it.copy(user = user, ntfyUrl = url) }
    }

    fun testNtfy() = action("Test-Nachricht gesendet") { api().testNtfy() }

    /** Öffnet das Thema – die ntfy-App fängt den Link ab, sonst die ntfy-Webseite zum Abonnieren. */
    fun openNtfy(topic: String) {
        val known = _state.value.ntfyUrl
        if (known.isNotBlank()) return openUrl(known)
        viewModelScope.launch {
            val base = runCatching { withContext(Dispatchers.IO) { api().info().optString("ntfy_url") } }
                .getOrNull()?.ifBlank { null } ?: "https://ntfy.sh"
            openUrl("$base/$topic")
        }
    }

    // --- Codes, Beta, Kauf ---------------------------------------------------

    private fun requireLogin(reason: String): Boolean {
        if (_state.value.user != null) return true
        toast(reason)
        navigate(Screen.Account)
        return false
    }

    fun requestRedeem(fullName: String? = null) {
        if (!requireLogin("Zum Einlösen eines Codes bitte zuerst anmelden oder registrieren")) return
        _state.update { it.copy(showRedeem = true, redeemFor = fullName) }
    }

    fun dismissRedeem() = _state.update { it.copy(showRedeem = false, redeemFor = null) }

    fun redeem(code: String) {
        if (_state.value.busy) return
        viewModelScope.launch {
            _state.update { it.copy(busy = true) }
            try {
                val name = withContext(Dispatchers.IO) { api().redeem(code.trim()) }
                _state.update { it.copy(busy = false, showRedeem = false, redeemFor = null) }
                toast("$name ist jetzt freigeschaltet 🎉")
                refresh()
            } catch (e: Exception) {
                _state.update { it.copy(busy = false) }
                toast(e.message ?: "Fehler")
            }
        }
    }

    fun setBeta(app: StoreApp, join: Boolean) {
        if (!requireLogin("Für Beta-Versionen bitte anmelden")) return
        action(if (join) "Du bist jetzt Beta-Tester von ${app.name}" else "Beta von ${app.name} verlassen",
            after = ::refresh) { api().setBeta(app.fullName, join) }
    }

    fun requestBuy(app: StoreApp) {
        if (!requireLogin("Zum Kaufen bitte anmelden oder registrieren")) return
        if (!app.canBuy) {
            toast("Kauf ist noch nicht eingerichtet – frag den Entwickler nach einem Freischalt-Code")
            requestRedeem(app.fullName)
            return
        }
        _state.update { it.copy(buyFor = app.fullName) }
    }

    fun dismissBuy() = _state.update { it.copy(buyFor = null) }

    fun buy(app: StoreApp) = action(after = {}) {
        val url = api().purchase(app.fullName)
        _state.update { it.copy(buyFor = null) }
        purchasePending = true
        openUrl(url)
    }

    // --- Installation --------------------------------------------------------

    fun install(app: StoreApp) {
        if (_state.value.tasks.containsKey(app.fullName)) return
        if (!app.unlocked) {
            if (app.isPaid) requestBuy(app) else requestRedeem(app.fullName)
            return
        }
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

    fun updateAll() = _state.value.updates.filter { it.app.unlocked }.forEach { install(it.app) }

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
        if (url.isBlank()) return
        runCatching {
            context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }.onFailure { toast("Kein Browser gefunden") }
    }

    fun openLegal(page: String) = openUrl("${StoreSettings.SERVER_URL}/$page")

    fun openInstallPermissionSettings() {
        dismissPermissionDialog()
        val intent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        context.startActivity(intent)
    }

    fun setUpdateCheck(enabled: Boolean) {
        settings.updateCheckEnabled = enabled
        UpdateCheckWorker.schedule(context, enabled)
    }

    private fun onInstallEvent(event: InstallEvent) {
        val name = apps.firstOrNull { it.fullName == event.fullName }?.name ?: event.fullName
        when (event) {
            is InstallEvent.WaitingForUser -> Unit
            is InstallEvent.Success -> {
                setTask(event.fullName, null)
                onResume()
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
