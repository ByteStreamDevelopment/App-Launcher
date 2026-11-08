package com.bytestreamdevelopment.bytedroide.data

/** Freigabe einer App. */
enum class Access(val apiValue: String, val label: String) {
    Open("open", "Offen"),
    Code("code", "Mit Code"),
    Hidden("hidden", "Versteckt");

    companion object {
        fun of(value: String) = entries.firstOrNull { it.apiValue == value } ?: Open
    }
}

/** Rolle eines Kontos. */
enum class Role(val apiValue: String, val label: String) {
    User("user", "Benutzer"),
    Developer("developer", "Entwickler"),
    Admin("admin", "Admin");

    companion object {
        fun of(value: String) = entries.firstOrNull { it.apiValue == value } ?: User
    }
}

/** Beta-Programm einer App. */
enum class BetaMode(val apiValue: String, val label: String) {
    Off("off", "Aus"),
    Open("open", "Offen"),
    Closed("closed", "Nur Eingeladene");

    companion object {
        fun of(value: String) = entries.firstOrNull { it.apiValue == value } ?: Off
    }
}

data class BetaInfo(
    val mode: BetaMode,
    /** Gibt es gerade eine Beta-Version, der man beitreten kann? */
    val available: Boolean,
    val joined: Boolean,
    val version: String,
)

/** Eine App aus dem Katalog. */
data class StoreApp(
    /** "owner/name" – eindeutiger Schlüssel. */
    val fullName: String,
    val owner: String,
    val developer: String?,
    val name: String,
    val description: String,
    val category: String,
    val homepage: String,
    val htmlUrl: String,
    val avatarUrl: String?,
    val release: Release,
    val access: Access,
    val priceCents: Int,
    /** Formatierter Preis, z. B. "1,99 €" (leer = kostenlos). */
    val price: String,
    /** Kann man die App direkt kaufen (Zahlungsanbieter eingerichtet)? */
    val canBuy: Boolean,
    /** Darf der aktuelle Benutzer die App laden? (offen, freigeschaltet, gekauft, eigene App oder Admin) */
    val unlocked: Boolean,
    val beta: BetaInfo,
    val review: String,
    val canManage: Boolean,
    /** Paketname laut Server (nur bei hochgeladenen Apps bekannt). */
    val packageName: String? = null,
    val ratingAverage: Double = 0.0,
    val ratingCount: Int = 0,
    val screenshots: List<String> = emptyList(),
) {
    val isPaid get() = priceCents > 0
    val isBetaRelease get() = release.channel == "beta"
}

data class Release(
    val tag: String,
    val name: String,
    val notes: String,
    val publishedAt: String,
    val htmlUrl: String,
    val channel: String,
    val apk: ApkAsset,
)

data class ApkAsset(
    val name: String,
    val size: Long,
)

data class UserInfo(
    val id: Long,
    val username: String,
    val email: String,
    val emailVerified: Boolean,
    val role: Role,
    val devRequested: Boolean,
    val notifyUpdates: Boolean,
    val notifyNews: Boolean,
    /** ntfy-Thema für Push-Benachrichtigungen (leer = aus) */
    val ntfyTopic: String = "",
) {
    val isAdmin get() = role == Role.Admin
    val isDeveloper get() = role == Role.Developer || role == Role.Admin
}

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

data class Purchase(
    val id: Long,
    val app: String,
    val appName: String,
    val price: String,
    val status: String,
    val createdAt: Long,
    val withdrawnAt: Long?,
    val canWithdraw: Boolean,
) {
    val statusLabel
        get() = when (status) {
            "paid" -> "Bezahlt"
            "withdrawal_requested" -> "Widerrufen – wird bearbeitet"
            "refunded" -> "Erstattet"
            else -> status
        }
}

// --- Entwickler --------------------------------------------------------------

