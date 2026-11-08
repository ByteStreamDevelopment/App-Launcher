package com.bytestreamdevelopment.bytedroide.data

import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

class ApiException(val code: Int, message: String) : IOException(message)

/** Client für den eigenen Store-Server (siehe server/store_server.py). */
class StoreApi(baseUrl: String, private val token: String?, private val installId: String? = null) {
    private val base = baseUrl.trimEnd('/')

    // --- Katalog & Konto ---------------------------------------------------

    /** Apps + angemeldeter Benutzer (null = nicht angemeldet / Sitzung abgelaufen) + ungelesene Nachrichten. */
    fun apps(): Triple<List<JSONObject>, UserInfo?, Int> {
        val body = request("GET", "/api/apps")
        return Triple(body.getJSONArray("apps").objects(), body.optJSONObject("user")?.let(::parseUser),
            body.optInt("unread_messages"))
    }

    fun login(username: String, password: String): Pair<String, UserInfo> =
        session(request("POST", "/api/login", JSONObject().put("username", username).put("password", password)))

    fun register(
        username: String,
        email: String,
        password: String,
        developer: Boolean,
        developerNote: String,
    ): Pair<String, UserInfo> {
        val body = JSONObject()
            .put("username", username)
            .put("email", email)
            .put("password", password)
            .put("accept_terms", true)
            .put("developer", developer)
            .put("developer_note", developerNote)
        return session(request("POST", "/api/register", body))
    }

    fun logout() {
        request("POST", "/api/logout", JSONObject())
    }

    fun forgotPassword(login: String) {
        request("POST", "/api/password/forgot", JSONObject().put("login", login))
    }

    fun me(): UserInfo = parseUser(request("GET", "/api/me").getJSONObject("user"))

    fun updateMe(changes: JSONObject): UserInfo = parseUser(request("PUT", "/api/me", changes).getJSONObject("user"))

    fun changePassword(old: String, new: String) {
        request("POST", "/api/me/password", JSONObject().put("old_password", old).put("new_password", new))
    }

    fun resendVerification() {
        request("POST", "/api/me/verify", JSONObject())
    }

    fun requestDeveloper(note: String): UserInfo =
        parseUser(request("POST", "/api/me/developer", JSONObject().put("note", note)).getJSONObject("user"))

    fun deleteAccount(password: String) {
        request("DELETE", "/api/me", JSONObject().put("password", password))
    }

    fun exportData(): String = request("GET", "/api/me/export").toString(2)

    fun purchases(): List<Purchase> = request("GET", "/api/me/purchases").getJSONArray("purchases").objects().map {
        Purchase(
            id = it.getLong("id"),
            app = it.optString("app"),
            appName = it.optString("app_name"),
            price = it.optString("price"),
            status = it.optString("status"),
            createdAt = it.optLong("created_at"),
            withdrawnAt = if (it.isNull("withdrawn_at")) null else it.optLong("withdrawn_at"),
            canWithdraw = it.optBoolean("can_withdraw"),
        )
    }

    fun withdraw(purchaseId: Long) {
        request("POST", "/api/me/purchases/$purchaseId/withdraw", JSONObject())
    }

    /** Löst einen Einmal-Code ein, liefert den Namen der freigeschalteten App. */
    fun redeem(code: String): String =
        request("POST", "/api/redeem", JSONObject().put("code", code)).optString("name")

    fun setBeta(fullName: String, join: Boolean) {
        request(if (join) "POST" else "DELETE", "/api/apps/${appPath(fullName)}/beta", if (join) JSONObject() else null)
    }

    /** Startet den Kauf, liefert die Adresse der Bezahlseite. */
    fun purchase(fullName: String): String =
        request("POST", "/api/apps/${appPath(fullName)}/purchase", JSONObject().put("accept_waiver", true))
            .getString("checkout_url")

    // --- Bewertungen ----------------------------------------------------------

    fun reviews(fullName: String): ReviewList = parseReviews(request("GET", "/api/apps/${appPath(fullName)}/reviews"))

    fun setReview(fullName: String, rating: Int, text: String): ReviewList = parseReviews(
        request("PUT", "/api/apps/${appPath(fullName)}/reviews", JSONObject().put("rating", rating).put("text", text)),
    )

    fun deleteReview(fullName: String): ReviewList =
        parseReviews(request("DELETE", "/api/apps/${appPath(fullName)}/reviews"))

