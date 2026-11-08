package com.bytestreamdevelopment.bytedroide.data

import android.content.Context
import androidx.core.content.edit

/** Einstellungen, Anmeldung und Zuordnung Repo -> Paketname (in SharedPreferences). */
class StoreSettings(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("store", Context.MODE_PRIVATE)

    /** Fester ByteDroide-Server. */
    val serverUrl: String get() = SERVER_URL

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

    /** Zufällige, stabile Kennung dieser Installation (für gestaffelte Rollouts, ohne Personenbezug). */
    val installId: String
        get() = prefs.getString(KEY_INSTALL_ID, null) ?: java.util.UUID.randomUUID().toString().also {
            prefs.edit { putString(KEY_INSTALL_ID, it) }
        }

    fun packageFor(fullName: String): String? = prefs.getString(PKG_PREFIX + fullName, null)

    fun rememberPackage(fullName: String, packageName: String) =
        prefs.edit { putString(PKG_PREFIX + fullName, packageName) }

    companion object {
        const val SERVER_URL = "https://apps.nebendahl.eu"
        private const val KEY_SESSION = "session_token"
        private const val KEY_UPDATE_CHECK = "update_check"
        private const val KEY_LAST_NOTIFIED = "last_notified"
        private const val PKG_PREFIX = "pkg:"
        private const val KEY_INSTALL_ID = "install_id"
    }
}
