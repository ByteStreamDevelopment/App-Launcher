package com.bytestreamdevelopment.bytedroide.data

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Prüft, dass die App echte Antworten des Store-Servers versteht.
 * api-samples.json wurde mit server/tests erzeugt (siehe README, Abschnitt Tests).
 */
class ApiContractTest {
    private val samples = JSONObject(javaClass.classLoader!!.getResource("api-samples.json")!!.readText())

    @Test
    fun katalogEintrag() {
        val apps = samples.getJSONObject("apps").getJSONArray("apps")
        val raw = (0 until apps.length()).map { apps.getJSONObject(it) }.first { it.getString("id") == "anna/spiel" }
        val app = Catalog.parseApp(raw, arrayOf("arm64-v8a"))
        assertNotNull(app)
        app!!
        assertEquals("Mein Spiel", app.name)
        assertEquals("anna", app.developer)
        assertEquals("Spiele", app.category)
        assertEquals(199, app.priceCents)
        assertEquals("1,99 €", app.price)
        assertTrue(app.isPaid)
        assertTrue(app.canBuy)
        assertTrue(app.unlocked)
        assertTrue(app.isBetaRelease)
        assertEquals(BetaMode.Open, app.beta.mode)
        assertTrue(app.beta.joined)
        assertEquals("1.1.0-beta", app.release.tag)
        assertTrue(app.release.apk.name.endsWith(".apk"))
        assertTrue(app.release.apk.size > 0)
        assertEquals("com.anna.spiel", app.packageName)
    }

    @Test
    fun benutzer() {
        val me = StoreApi.parseUser(samples.getJSONObject("me").getJSONObject("user"))
        assertEquals("anna", me.username)
        assertEquals(Role.Developer, me.role)
        assertTrue(me.isDeveloper)
        assertFalse(me.isAdmin)
        assertTrue(me.emailVerified)
        assertEquals("anna@example.org", me.email)
    }

    @Test
    fun entwicklerApp() {
        val app = StoreApi.parseDevApp(samples.getJSONObject("devapp"))
        assertEquals("anna/spiel", app.fullName)
        assertTrue(app.isUpload)
        assertEquals("com.anna.spiel", app.packageName)
        assertEquals("1.0.0", app.stable)
        assertEquals("1.1.0-beta", app.betaVersion)
        assertEquals("approved", app.review)
        assertEquals(1, app.sales)
        assertEquals(199L, app.revenueCents)
    }

    @Test
    fun adminBenutzerliste() {
        val users = samples.getJSONObject("users").getJSONArray("users")
        val roles = (0 until users.length()).map { StoreApi.parseUser(users.getJSONObject(it)).role }
        assertTrue(Role.Admin in roles)
        assertTrue(Role.Developer in roles)
        assertTrue(Role.User in roles)
    }

    @Test
    fun kaeufe() {
        val p = samples.getJSONObject("purchases").getJSONArray("purchases").getJSONObject(0)
        assertEquals("paid", p.getString("status"))
        assertTrue(p.getBoolean("can_withdraw"))
        assertEquals("1,99 €", p.getString("price"))
    }

    @Test
    fun preisFormat() = assertEquals("12,05 €", formatCents(1205))
}