    fun replyReview(fullName: String, userId: Long, text: String): ReviewList = parseReviews(
        request("PUT", "/api/dev/apps/${appPath(fullName)}/reviews/$userId/reply", JSONObject().put("text", text)),
    )

    fun adminDeleteReview(fullName: String, userId: Long) {
        request("DELETE", "/api/admin/apps/${appPath(fullName)}/reviews/$userId")
    }

    // --- Nachrichten --------------------------------------------------------

    /** Gespräche + Anzahl ungelesener. */
    fun threads(): Pair<List<ThreadSummary>, Int> {
        val body = request("GET", "/api/threads")
        return body.getJSONArray("threads").objects().map {
            ThreadSummary(
                id = it.getLong("id"),
                app = it.optString("app"),
                appName = it.optString("app_name"),
                kind = it.optString("kind"),
                kindLabel = it.optString("kind_label"),
                subject = it.optString("subject"),
                status = it.optString("status"),
                role = it.optString("role"),
                with = it.optString("with"),
                updatedAt = it.optLong("updated_at"),
                unread = it.optBoolean("unread"),
                preview = it.optString("preview"),
            )
        } to body.optInt("unread")
    }

    fun thread(id: Long): ThreadDetail = parseThread(request("GET", "/api/threads/$id"))

    fun createThread(fullName: String, kind: String, subject: String, message: String, device: String): ThreadDetail =
        parseThread(
            request(
                "POST", "/api/apps/${appPath(fullName)}/threads",
                JSONObject().put("kind", kind).put("subject", subject).put("message", message).put("device", device),
            ),
        )

    fun postMessage(id: Long, message: String): ThreadDetail =
        parseThread(request("POST", "/api/threads/$id/messages", JSONObject().put("message", message)))

    fun setThreadStatus(id: Long, status: String): ThreadDetail =
        parseThread(request("PUT", "/api/threads/$id", JSONObject().put("status", status)))

    // --- Push über ntfy -----------------------------------------------------

    /** Schaltet ntfy-Push an/aus. Liefert Benutzer + Adresse des Themas zum Abonnieren. */
    fun setNtfy(enable: Boolean): Pair<UserInfo, String> {
        val body = request("POST", "/api/me/ntfy", JSONObject().put("enable", enable))
        return parseUser(body.getJSONObject("user")) to body.optString("ntfy_url")
    }

    fun testNtfy() {
        request("POST", "/api/me/ntfy/test", JSONObject())
    }

    fun info(): JSONObject = request("GET", "/api/info")

    fun openDownload(fullName: String, asset: String): HttpURLConnection =
        open("GET", "${base}/api/apps/${appPath(fullName)}/download?asset=${enc(asset)}")

    // --- Entwickler --------------------------------------------------------

    fun devApps(): List<DevApp> = request("GET", "/api/dev/apps").getJSONArray("apps").objects().map(::parseDevApp)

    fun devApp(fullName: String): DevApp = parseDevApp(request("GET", "/api/dev/apps/${appPath(fullName)}"))

    fun createApp(fields: JSONObject): DevApp = parseDevApp(request("POST", "/api/dev/apps", fields))

    fun updateApp(fullName: String, fields: JSONObject): DevApp =
        parseDevApp(request("PUT", "/api/dev/apps/${appPath(fullName)}", fields))

    fun deleteApp(fullName: String) {
        request("DELETE", "/api/dev/apps/${appPath(fullName)}")
    }

    fun releases(fullName: String): List<DevRelease> =
        request("GET", "/api/dev/apps/${appPath(fullName)}/releases").getJSONArray("releases").objects().map {
            DevRelease(
                id = it.getLong("id"),
                version = it.optString("version"),
                versionCode = if (it.isNull("version_code")) null else it.optLong("version_code"),
                notes = it.optString("notes"),
                channel = it.optString("channel"),
                size = it.optLong("size"),
                createdAt = it.optLong("created_at"),
                status = it.optString("status", "approved"),
                rollout = it.optInt("rollout", 100),
                scan = it.optString("scan"),
                reviewNote = it.optString("review_note"),
            )
        }

    fun setRollout(fullName: String, id: Long, rollout: Int) {
        request("PUT", "/api/dev/apps/${appPath(fullName)}/releases/$id", JSONObject().put("rollout", rollout))
    }

