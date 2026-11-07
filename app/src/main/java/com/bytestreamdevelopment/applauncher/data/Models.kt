package com.bytestreamdevelopment.applauncher.data

/** Eine App aus dem Katalog = ein Forgejo-Repo, dessen neuestes Release eine APK enthält. */
data class StoreApp(
    /** "owner/repo" – eindeutiger Schlüssel. */
    val fullName: String,
    val owner: String,
    val name: String,
    val description: String,
    val htmlUrl: String,
    val avatarUrl: String?,
    val release: Release,
)

data class Release(
    val tag: String,
    val name: String,
    val notes: String,
    val publishedAt: String,
    val htmlUrl: String,
    val apk: ApkAsset,
)

data class ApkAsset(
    val name: String,
    val size: Long,
    val downloadUrl: String,
)

sealed interface InstallState {
    data object NotInstalled : InstallState
    data class UpToDate(val installedVersion: String) : InstallState
    data class UpdateAvailable(val installedVersion: String, val latestVersion: String) : InstallState
}

/** App + aktueller Installationsstatus auf diesem Gerät. */
data class AppEntry(
    val app: StoreApp,
    val state: InstallState,
    /** Paketname, falls bekannt (wird beim ersten Download aus der APK gelesen). */
    val packageName: String?,
)
