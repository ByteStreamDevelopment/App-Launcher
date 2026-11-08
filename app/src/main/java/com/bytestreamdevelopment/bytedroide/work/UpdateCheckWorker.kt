package com.bytestreamdevelopment.applauncher.work

import android.Manifest
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.bytestreamdevelopment.applauncher.MainActivity
import com.bytestreamdevelopment.applauncher.R
import com.bytestreamdevelopment.applauncher.data.Catalog
import com.bytestreamdevelopment.applauncher.data.InstallState
import com.bytestreamdevelopment.applauncher.data.StoreSettings
import java.util.concurrent.TimeUnit

/** Prüft regelmäßig auf neue Releases installierter Apps und benachrichtigt. */
class UpdateCheckWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val settings = StoreSettings(applicationContext)
        if (!settings.updateCheckEnabled) return Result.success()
        return try {
            val catalog = Catalog(applicationContext, settings)
            val updates = catalog.entries(catalog.load().apps).filter { it.state is InstallState.UpdateAvailable }
            val signature = updates.joinToString(",") { "${it.app.fullName}@${it.app.release.tag}" }
            if (updates.isNotEmpty() && signature != settings.lastNotifiedUpdates) {
                notify(updates.map { it.app.name })
            }
            settings.lastNotifiedUpdates = signature
            Result.success()
        } catch (e: Exception) {
            Result.retry()
        }
    }

    private fun notify(names: List<String>) {
        val ctx = applicationContext
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return

        val intent = Intent(ctx, MainActivity::class.java)
            .putExtra(MainActivity.EXTRA_OPEN_UPDATES, true)
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP)
        val pending = PendingIntent.getActivity(
            ctx, 0, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val title = if (names.size == 1) "Update für ${names.first()} verfügbar" else "${names.size} Updates verfügbar"
        val notification = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(names.joinToString(", "))
            .setContentIntent(pending)
            .setAutoCancel(true)
            .build()
        NotificationManagerCompat.from(ctx).notify(NOTIFICATION_ID, notification)
    }

    companion object {
        const val CHANNEL_ID = "updates"
        private const val NOTIFICATION_ID = 1
        private const val WORK_NAME = "update-check"

        fun schedule(context: Context, enabled: Boolean) {
            val wm = WorkManager.getInstance(context)
            if (!enabled) {
                wm.cancelUniqueWork(WORK_NAME)
                return
            }
            val request = PeriodicWorkRequestBuilder<UpdateCheckWorker>(6, TimeUnit.HOURS)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            wm.enqueueUniquePeriodicWork(WORK_NAME, ExistingPeriodicWorkPolicy.KEEP, request)
        }
    }
}
