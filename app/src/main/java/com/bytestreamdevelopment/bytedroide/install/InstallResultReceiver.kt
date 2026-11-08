package com.bytestreamdevelopment.bytedroide.install

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build

/** Empfängt das Ergebnis einer PackageInstaller-Session. */
class InstallResultReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val fullName = intent.getStringExtra(EXTRA_FULL_NAME) ?: return
        when (val status = intent.getIntExtra(PackageInstaller.EXTRA_STATUS, PackageInstaller.STATUS_FAILURE)) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                val confirm: Intent? = if (Build.VERSION.SDK_INT >= 33) {
                    intent.getParcelableExtra(Intent.EXTRA_INTENT, Intent::class.java)
                } else {
                    @Suppress("DEPRECATION")
                    intent.getParcelableExtra(Intent.EXTRA_INTENT)
                }
                if (confirm != null) {
                    confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    try {
                        context.startActivity(confirm)
                        InstallEvents.emit(InstallEvent.WaitingForUser(fullName))
                    } catch (e: Exception) {
                        InstallEvents.emit(InstallEvent.Failure(fullName, "Bestätigungsdialog konnte nicht geöffnet werden"))
                    }
                } else {
                    InstallEvents.emit(InstallEvent.Failure(fullName, "Bestätigung nicht möglich"))
                }
            }
            PackageInstaller.STATUS_SUCCESS -> InstallEvents.emit(InstallEvent.Success(fullName))
            PackageInstaller.STATUS_FAILURE_ABORTED -> InstallEvents.emit(InstallEvent.Aborted(fullName))
            else -> {
                val detail = intent.getStringExtra(PackageInstaller.EXTRA_STATUS_MESSAGE)
                InstallEvents.emit(InstallEvent.Failure(fullName, describe(status, detail)))
            }
        }
    }

    private fun describe(status: Int, detail: String?): String {
        val base = when (status) {
            PackageInstaller.STATUS_FAILURE_CONFLICT ->
                "Konflikt mit installierter App (andere Signatur? Dann erst deinstallieren)"
            PackageInstaller.STATUS_FAILURE_INCOMPATIBLE -> "App ist mit diesem Gerät nicht kompatibel"
            PackageInstaller.STATUS_FAILURE_INVALID -> "Ungültige APK"
            PackageInstaller.STATUS_FAILURE_STORAGE -> "Nicht genug Speicherplatz"
            PackageInstaller.STATUS_FAILURE_BLOCKED -> "Installation blockiert"
            else -> "Installation fehlgeschlagen"
        }
        return if (detail.isNullOrBlank()) base else "$base: $detail"
    }

    companion object {
        const val EXTRA_FULL_NAME = "full_name"
    }
}