    fun addScreenshot(fullName: String, data: ByteArray) {
        upload("POST", "$base/api/dev/apps/${appPath(fullName)}/screenshots", data)
    }

    fun orderScreenshots(fullName: String, ids: List<Long>) {
        request("PUT", "/api/dev/apps/${appPath(fullName)}/screenshots", JSONObject().put("order", JSONArray(ids)))
    }

    fun deleteScreenshot(fullName: String, id: Long) {
        request("DELETE", "/api/dev/apps/${appPath(fullName)}/screenshots/$id")
    }

    fun deleteRelease(fullName: String, id: Long) {
        request("DELETE", "/api/dev/apps/${appPath(fullName)}/releases/$id")
    }

    /** Lädt eine APK hoch. Liefert die erkannte Version. */
    fun uploadRelease(
        fullName: String,
        input: InputStream,
        size: Long,
        channel: String,
        notes: String,
        rollout: Int = 100,
        onProgress: (Float) -> Unit,
    ): String {
        val url = "$base/api/dev/apps/${appPath(fullName)}/releases?channel=${enc(channel)}&notes=${enc(notes)}" +
            "&rollout=$rollout"
        val conn = open("POST", url)
        conn.readTimeout = 300_000
        conn.doOutput = true
        conn.setFixedLengthStreamingMode(size)
        conn.setRequestProperty("Content-Type", "application/vnd.android.package-archive")
        try {
            conn.outputStream.use { out ->
                val buffer = ByteArray(64 * 1024)
                var done = 0L
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    out.write(buffer, 0, read)
                    done += read
                    onProgress((done.toFloat() / size).coerceIn(0f, 1f))
                }
            }
            return readResponse(conn).optString("version")
        } finally {
            conn.disconnect()
        }
    }

    fun uploadIcon(fullName: String, data: ByteArray) {
        upload("POST", "$base/api/dev/apps/${appPath(fullName)}/icon", data)
    }

    private fun upload(method: String, url: String, data: ByteArray) {
        val conn = open(method, url)
        conn.doOutput = true
        conn.setFixedLengthStreamingMode(data.size)
        conn.setRequestProperty("Content-Type", "application/octet-stream")
        try {
            conn.outputStream.use { it.write(data) }
            readResponse(conn)
        } finally {
            conn.disconnect()
        }
    }

    fun codes(fullName: String): List<AccessCode> =
        request("GET", "/api/dev/apps/${appPath(fullName)}/codes").getJSONArray("codes").objects().map {
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
        val arr = request("POST", "/api/dev/apps/${appPath(fullName)}/codes", body).getJSONArray("codes")
        return (0 until arr.length()).map { arr.getString(it) }
    }

    fun deleteCode(code: String) {
        request("DELETE", "/api/dev/codes/${enc(code)}")
    }

    fun testers(fullName: String): List<Tester> =
        request("GET", "/api/dev/apps/${appPath(fullName)}/testers").getJSONArray("testers").objects().map {
            Tester(it.getLong("id"), it.optString("username"), it.optLong("joined_at"))
        }

    fun addTester(fullName: String, username: String) {
        request("POST", "/api/dev/apps/${appPath(fullName)}/testers", JSONObject().put("username", username))
    }

    fun removeTester(fullName: String, userId: Long) {
        request("DELETE", "/api/dev/apps/${appPath(fullName)}/testers/$userId")
    }

    // --- Admin -------------------------------------------------------------

    fun overview(): AdminOverview = request("GET", "/api/admin/overview").let {
        AdminOverview(
            users = it.optInt("users"),
            developers = it.optInt("developers"),
            devRequests = it.optInt("dev_requests"),
            apps = it.optInt("apps"),
            appsPending = it.optInt("apps_pending"),
            downloads30d = it.optInt("downloads_30d"),
            revenueCents = it.optLong("revenue_cents"),
            withdrawalsOpen = it.optInt("withdrawals_open"),
            mailEnabled = it.optBoolean("mail_enabled"),
            paymentsEnabled = it.optBoolean("payments_enabled"),
            legalMissing = (it.optJSONArray("legal_missing") ?: JSONArray()).let { a ->
                (0 until a.length()).map(a::getString)
            },
            releasesPending = it.optInt("releases_pending"),
            reviewReleases = it.optBoolean("review_releases"),
            scannerEnabled = it.optBoolean("scanner_enabled"),
        )
    }

    fun adminApps(refresh: Boolean): List<DevApp> =
        request("GET", "/api/admin/apps" + if (refresh) "?refresh=1" else "").getJSONArray("apps").objects()
            .map(::parseDevApp)

    fun adminUpdateApp(fullName: String, fields: JSONObject): DevApp =
        parseDevApp(request("PUT", "/api/admin/apps/${appPath(fullName)}", fields))

    fun users(): List<AdminUser> = request("GET", "/api/admin/users").getJSONArray("users").objects().map { u ->
        AdminUser(
            user = parseUser(u),
            createdAt = u.optLong("created_at"),
            devNote = u.optString("dev_note"),
            apps = u.optInt("apps"),
            unlocked = (u.optJSONArray("unlocked") ?: JSONArray()).objects()
                .map { it.getString("id") to it.optString("name") },
        )
    }

    fun setRole(userId: Long, role: Role) {
        request("PUT", "/api/admin/users/$userId", JSONObject().put("role", role.apiValue))
    }

    fun decideDeveloper(userId: Long, approve: Boolean, note: String) {
        request("POST", "/api/admin/users/$userId/developer", JSONObject().put("approve", approve).put("note", note))
    }

    fun deleteUser(userId: Long) {
        request("DELETE", "/api/admin/users/$userId")
    }

    fun revokeUnlock(userId: Long, fullName: String) {
        request("DELETE", "/api/admin/users/$userId/unlocks/${appPath(fullName)}")
    }

    fun adminPurchases(): List<AdminPurchase> =
        request("GET", "/api/admin/purchases").getJSONArray("purchases").objects().map {
            AdminPurchase(
                id = it.getLong("id"),
                username = it.optString("username"),
                email = it.optString("email"),
                appName = it.optString("app_name"),
                price = it.optString("price"),
                status = it.optString("status"),
                createdAt = it.optLong("created_at"),
            )
        }

    fun pendingReleases(): List<PendingRelease> =
        request("GET", "/api/admin/releases").getJSONArray("releases").objects().map {
            PendingRelease(
                app = it.getString("app"),
                name = it.optString("name"),
                developer = it.optStringOrNull("developer"),
                channel = it.optString("channel"),
                version = it.optString("version"),
                notes = it.optString("notes"),
                releaseId = if (it.isNull("release_id")) null else it.optLong("release_id"),
            )
        }

    fun decideRelease(release: PendingRelease, approve: Boolean, note: String) {
        val body = JSONObject().put("app", release.app).put("channel", release.channel).put("approve", approve)
            .put("note", note)
        release.releaseId?.let { body.put("release_id", it) }
        request("POST", "/api/admin/releases/decide", body)
    }

    fun refund(purchaseId: Long) {
        request("POST", "/api/admin/purchases/$purchaseId/refund", JSONObject())
    }

    /** Rundmail an alle, die Neuigkeiten abonniert haben. Liefert die Anzahl der Empfänger. */
    fun announce(subject: String, message: String): Int =
        request("POST", "/api/admin/announce", JSONObject().put("subject", subject).put("message", message))
            .optInt("recipients")

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
            return readResponse(conn)
        } finally {
            conn.disconnect()
        }
    }

    private fun readResponse(conn: HttpURLConnection): JSONObject {
        val code = conn.responseCode
        val stream = if (code in 200..299) conn.inputStream else conn.errorStream
        val text = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
        if (code !in 200..299) {
            val msg = runCatching { JSONObject(text).optString("error") }.getOrNull()
            throw ApiException(code, msg?.ifBlank { null } ?: "Serverfehler ($code)")
        }
        return if (text.isBlank()) JSONObject() else JSONObject(text)
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
        if (!installId.isNullOrBlank()) conn.setRequestProperty("X-Install-Id", installId)
        return conn
    }

    private fun appPath(fullName: String) = fullName.split('/', limit = 2).joinToString("/") { enc(it) }

    private fun enc(s: String) = URLEncoder.encode(s, "UTF-8").replace("+", "%20")

    companion object {
        fun parseUser(o: JSONObject) = UserInfo(
            id = o.optLong("id"),
            username = o.optString("username"),
            email = o.optString("email"),
            emailVerified = o.optBoolean("email_verified"),
            role = Role.of(o.optString("role", if (o.optBoolean("is_admin")) "admin" else "user")),
            devRequested = o.optBoolean("dev_requested"),
            notifyUpdates = o.optBoolean("notify_updates", true),
            notifyNews = o.optBoolean("notify_news"),
            ntfyTopic = o.optString("ntfy_topic"),
        )

        fun JSONObject.optStringOrNull(key: String) =
            if (isNull(key)) null else optString(key).ifBlank { null }

        fun parseDevApp(o: JSONObject) = DevApp(
            fullName = o.getString("id"),
            name = o.optString("name"),
            description = o.optString("description"),
            category = o.optString("category"),
            homepage = o.optString("homepage"),
            developer = o.optStringOrNull("developer"),
            sourceType = o.optString("source_type"),
            sourceUrl = o.optString("source_url"),
            hasSourceToken = o.optBoolean("has_source_token"),
            packageName = o.optStringOrNull("package_name"),
            access = Access.of(o.optString("access")),
            priceCents = o.optInt("price_cents"),
            beta = BetaMode.of(o.optString("beta")),
            review = o.optString("review"),
            reviewNote = o.optString("review_note"),
            avatarUrl = o.optStringOrNull("avatar_url"),
            stable = o.optStringOrNull("stable"),
            betaVersion = o.optStringOrNull("beta_version"),
            sourceError = o.optStringOrNull("source_error"),
            downloads = o.optInt("downloads"),
            downloads30d = o.optInt("downloads_30d"),
            sales = o.optInt("sales"),
            revenueCents = o.optLong("revenue_cents"),
            codesOpen = o.optInt("codes_open"),
            codesUsed = o.optInt("codes_used"),
            testers = o.optInt("testers"),
            unlockedUsers = o.optInt("unlocked_users"),
            screenshots = (o.optJSONArray("screenshots") ?: JSONArray()).objects()
                .map { Screenshot(it.getLong("id"), it.getString("url")) },
            pendingVersions = (o.optJSONArray("pending_versions") ?: JSONArray()).strings(),
            blockedVersions = (o.optJSONArray("blocked_versions") ?: JSONArray()).strings(),
            ratingAverage = o.optJSONObject("rating")?.optDouble("average", 0.0) ?: 0.0,
            ratingCount = o.optJSONObject("rating")?.optInt("count") ?: 0,
            reviewReleases = o.optBoolean("review_releases"),
        )

        fun parseThread(o: JSONObject) = ThreadDetail(
            id = o.getLong("id"),
            app = o.optString("app"),
            appName = o.optString("app_name"),
            kindLabel = o.optString("kind_label"),
            subject = o.optString("subject"),
            status = o.optString("status"),
            role = o.optString("role"),
            device = o.optString("device"),
            user = o.optString("user"),
            developer = o.optString("developer"),
            createdAt = o.optLong("created_at"),
            messages = (o.optJSONArray("messages") ?: JSONArray()).objects().map {
                ChatMessage(
                    id = it.getLong("id"),
                    author = it.optString("author"),
                    fromDev = it.optBoolean("from_dev"),
                    mine = it.optBoolean("mine"),
                    body = it.optString("body"),
                    createdAt = it.optLong("created_at"),
                )
            },
        )

        fun parseReviews(o: JSONObject): ReviewList {
            fun review(r: JSONObject) = Review(
                userId = r.getLong("user_id"),
                username = r.optString("username"),
                rating = r.optInt("rating"),
                text = r.optString("text"),
                version = r.optString("version"),
                updatedAt = r.optLong("updated_at"),
                reply = r.optString("reply"),
                mine = r.optBoolean("mine"),
            )
            val dist = o.optJSONArray("distribution") ?: JSONArray()
            return ReviewList(
                average = o.optDouble("average", 0.0),
                count = o.optInt("count"),
                distribution = (0 until dist.length()).map { dist.getInt(it) },
                reviews = (o.optJSONArray("reviews") ?: JSONArray()).objects().map(::review),
                canReview = o.optBoolean("can_review"),
                canReply = o.optBoolean("can_reply"),
                mine = o.optJSONObject("mine")?.let(::review),
            )
        }
    }
}

private fun JSONArray.objects(): List<JSONObject> = (0 until length()).map { getJSONObject(it) }

private fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }
