package com.bytestreamdevelopment.applauncher.data

import android.content.Context
import androidx.core.content.edit
import com.bytestreamdevelopment.applauncher.BuildConfig

/** Einstellungen, Anmeldung und Zuordnung Repo -> Paketname (in SharedPreferences). */
class StoreSettings(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("store", Context.MODE_PRIVATE)

    /** Adresse des Store-Servers (nicht Forgejo selbst). */
    var serverUrl: String
        get() = prefs.getString(KEY_SERVER, null) ?: BuildConfig.DEFAULT_SERVER_URL
        set(value) = prefs.edit { putString(KEY_SERVER, normalizeUrl(value)) }

    val isServerConfigured get() = serverUrl.isNotBlank()

    var sessionToken: String
        get() = prefs.getString(KEY_SESSION, "") ?: ""
        set(value) = prefs.edit { putString(KEY_SESSION, value) }

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
        private const val KEY_SERVER = "store_server_url"
        private const val KEY_SESSION = "session_token"
        private const val KEY_UPDATE_CHECK = "update_check"
        private const val KEY_LAST_NOTIFIED = "last_notified"
        private const val PKG_PREFIX = "pkg:"

        fun normalizeUrl(value: String): String {
            val v = value.trim().trimEnd('/')
            if (v.isEmpty()) return ""
            return if (v.startsWith("http://") || v.startsWith("https://")) v else "https://$v"
        }
    }
}