/** App aus Sicht ihres Entwicklers (oder eines Admins). */
data class DevApp(
    val fullName: String,
    val name: String,
    val description: String,
    val category: String,
    val homepage: String,
    val developer: String?,
    /** upload | github | forgejo | forgejo_auto */
    val sourceType: String,
    val sourceUrl: String,
    val hasSourceToken: Boolean,
    val packageName: String?,
    val access: Access,
    val priceCents: Int,
    val beta: BetaMode,
    val review: String,
    val reviewNote: String,
    val avatarUrl: String?,
    val stable: String?,
    val betaVersion: String?,
    val sourceError: String?,
    val downloads: Int,
    val downloads30d: Int,
    val sales: Int,
    val revenueCents: Long,
    val codesOpen: Int,
    val codesUsed: Int,
    val testers: Int,
    val unlockedUsers: Int,
    val screenshots: List<Screenshot> = emptyList(),
    /** Versionen, die auf Admin-Prüfung warten */
    val pendingVersions: List<String> = emptyList(),
    /** Abgelehnte oder vom Virenscan gesperrte Versionen */
    val blockedVersions: List<String> = emptyList(),
    val ratingAverage: Double = 0.0,
    val ratingCount: Int = 0,
    val reviewReleases: Boolean = false,
) {
    val isUpload get() = sourceType == "upload"
    val reviewLabel
        get() = when (review) {
            "approved" -> "Veröffentlicht"
            "rejected" -> "Abgelehnt"
            else -> "In Prüfung"
        }
}

data class DevRelease(
    val id: Long,
    val version: String,
    val versionCode: Long?,
    val notes: String,
    val channel: String,
    val size: Long,
    val createdAt: Long,
    /** approved | pending | rejected */
    val status: String = "approved",
    /** Prozent der Nutzer, die diese Version bekommen */
    val rollout: Int = 100,
    /** clean | unscanned | "" */
    val scan: String = "",
    val reviewNote: String = "",
)

data class Screenshot(val id: Long, val url: String)

/** Gespräch zwischen Nutzer und Entwickler (Übersicht). */
data class ThreadSummary(
    val id: Long,
    val app: String,
    val appName: String,
    val kind: String,
    val kindLabel: String,
    val subject: String,
    val status: String,
    /** "user" = ich habe geschrieben, "dev" = ich betreue die App */
    val role: String,
    val with: String,
    val updatedAt: Long,
    val unread: Boolean,
    val preview: String,
)

data class ChatMessage(
    val id: Long,
    val author: String,
    val fromDev: Boolean,
    val mine: Boolean,
    val body: String,
    val createdAt: Long,
)

data class ThreadDetail(
    val id: Long,
    val app: String,
    val appName: String,
    val kindLabel: String,
    val subject: String,
    val status: String,
    val role: String,
    val device: String,
    val user: String,
    val developer: String,
    val createdAt: Long,
    val messages: List<ChatMessage>,
)

data class Review(
    val userId: Long,
    val username: String,
    val rating: Int,
    val text: String,
    val version: String,
    val updatedAt: Long,
    val reply: String,
    val mine: Boolean,
)

data class ReviewList(
    val average: Double,
    val count: Int,
    /** Anzahl je Sterne, Reihenfolge 5,4,3,2,1 */
    val distribution: List<Int>,
    val reviews: List<Review>,
    val canReview: Boolean,
    val canReply: Boolean,
    val mine: Review?,
)

data class PendingRelease(
    val app: String,
    val name: String,
    val developer: String?,
    val channel: String,
    val version: String,
    val notes: String,
    val releaseId: Long?,
)

data class Tester(val id: Long, val username: String, val joinedAt: Long)

data class AccessCode(
    val code: String,
    val note: String,
    val createdAt: Long,
    val usedAt: Long?,
    val usedBy: String?,
)

// --- Admin -------------------------------------------------------------------

data class AdminUser(
    val user: UserInfo,
    val createdAt: Long,
    val devNote: String,
    val apps: Int,
    /** Freigeschaltete Apps: fullName -> Name */
    val unlocked: List<Pair<String, String>>,
)

data class AdminOverview(
    val users: Int,
    val developers: Int,
    val devRequests: Int,
    val apps: Int,
    val appsPending: Int,
    val downloads30d: Int,
    val revenueCents: Long,
    val withdrawalsOpen: Int,
    val mailEnabled: Boolean,
    val paymentsEnabled: Boolean,
    val legalMissing: List<String>,
    val releasesPending: Int = 0,
    val reviewReleases: Boolean = false,
    val scannerEnabled: Boolean = false,
)

data class AdminPurchase(
    val id: Long,
    val username: String,
    val email: String,
    val appName: String,
    val price: String,
    val status: String,
    val createdAt: Long,
)

fun formatCents(cents: Long): String = "%d,%02d €".format(cents / 100, cents % 100)
