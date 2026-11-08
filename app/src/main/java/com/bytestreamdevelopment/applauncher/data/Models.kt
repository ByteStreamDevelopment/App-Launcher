package com.bytestreamdevelopment.applauncher.data

/** Freigabe einer App, vom Admin festgelegt. */
enum class Access(val apiValue: String, val label: String) {
    Open("open", "Offen"),
    Code("code", "Mit Code"),
    Hidden("hidden", "Versteckt");

    companion object {
        fun of(value: String) = entries.firstOrNull { it.apiValue == value } ?: Open
    }
}

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
    val access: Access,
    /** Darf der aktuelle Benutzer die App laden? (offen, freigeschaltet oder Admin) */
    val unlocked: Boolean,
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
)

data class UserInfo(
    val id: Long,
    val username: String,
    val isAdmin: Boolean,
    /** Haupt-Admin (ProfImpossible) – kann nicht entfernt werden. */
    val isOwner: Boolean,
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

// --- Admin ---------------------------------------------------------------

data class AdminApp(
    val fullName: String,
    val name: String,
    val owner: String,
    val access: Access,
    val isPrivate: Boolean,
    val codesOpen: Int,
    val codesUsed: Int,
    val unlockedUsers: Int,
    val version: String,
)

data class AccessCode(
    val code: String,
    val note: String,
    val createdAt: Long,
    val usedAt: Long?,
    val usedBy: String?,
)

data class AdminUser(
    val user: UserInfo,
    val createdAt: Long,
    /** Per Code freigeschaltete Apps: fullName -> Name */
    val unlocked: List<Pair<String, String>>,
)
