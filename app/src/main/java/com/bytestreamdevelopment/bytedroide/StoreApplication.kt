package com.bytestreamdevelopment.bytedroide

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import com.bytestreamdevelopment.bytedroide.data.StoreSettings
import com.bytestreamdevelopment.bytedroide.work.UpdateCheckWorker

class StoreApplication : Application() {
    override fun onCreate() {
        super.onCreate()
        val channel = NotificationChannel(
            UpdateCheckWorker.CHANNEL_ID,
            getString(R.string.channel_updates),
            NotificationManager.IMPORTANCE_DEFAULT,
        )
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        UpdateCheckWorker.schedule(this, StoreSettings(this).updateCheckEnabled)
    }
}
