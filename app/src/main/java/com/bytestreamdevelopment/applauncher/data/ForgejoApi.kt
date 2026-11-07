package com.bytestreamdevelopment.applauncher.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class ApiException(val code: Int, message: String) : IOException(message)

/** Minimaler Client für die Forgejo/Gitea-API v1. */
class ForgejoApi(baseUrl: String, private val token: String?) {
    private val base = baseUrl.trimEnd('/')

    /** Alle sichtbaren Repos (mit Token auch private). */
    fun searchRepos(): List<JSONObject> {
        val result = mutableListOf<JSONObject>()
        var page = 1
        while (page <= MAX_PAGES) {
            val body = JSONObject(get("/api/v1/repos/search?limit=$PAGE_SIZE&page=$page"))
            val data = body.optJSONArray("data") ?: JSONArray()
            for (i in 0 until data.length()) result += data.getJSONObject(i)
            if (data.length() < PAGE_SIZE) break
            page++
        }
        return result
    }

    /** Neuestes veröffentlichtes Release (ohne Entwürfe/Pre-Releases) oder null. */
    fun latestRelease(fullName: String): JSONObject? {
        val (owner, repo) = fullName.split('/', limit = 2)
        return try {
            JSONObject(get("/api/v1/repos/${enc(owner)}/${enc(repo)}/releases/latest"))
        } catch (e: ApiException) {
            if (e.code == 404) null else throw e
        }
    }

    private fun get(path: String): String {
        val conn = openConnection(base + path)
        conn.setRequestProperty("Accept", "application/json")
        try {
            val code = conn.responseCode
            if (code !in 200..299) {
                val msg = when (code) {
                    401, 403 -> "Zugriff verweigert ($code) – Token prüfen"
                    404 -> "Nicht gefunden (404)"
                    else -> "Serverfehler ($code)"
                }
                throw ApiException(code, msg)
            }
            return conn.inputStream.bufferedReader().use { it.readText() }
        } finally {
            conn.disconnect()
        }
    }

    fun openConnection(url: String): HttpURLConnection {
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.connectTimeout = 15_000
        conn.readTimeout = 30_000
        conn.setRequestProperty("User-Agent", "App-Launcher-Store")
        if (!token.isNullOrBlank()) conn.setRequestProperty("Authorization", "token $token")
        return conn
    }

    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8").replace("+", "%20")

    companion object {
        private const val PAGE_SIZE = 50
        private const val MAX_PAGES = 20
    }
}
