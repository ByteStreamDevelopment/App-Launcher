package com.bytestreamdevelopment.applauncher.data

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withPermit
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/** Lädt den App-Katalog vom Forgejo-Server und ermittelt den Installationsstatus. */
class Catalog(private val context: Context, private val settings: StoreSettings) {

    fun api() = ForgejoApi(settings.serverUrl, settings.token.ifBlank { null })

    suspend fun load(): List<StoreApp> = withContext(Dispatchers.IO) {
        val api = api()
        val owners = settings.owners
        val repos = api.searchRepos().filter { repo ->
            val owner = repo.optJSONObject("owner")?.optString("login").orEmpty().lowercase()
            repo.optInt("release_counter", 1) > 0 &&
                !repo.optBoolean("empty") &&
                (owners.isEmpty() || owner in owners)
        }
        val limit = Semaphore(6)
        coroutineScope {
            repos.map { repo ->
                async {
                    limit.withPermit {
                        runCatching {
                            val fullName = repo.getString("full_name")
                            api.latestRelease(fullName)?.let { toStoreApp(repo, it) }
                        }.getOrNull()
                    }
                }
            }.awaitAll()
        }.filterNotNull().sortedBy { it.name.lowercase() }
    }

    fun entries(apps: List<StoreApp>): List<AppEntry> = apps.map { entry(it) }

    fun entry(app: StoreApp): AppEntry {
        val pkg = settings.packageFor(app.fullName)
        return AppEntry(app, installState(pkg, app), pkg)
    }

    private fun installState(pkg: String?, app: StoreApp): InstallState {
        if (pkg == null) return InstallState.NotInstalled
        val info = try {
            context.packageManager.getPackageInfo(pkg, 0)
        } catch (_: PackageManager.NameNotFoundException) {
            return InstallState.NotInstalled
        }
        val installed = info.versionName ?: "?"
        return if (Versions.isNewer(app.release.tag, installed)) {
            InstallState.UpdateAvailable(installed, Versions.normalize(app.release.tag))
        } else {
            InstallState.UpToDate(installed)
        }
    }

    private fun toStoreApp(repo: JSONObject, release: JSONObject): StoreApp? {
        val apk = pickApk(release.optJSONArray("assets") ?: JSONArray()) ?: return null
        val owner = repo.optJSONObject("owner")?.optString("login").orEmpty()
        return StoreApp(
            fullName = repo.getString("full_name"),
            owner = owner,
            name = repo.optString("name"),
            description = repo.optString("description"),
            htmlUrl = repo.optString("html_url"),
            avatarUrl = repo.optString("avatar_url").takeIf { it.isNotBlank() },
            release = Release(
                tag = release.optString("tag_name"),
                name = release.optString("name").ifBlank { release.optString("tag_name") },
                notes = release.optString("body"),
                publishedAt = release.optString("published_at"),
                htmlUrl = release.optString("html_url"),
                apk = apk,
            ),
        )
    }

    /** Bevorzugt "universal"-APKs, dann passende ABI, sonst die erste APK. */
    private fun pickApk(assets: JSONArray): ApkAsset? {
        val apks = (0 until assets.length())
            .map { assets.getJSONObject(it) }
            .filter { it.optString("name").endsWith(".apk", ignoreCase = true) }
            .map { ApkAsset(it.optString("name"), it.optLong("size"), it.optString("browser_download_url")) }
        if (apks.isEmpty()) return null
        return apks.firstOrNull { "universal" in it.name.lowercase() }
            ?: Build.SUPPORTED_ABIS.firstNotNullOfOrNull { abi -> apks.firstOrNull { abi in it.name } }
            ?: apks.first()
    }
}
