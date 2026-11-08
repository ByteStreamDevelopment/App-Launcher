package com.bytestreamdevelopment.bytedroide.data

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

data class CatalogResult(val apps: List<StoreApp>, val user: UserInfo?)

/** Lädt den App-Katalog vom Store-Server und ermittelt den Installationsstatus. */
class Catalog(private val context: Context, private val settings: StoreSettings) {

    fun api() = StoreApi(settings.serverUrl, settings.sessionToken.ifBlank { null })

    suspend fun load(): CatalogResult = withContext(Dispatchers.IO) {
        val (raw, user) = api().apps()
        // Token vorhanden, aber Server kennt ihn nicht mehr -> Sitzung abgelaufen
        if (user == null && settings.sessionToken.isNotBlank()) settings.sessionToken = ""
        CatalogResult(raw.mapNotNull { parseApp(it, Build.SUPPORTED_ABIS) }, user)
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

    companion object {
        /** Wandelt einen App-Eintrag aus /api/apps um (null = keine passende APK). */
        fun parseApp(o: JSONObject, abis: Array<String>): StoreApp? {
            val apk = pickApk(o.optJSONArray("apks") ?: JSONArray(), abis) ?: return null
            val rel = o.optJSONObject("release") ?: JSONObject()
            val beta = o.optJSONObject("beta") ?: JSONObject()
            return StoreApp(
                fullName = o.getString("id"),
                owner = o.optString("owner"),
                developer = if (o.isNull("developer")) null else o.optString("developer").ifBlank { null },
                name = o.optString("name"),
                description = o.optString("description"),
                category = o.optString("category"),
                homepage = o.optString("homepage"),
                htmlUrl = o.optString("html_url"),
                avatarUrl = if (o.isNull("avatar_url")) null else o.optString("avatar_url").ifBlank { null },
                release = Release(
                    tag = rel.optString("tag"),
                    name = rel.optString("name").ifBlank { rel.optString("tag") },
                    notes = rel.optString("notes"),
                    publishedAt = rel.optString("published_at"),
                    htmlUrl = rel.optString("html_url"),
                    channel = rel.optString("channel", "stable"),
                    apk = apk,
                ),
                access = Access.of(o.optString("access")),
                priceCents = o.optInt("price_cents"),
                price = o.optString("price"),
                canBuy = o.optBoolean("can_buy"),
                unlocked = o.optBoolean("unlocked", true),
                beta = BetaInfo(
                    mode = BetaMode.of(beta.optString("mode")),
                    available = beta.optBoolean("available"),
                    joined = beta.optBoolean("joined"),
                    version = beta.optString("version"),
                ),
                review = o.optString("review", "approved"),
                canManage = o.optBoolean("can_manage"),
            )
        }

        /** Bevorzugt "universal"-APKs, dann passende ABI, sonst die erste APK. */
        private fun pickApk(assets: JSONArray, abis: Array<String>): ApkAsset? {
            val apks = (0 until assets.length())
                .map { assets.getJSONObject(it) }
                .map { ApkAsset(it.optString("name"), it.optLong("size")) }
            if (apks.isEmpty()) return null
            return apks.firstOrNull { "universal" in it.name.lowercase() }
                ?: abis.firstNotNullOfOrNull { abi -> apks.firstOrNull { abi in it.name } }
                ?: apks.first()
        }
    }
}
