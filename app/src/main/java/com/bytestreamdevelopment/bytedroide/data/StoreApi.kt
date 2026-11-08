package com.bytestreamdevelopment.applauncher.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class ApiException(val code: Int, message: String) : IOException(message)

/** Client für den eigenen Store-Server (siehe server/store_server.py). */
class StoreApi(baseUrl: String, private val token: String?) {
    private val base = baseUrl.trimEnd('/')

    // --- Katalog & Konto ---------------------------------------------------

    /** Apps + angemeldeter Benutzer (null = nicht angemeldet / Sitzung abgelaufen). */
    fun apps(): Pair<List<JSONObject>, UserInfo?> {
        val body = request("GET", "/api/apps")
        return body.getJSONArray("apps").objects() to body.optJSONObject("user")?.let(::parseUser)
    }

    fun login(username: String, password: String): Pair<String, UserInfo> =
        session(request("POST", "/api/login", JSONObject().put("username", username).put("password", password)))

    fun register(username: String, password: String, adminPassword: String): Pair<String, UserInfo> {
        val body = JSONObject().put("username", username).put("password", password)
        if (adminPassword.isNotBlank()) body.put("admin_password", adminPassword)
        return session(request("POST", "/api/register", body))
    }

    fun logout() {
        request("POST", "/api/logout", JSONObject())
    }

    /** Löst einen Einmal-Code ein, liefert den Namen der freigeschalteten App. */
    fun redeem(code: String): String =
        request("POST", "/api/redeem", JSONObject().put("code", code)).optString("name")

    fun openDownload(fullName: String, asset: String): HttpURLConnection =
        open("GET", "${base}/api/apps/${appPath(fullName)}/download?asset=${enc(asset)}")

    // --- Admin -------------------------------------------------------------

    fun adminApps(refresh: Boolean): List<AdminApp> =
        request("GET", "/api/admin/apps" + if (refresh) "?refresh=1" else "").getJSONArray("apps").objects().map {
            AdminApp(
                fullName = it.getString("id"),
                name = it.optString("name"),
                owner = it.optString("owner"),
                access = Access.of(it.optString("access")),
                isPrivate = it.optBoolean("private"),
                codesOpen = it.optInt("codes_open"),
                codesUsed = it.optInt("codes_used"),
                unlockedUsers = it.optInt("unlocked_users"),
                version = it.optJSONObject("release")?.optString("tag").orEmpty(),
            )
        }

    fun setAccess(fullName: String, access: Access) {
        request("PUT", "/api/admin/apps/${appPath(fullName)}", JSONObject().put("access", access.apiValue))
    }

    fun codes(fullName: String): List<AccessCode> =
        request("GET", "/api/admin/apps/${appPath(fullName)}/codes").getJSONArray("codes").objects().map {
            AccessCode(
                code = it.getString("code"),
                note = it.optString("note"),
                createdAt = it.optLong("created_at"),
                usedAt = if (it.isNull("used_at")) null else it.optLong("used_at"),
                usedBy = if (it.isNull("used_by")) null else it.optString("used_by"),
            )
        }

    fun createCodes(fullName: String, count: Int, note: String): List<String> {
        val body = JSONObject().put("count", count).put("note", note)
        val arr = request("POST", "/api/admin/apps/${appPath(fullName)}/codes", body).getJSONArray("codes")
        return (0 until arr.length()).map { arr.getString(it) }
    }

    fun deleteCode(code: String) {
        request("DELETE", "/api/admin/codes/${enc(code)}")
    }

    fun users(): List<AdminUser> = request("GET", "/api/admin/users").getJSONArray("users").objects().map { u ->
        AdminUser(
            user = parseUser(u),
            createdAt = u.optLong("created_at"),
            unlocked = (u.optJSONArray("unlocked") ?: JSONArray()).objects().map { it.getString("id") to it.optString("name") },
        )
    }

    fun setAdmin(userId: Long, admin: Boolean) {
        request("PUT", "/api/admin/users/$userId", JSONObject().put("is_admin", admin))
    }

    fun deleteUser(userId: Long) {
        request("DELETE", "/api/admin/users/$userId")
    }

    fun revokeUnlock(userId: Long, fullName: String) {
        request("DELETE", "/api/admin/users/$userId/unlocks/${appPath(fullName)}")
    }

    // --- Intern ------------------------------------------------------------

    private fun session(body: JSONObject) = body.getString("token") to parseUser(body.getJSONObject("user"))

    private fun request(method: String, path: String, body: JSONObject? = null): JSONObject {
        val conn = open(method, base + path)
        try {
            if (body != null) {
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                conn.outputStream.use { it.write(body.toString().toByteArray()) }
            }
            val code = conn.responseCode
            val stream = if (code in 200..299) conn.inputStream else conn.errorStream
            val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) {
                val msg = runCatching { JSONObject(text).optString("error") }.getOrNull()
                throw ApiException(code, msg?.ifBlank { null } ?: "Serverfehler ($code)")
            }
            return if (text.isBlank()) JSONObject() else JSONObject(text)
        } finally {
            conn.disconnect()
        }
    }

    private fun open(method: String, url: String): HttpURLConnection {
        if (base.isBlank()) throw ApiException(0, "Keine Server-Adresse eingestellt")
        val conn = URL(url).openConnection() as HttpURLConnection
        conn.requestMethod = method
        conn.connectTimeout = 15_000
        conn.readTimeout = 60_000
        conn.setRequestProperty("Accept", "application/json")
        conn.setRequestProperty("User-Agent", "ByteDroide")
        if (!token.isNullOrBlank()) conn.setRequestProperty("Authorization", "Bearer $token")
        return conn
    }

    private fun appPath(fullName: String) = fullName.split('/', limit = 2).joinToString("/") { enc(it) }

    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8").replace("+", "%20")

    companion object {
        fun parseUser(o: JSONObject) = UserInfo(
            id = o.optLong("id"),
            username = o.optString("username"),
            isAdmin = o.optBoolean("is_admin"),
            isOwner = o.optBoolean("is_owner"),
        )
    }
}

private fun JSONArray.objects(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }
