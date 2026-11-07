package com.bytestreamdevelopment.applauncher.install

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageInstaller
import android.os.Build
import com.bytestreamdevelopment.applauncher.data.ApiException
import com.bytestreamdevelopment.applauncher.data.ForgejoApi
import com.bytestreamdevelopment.applauncher.data.StoreApp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import java.io.File
import kotlin.coroutines.coroutineContext

object ApkInstaller {

    /** Lädt die APK herunter. [onProgress] erhält 0..1 oder null (Größe unbekannt). */
    suspend fun download(
        context: Context,
        api: ForgejoApi,
        app: StoreApp,
        onProgress: (Float?) -> Unit,
    ): File = withContext(Dispatchers.IO) {
        val dir = File(context.cacheDir, "apks").apply { mkdirs() }
        // Alte Downloads aufräumen
        dir.listFiles()?.forEach { it.delete() }
        val file = File(dir, app.fullName.replace('/', '_') + ".apk")

        val conn = api.openConnection(app.release.apk.downloadUrl)
        try {
            val code = conn.responseCode
            if (code !in 200..299) throw ApiException(code, "Download fehlgeschlagen ($code)")
            val total = conn.contentLengthLong.takeIf { it > 0 } ?: app.release.apk.size.takeIf { it > 0 }
            conn.inputStream.use { input ->
                file.outputStream().use { output ->
                    val buffer = ByteArray(64 * 1024)
                    var done = 0L
                    var lastReported = -1
                    while (true) {
                        coroutineContext.ensureActive()
                        val read = input.read(buffer)
                        if (read < 0) break
                        output.write(buffer, 0, read)
                        done += read
                        if (total != null) {
                            val percent = (done * 100 / total).toInt()
                            if (percent != lastReported) {
                                lastReported = percent
                                onProgress((done.toFloat() / total).coerceIn(0f, 1f))
                            }
                        } else {
                            onProgress(null)
                        }
                    }
                }
            }
        } catch (e: Throwable) {
            file.delete()
            throw e
        } finally {
            conn.disconnect()
        }
        file
    }

    /** Liest Paketname und Version aus der heruntergeladenen APK. */
    fun inspect(context: Context, file: File): PackageInfo? =
        context.packageManager.getPackageArchiveInfo(file.path, 0)

    /** Übergibt die APK an den System-Installer. Ergebnis kommt über [InstallEvents]. */
    suspend fun install(context: Context, file: File, fullName: String, packageName: String) =
        withContext(Dispatchers.IO) {
            val installer = context.packageManager.packageInstaller
            val params = PackageInstaller.SessionParams(PackageInstaller.SessionParams.MODE_FULL_INSTALL).apply {
                setAppPackageName(packageName)
                setSize(file.length())
                if (Build.VERSION.SDK_INT >= 31) {
                    // Updates von Apps, die dieser Store installiert hat, laufen ohne Rückfrage.
                    setRequireUserAction(PackageInstaller.SessionParams.USER_ACTION_NOT_REQUIRED)
                }
            }
            val sessionId = installer.createSession(params)
            try {
                installer.openSession(sessionId).use { session ->
                    file.inputStream().use { input ->
                        session.openWrite("base.apk", 0, file.length()).use { output ->
                            input.copyTo(output)
                            session.fsync(output)
                        }
                    }
                    val intent = Intent(context, InstallResultReceiver::class.java)
                        .putExtra(InstallResultReceiver.EXTRA_FULL_NAME, fullName)
                    val flags = PendingIntent.FLAG_UPDATE_CURRENT or
                        (if (Build.VERSION.SDK_INT >= 31) PendingIntent.FLAG_MUTABLE else 0)
                    val pending = PendingIntent.getBroadcast(context, sessionId, intent, flags)
                    session.commit(pending.intentSender)
                }
            } catch (e: Throwable) {
                runCatching { installer.abandonSession(sessionId) }
                throw e
            }
        }
}
