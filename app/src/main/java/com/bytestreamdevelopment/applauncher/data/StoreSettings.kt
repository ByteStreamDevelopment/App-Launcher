package com.bytestreamdevelopment.applauncher.data

import android.content.Context
import androidx.core.content.edit

/** Einstellungen + Zuordnung Repo -> Paketname (in SharedPreferences). */
class StoreSettings(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("store", Context.MODE_PRIVATE)

    var serverUrl: String
        get() = prefs.getString(KEY_SERVER, DEFAULT_SERVER) ?: DEFAULT_SERVER
        set(value) = prefs.edit { putString(KEY_SERVER, value.trim().trimEnd('/').ifEmpty { DEFAULT_SERVER }) }

    /** Optionaler Forgejo-Zugangstoken (für private Repos). */
    var token: String
        get() = prefs.getString(KEY_TOKEN, "") ?: ""
        set(value) = prefs.edit { putString(KEY_TOKEN, value.trim()) }

    /** Kommagetrennte Liste von Benutzern/Organisationen. Leer = alle. */
    var ownerFilter: String
        get() = prefs.getString(KEY_OWNERS, "") ?: ""
        set(value) = prefs.edit { putString(KEY_OWNERS, value.trim()) }

    val owners: Set<String>
        get() = ownerFilter.split(',', ' ', ';')
            .map { it.trim().lowercase() }
            .filter { it.isNotEmpty() }
            .toSet()

    var updateCheckEnabled: Boolean
        get() = prefs.getBoolean(KEY_UPDATE_CHECK, true)
        set(value) = prefs.edit { putBoolean(KEY_UPDATE_CHECK, value) }

    /** Merkt sich, welche Updates schon gemeldet wurden (keine Doppel-Benachrichtigungen). */
    var lastNotifiedUpdates: String
        get() = prefs.getString(KEY_LAST_NOTIFIED, "") ?: ""
        set(value) = prefs.edit { putString(KEY_LAST_NOTIFIED, value) }

    fun packageFor(fullName: String): String? = prefs.getString(PKG_PREFIX + fullName, null)

    fun rememberPackage(fullName: String, packageName: String) =
        prefs.edit { putString(PKG_PREFIX + fullName, packageName) }

    companion object {
        const val DEFAULT_SERVER = "https://git.nebendahl.eu"
        private const val KEY_SERVER = "server_url"
        private const val KEY_TOKEN = "token"
        private const val KEY_OWNERS = "owners"
        private const val KEY_UPDATE_CHECK = "update_check"
        private const val KEY_LAST_NOTIFIED = "last_notified"
        private const val PKG_PREFIX = "pkg:"
    }
}
