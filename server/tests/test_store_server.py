import hashlib
import hmac
import io
import json
import os
import re
import sqlite3
import struct
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import apk_info  # noqa: E402
import store_server as ss  # noqa: E402

FORGEJO = "https://git.nebendahl.eu"
WEBHOOK_SECRET = "whsec_test"


# ---------------------------------------------------------------------------
# Test-Hilfen
# ---------------------------------------------------------------------------

def axml_manifest(package: str, version_name: str, version_code: int) -> bytes:
    """Minimales binäres AndroidManifest.xml (wie von aapt2 erzeugt)."""
    strings = ["versionCode", "versionName", "manifest", "package",
               "http://schemas.android.com/apk/res/android", package, version_name]
    data = b""
    offsets = []
    for s in strings:
        offsets.append(len(data))
        data += struct.pack("<H", len(s)) + s.encode("utf-16-le") + b"\0\0"
    data += b"\0" * (-len(data) % 4)
    header = 28 + 4 * len(strings)
    pool = struct.pack("<HHIIIIII", 0x0001, 28, header + len(data), len(strings), 0, 0, header, 0)
    pool += struct.pack(f"<{len(strings)}I", *offsets) + data
    resmap = struct.pack("<HHI", 0x0180, 8, 16) + struct.pack("<II", 0x0101021B, 0x0101021C)
    attrs = [(0xFFFFFFFF, 3, 5, 0x03, 5), (4, 0, 0xFFFFFFFF, 0x10, version_code), (4, 1, 6, 0x03, 6)]
    body = struct.pack("<IIHHHHHH", 0xFFFFFFFF, 2, 20, 20, len(attrs), 0, 0, 0)
    for ns, name, raw, typ, val in attrs:
        body += struct.pack("<IIIHBBI", ns, name, raw, 8, 0, typ, val)
    elem = struct.pack("<HHIII", 0x0102, 16, 16 + len(body), 1, 0xFFFFFFFF) + body
    content = pool + resmap + elem
    return struct.pack("<HHI", 0x0003, 8, 8 + len(content)) + content


def make_apk(package="com.example.app", version="1.0.0", code=1) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("AndroidManifest.xml", axml_manifest(package, version, code))
        zf.writestr("classes.dex", b"dex\n035\0" + os.urandom(64))
    return buf.getvalue()


def forgejo_release(tag, apk, prerelease=False, url="http://f/x.apk"):
    return {"tag_name": tag, "name": tag, "body": f"Neu in {tag}", "published_at": "2026-11-07T09:05:45+01:00",
            "prerelease": prerelease, "draft": False,
            "assets": [{"name": apk, "size": 11, "browser_download_url": url}, {"name": "notes.txt", "size": 1}]}


class FakeRemote:
    """Simuliert Forgejo und GitHub."""

    def __init__(self):
        self.repos = [
            {"full_name": "Manhunt/manhunt", "name": "manhunt", "owner": {"login": "Manhunt"}, "release_counter": 4,
             "description": "Spiel", "html_url": f"{FORGEJO}/Manhunt/manhunt", "private": False},
            {"full_name": "Mrcoolgamer11/Geheim", "name": "Geheim", "owner": {"login": "Mrcoolgamer11"},
             "release_counter": 1, "description": "", "html_url": "y", "private": True},
            {"full_name": "Mrcoolgamer11/Bot", "name": "Bot", "owner": {"login": "Mrcoolgamer11"},
             "release_counter": 0},
        ]
        self.releases = {
            f"{FORGEJO}/api/v1/repos/Manhunt/manhunt/releases?limit=15": [
                forgejo_release("v2.6.0-beta1", "manhunt-v2.6.0-beta1.apk", prerelease=True, url="http://f/beta.apk"),
                forgejo_release("v2.5.0", "manhunt-v2.5.0.apk", url="http://f/manhunt.apk"),
            ],
            f"{FORGEJO}/api/v1/repos/Mrcoolgamer11/Geheim/releases?limit=15": [
                forgejo_release("v1.0", "geheim.apk", url="http://f/g.apk")],
            "https://api.github.com/repos/anna/wetter/releases?per_page=15": [
                {"tag_name": "v3.1.0", "name": "Wetter 3.1", "body": "", "prerelease": False, "draft": False,
                 "published_at": "2026-11-01T10:00:00Z", "html_url": "gh",
                 "assets": [{"name": "wetter.apk", "size": 5, "browser_download_url": "http://gh/wetter.apk",
                             "url": "http://api.gh/asset/1"}]}],
        }
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append((url, headers))
        if url.startswith(f"{FORGEJO}/api/v1/repos/search"):
            return {"data": self.repos if "page=1" in url else []}
        return self.releases.get(url)


class FakeSources(ss.Sources):
    def open_download(self, url, headers):
        data = b"APK:" + url.encode()
        resp = io.BytesIO(data)
        resp.headers = {"Content-Length": str(len(data))}
        return resp


class FakeMailer:
    enabled = True

    def __init__(self):
        self.sent = []

    def send(self, to, subject, html_body, text_body):
        self.sent.append({"to": to, "subject": subject, "html": html_body, "text": text_body})

    def to(self, addr):
        return [m for m in self.sent if m["to"] == addr]

    def token(self, addr, path):
        for m in reversed(self.sent):
            if m["to"] == addr:
                found = re.search(re.escape(path) + r"\?token=([\w-]+)", m["text"])
                if found:
                    return found.group(1)
        raise AssertionError(f"Keine Mail mit {path} an {addr}")


class FakeStripe:
    def __init__(self):
        self.calls = []

    def __call__(self, method, path, params=None):
        self.calls.append((method, path, dict(params or [])))
        if path == "/v1/checkout/sessions":
            return {"id": "cs_test_1", "url": "https://checkout.stripe.com/c/pay/cs_test_1"}
        return {"id": "re_1"}


class ServerTestCase(unittest.TestCase):
    env = {}

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        env = {"DB_PATH": os.path.join(self.tmp.name, "t.db"), "HOST": "127.0.0.1", "PORT": "0",
               "PUBLIC_URL": "https://store.test", "ALLOW_PRIVATE_SOURCES": "1", **self.env}
        self.config = ss.Config(env)
        self.remote = FakeRemote()
        self.mail = FakeMailer()
        self.stripe = FakeStripe()
        self.server = ss.make_server(self.config, FakeSources(self.config, fetcher=self.remote), mailer=self.mail,
                                     stripe=self.stripe)
        self.store = self.server.store
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def call(self, method, path, body=None, token=None, raw=False, data=None, headers=None):
        payload = data if data is not None else (json.dumps(body).encode() if body is not None else None)
        req = urllib.request.Request(self.base + path, method=method, data=payload)
        req.add_header("Content-Type", "application/json" if data is None else "application/octet-stream")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req) as r:
                out = r.read()
                return r.status, (out if raw else json.loads(out))
        except urllib.error.HTTPError as e:
            out = e.read()
            try:
                return e.code, json.loads(out)
            except ValueError:
                return e.code, out

    def register(self, name, pw="passwort123", email=None, developer=False, terms=True, expect=200):
        body = {"username": name, "password": pw, "email": email or f"{name.lower()}@example.org",
                "accept_terms": terms, "developer": developer}
        status, r = self.call("POST", "/api/register", body)
        if expect is not None:
            self.assertEqual(status, expect, r)
        return r

    def admin(self):
        return self.register("chef")["token"]

    def users(self, admin):
        return {u["username"]: u for u in self.call("GET", "/api/admin/users", token=admin)[1]["users"]}

    def developer(self, admin, name="anna"):
        tok = self.register(name, developer=True)["token"]
        uid = self.users(admin)[name]["id"]
        status, r = self.call("POST", f"/api/admin/users/{uid}/developer", {"approve": True}, admin)
        self.assertEqual(status, 200, r)
        self.verify(f"{name}@example.org")
        return tok

    def verify(self, email):
        token = self.mail.token(email, "/verify")
        status, _ = self.call("GET", f"/verify?token={token}", raw=True)
        self.assertEqual(status, 200)

    def apps(self, token=None):
        return {a["id"]: a for a in self.call("GET", "/api/apps", token=token)[1]["apps"]}

    def upload(self, token, app, apk, version="", channel="stable", notes=""):
        q = f"?channel={channel}" + (f"&version={version}" if version else "") + \
            (f"&notes={urllib.request.quote(notes)}" if notes else "")
        return self.call("POST", f"/api/dev/apps/{app}/releases{q}", data=apk, token=token)

    def pay(self, user_id, app_key, ref="cs_test_1", amount=199):
        event = {"type": "checkout.session.completed", "data": {"object": {
            "id": ref, "payment_status": "paid", "amount_total": amount, "currency": "eur",
            "payment_intent": "pi_1", "metadata": {"user_id": str(user_id), "app": app_key}}}}
        payload = json.dumps(event).encode()
        ts = int(time.time())
        sig = hmac.new(WEBHOOK_SECRET.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
        return self.call("POST", "/api/stripe/webhook", data=payload, headers={"Stripe-Signature": f"t={ts},v1={sig}"})


# ---------------------------------------------------------------------------
# Konten & Rollen
# ---------------------------------------------------------------------------

class AccountTest(ServerTestCase):
    def test_erstes_konto_wird_admin(self):
        r = self.register("chef")
        self.assertTrue(r["first_admin"])
        self.assertEqual(r["user"]["role"], "admin")
        r = self.register("anna")
        self.assertFalse(r["first_admin"])
        self.assertEqual(r["user"]["role"], "user")
        self.assertFalse(r["user"]["is_admin"])

    def test_registrierung_pruefungen(self):
        self.register("anna")
        self.register("anna", email="neu@example.org", expect=409)
        self.register("bert", email="ANNA@example.org", expect=409)
        self.register("x", expect=400)
        self.register("bert", pw="kurz", expect=400)
        self.register("bert", email="keine-mail", expect=400)
        self.register("bert", terms=False, expect=400)

    def test_login_mit_name_oder_mail(self):
        self.register("anna")
        self.assertEqual(self.call("POST", "/api/login", {"username": "ANNA", "password": "passwort123"})[0], 200)
        self.assertEqual(self.call("POST", "/api/login", {"username": "anna@example.org",
                                                          "password": "passwort123"})[0], 200)
        self.assertEqual(self.call("POST", "/api/login", {"username": "anna", "password": "falsch!!"})[0], 401)

    def test_email_bestaetigung(self):
        tok = self.register("anna")["token"]
        mails = self.mail.to("anna@example.org")
        self.assertIn("bestätige", mails[0]["subject"])
        self.assertIn("<!doctype html>", mails[0]["html"])
        self.assertFalse(self.call("GET", "/api/me", token=tok)[1]["user"]["email_verified"])
        self.verify("anna@example.org")
        self.assertTrue(self.call("GET", "/api/me", token=tok)[1]["user"]["email_verified"])
        self.assertEqual(self.call("GET", "/verify?token=falsch", raw=True)[0], 400)

    def test_passwort_vergessen(self):
        self.register("anna")
        self.assertEqual(self.call("POST", "/api/password/forgot", {"login": "niemand"})[0], 200)
        self.assertEqual(self.call("POST", "/api/password/forgot", {"login": "anna@example.org"})[0], 200)
        token = self.mail.token("anna@example.org", "/reset")
        self.assertEqual(self.call("GET", f"/reset?token={token}", raw=True)[0], 200)
        req = urllib.request.Request(self.base + "/reset", method="POST",
                                     data=f"token={token}&password=neuesPasswort1".encode())
        with urllib.request.urlopen(req) as r:
            self.assertIn("Passwort geändert", r.read().decode())
        self.assertEqual(self.call("POST", "/api/login", {"username": "anna", "password": "neuesPasswort1"})[0], 200)
        # Link nur einmal gültig
        req = urllib.request.Request(self.base + "/reset", method="POST",
                                     data=f"token={token}&password=nochmalNeu12".encode())
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(req)

    def test_passwort_aendern_und_konto_loeschen(self):
        self.admin()
        tok = self.register("anna")["token"]
        self.assertEqual(self.call("POST", "/api/me/password", {"old_password": "falsch!!",
                                                                "new_password": "neuesPasswort1"}, tok)[0], 403)
        self.assertEqual(self.call("POST", "/api/me/password", {"old_password": "passwort123",
                                                                "new_password": "neuesPasswort1"}, tok)[0], 200)
        export = self.call("GET", "/api/me/export", token=tok)[1]
        self.assertEqual(export["konto"]["username"], "anna")
        self.assertEqual(self.call("DELETE", "/api/me", {"password": "falsch!!"}, tok)[0], 403)
        self.assertEqual(self.call("DELETE", "/api/me", {"password": "neuesPasswort1"}, tok)[0], 200)
        self.assertEqual(self.call("GET", "/api/me", token=tok)[0], 401)

    def test_letzter_admin_bleibt(self):
        admin = self.admin()
        self.assertEqual(self.call("DELETE", "/api/me", {"password": "passwort123"}, admin)[0], 400)
        me = self.users(admin)["chef"]
        self.assertEqual(self.call("PUT", f"/api/admin/users/{me['id']}", {"role": "user"}, admin)[0], 400)

    def test_rollen_verwalten(self):
        admin = self.admin()
        anna_tok = self.register("anna")["token"]
        self.verify("anna@example.org")
        anna = self.users(admin)["anna"]
        self.assertEqual(self.call("GET", "/api/admin/users", token=anna_tok)[0], 403)
        status, r = self.call("PUT", f"/api/admin/users/{anna['id']}", {"role": "admin"}, admin)
        self.assertEqual((status, r["user"]["role"]), (200, "admin"))
        self.assertTrue(any("Admin" in m["subject"] for m in self.mail.to("anna@example.org")))
        self.assertEqual(self.call("GET", "/api/admin/users", token=anna_tok)[0], 200)
        # jetzt gibt es zwei Admins -> chef darf sich selbst zurückstufen
        chef = self.users(admin)["chef"]
        self.assertEqual(self.call("PUT", f"/api/admin/users/{chef['id']}", {"role": "developer"}, anna_tok)[0], 200)
        self.assertEqual(self.call("DELETE", f"/api/admin/users/{anna['id']}", token=anna_tok)[0], 400)  # selbst
        self.assertEqual(self.call("DELETE", f"/api/admin/users/{chef['id']}", token=anna_tok)[0], 200)
        self.assertEqual(self.call("GET", "/api/me", token=admin)[0], 401)

    def test_entwickler_anfrage(self):
        admin = self.admin()
        self.verify("chef@example.org")
        tok = self.register("anna", developer=True)["token"]
        self.verify("anna@example.org")
        me = self.call("GET", "/api/me", token=tok)[1]["user"]
        self.assertEqual((me["role"], me["dev_requested"]), ("user", True))
        self.assertTrue(any("Entwickler-Anfrage" in m["subject"] for m in self.mail.to("chef@example.org")))
        self.assertEqual(self.call("GET", "/api/dev/apps", token=tok)[0], 403)

        uid = self.users(admin)["anna"]["id"]
        self.call("POST", f"/api/admin/users/{uid}/developer", {"approve": False, "note": "Bitte mehr Infos"}, admin)
        me = self.call("GET", "/api/me", token=tok)[1]["user"]
        self.assertFalse(me["dev_requested"])
        self.assertIn("Bitte mehr Infos", self.mail.to("anna@example.org")[-1]["text"])

        self.call("POST", "/api/me/developer", {"note": "Ich baue Spiele"}, tok)
        self.assertTrue(self.users(admin)["anna"]["dev_requested"])
        self.call("POST", f"/api/admin/users/{uid}/developer", {"approve": True}, admin)
        me = self.call("GET", "/api/me", token=tok)[1]["user"]
        self.assertEqual((me["role"], me["is_developer"], me["dev_requested"]), ("developer", True, False))
        self.assertEqual(self.call("GET", "/api/dev/apps", token=tok)[0], 200)

    def test_ungelesener_body_stoert_keep_alive_nicht(self):
        import http.client
        tok = self.register("anna")["token"]
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1])
        # Endpunkte, die ihren Body nicht lesen (auch bei Fehlern), dürfen die Verbindung nicht vergiften
        for method, path, auth in (("POST", "/api/me/verify", tok), ("POST", "/api/dev/apps/x/y/releases", None),
                                   ("GET", "/healthz", None)):
            conn.request(method, path, body=b"{}", headers={"Authorization": f"Bearer {auth}"} if auth else {})
            conn.getresponse().read()
            conn.request("GET", "/healthz")
            r = conn.getresponse()
            self.assertEqual((r.status, r.read()), (200, b'{"ok": true}'), path)
        conn.close()

    def test_logout_und_bremse(self):
        token = self.register("anna")["token"]
        self.call("POST", "/api/logout", {}, token)
        self.assertEqual(self.call("GET", "/api/me", token=token)[0], 401)
        for _ in range(10):
            self.call("POST", "/api/login", {"username": "anna", "password": "falsch!!"})
        self.assertEqual(self.call("POST", "/api/login", {"username": "anna", "password": "passwort123"})[0], 429)


# ---------------------------------------------------------------------------
# Katalog, Codes, Forgejo-Import
# ---------------------------------------------------------------------------

class CatalogTest(ServerTestCase):
    def test_forgejo_import_nur_repos_mit_apk(self):
        apps = self.apps()
        self.assertEqual(sorted(apps), ["Manhunt/manhunt", "Mrcoolgamer11/Geheim"])
        m = apps["Manhunt/manhunt"]
        self.assertEqual((m["release"]["tag"], m["release"]["channel"]), ("v2.5.0", "stable"))
        self.assertEqual((m["beta"]["available"], m["beta"]["version"]), (False, ""))  # Beta-Programm aus
        self.assertNotIn("url", m["apks"][0])
        self.assertEqual(len(m["apks"]), 1)
        self.assertTrue(m["unlocked"])

    def test_download_proxy(self):
        status, data = self.call("GET", "/api/apps/Manhunt/manhunt/download?asset=manhunt-v2.5.0.apk", raw=True)
        self.assertEqual((status, data), (200, b"APK:http://f/manhunt.apk"))

    def test_code_freischaltung(self):
        admin = self.admin()
        user = self.register("anna")["token"]
        self.assertEqual(self.call("PUT", "/api/admin/apps/Manhunt/manhunt", {"access": "code"}, admin)[0], 200)
        app = self.apps(user)["Manhunt/manhunt"]
        self.assertEqual((app["access"], app["unlocked"]), ("code", False))
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=user)[0], 403)
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download")[0], 401)
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=admin, raw=True)[0], 200)

        code = self.call("POST", "/api/admin/apps/Manhunt/manhunt/codes", {"count": 2, "note": "Für Anna"},
                         admin)[1]["codes"][0]
        status, r = self.call("POST", "/api/redeem", {"code": code.lower().replace("-", " ")}, user)
        self.assertEqual((status, r["name"]), (200, "manhunt"))
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=user, raw=True)[0], 200)
        other = self.register("bert")["token"]
        self.assertEqual(self.call("POST", "/api/redeem", {"code": code}, other)[0], 400)

        codes = self.call("GET", "/api/admin/apps/Manhunt/manhunt/codes", token=admin)[1]["codes"]
        self.assertEqual([c["used_by"] for c in codes if c["used_by"]], ["anna"])
        stats = {a["id"]: a for a in self.call("GET", "/api/admin/apps", token=admin)[1]["apps"]}
        self.assertEqual((stats["Manhunt/manhunt"]["codes_open"], stats["Manhunt/manhunt"]["codes_used"]), (1, 1))

        anna = self.users(admin)["anna"]
        self.assertEqual(anna["unlocked"][0]["id"], "Manhunt/manhunt")
        self.call("DELETE", f"/api/admin/users/{anna['id']}/unlocks/Manhunt/manhunt", token=admin)
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=user)[0], 403)
        self.call("POST", f"/api/admin/users/{anna['id']}/unlocks/Manhunt/manhunt", {}, admin)
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=user, raw=True)[0], 200)

    def test_versteckte_app(self):
        admin = self.admin()
        user = self.register("anna")["token"]
        self.call("PUT", "/api/admin/apps/Mrcoolgamer11/Geheim", {"access": "hidden"}, admin)
        self.assertNotIn("Mrcoolgamer11/Geheim", self.apps(user))
        self.assertEqual(self.call("GET", "/api/apps/Mrcoolgamer11/Geheim/download", token=user)[0], 404)
        self.assertIn("Mrcoolgamer11/Geheim", self.apps(admin))
        self.assertEqual(self.call("PUT", "/api/admin/apps/Mrcoolgamer11/Geheim", {"access": "x"}, admin)[0], 400)

    def test_open_beta(self):
        admin = self.admin()
        user = self.register("anna")["token"]
        self.assertEqual(self.call("POST", "/api/apps/Manhunt/manhunt/beta", {}, user)[0], 400)  # Programm aus
        self.call("PUT", "/api/admin/apps/Manhunt/manhunt", {"beta": "open"}, admin)
        self.assertTrue(self.apps(user)["Manhunt/manhunt"]["beta"]["available"])
        self.assertEqual(self.call("POST", "/api/apps/Manhunt/manhunt/beta", {}, user)[0], 200)
        app = self.apps(user)["Manhunt/manhunt"]
        self.assertEqual((app["release"]["tag"], app["release"]["channel"]), ("v2.6.0-beta1", "beta"))
        status, data = self.call("GET", "/api/apps/Manhunt/manhunt/download", token=user, raw=True)
        self.assertEqual(data, b"APK:http://f/beta.apk")
        self.call("DELETE", "/api/apps/Manhunt/manhunt/beta", token=user)
        self.assertEqual(self.apps(user)["Manhunt/manhunt"]["release"]["tag"], "v2.5.0")

    def test_alte_datenbank_wird_migriert(self):
        self.tearDown()
        self.old_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.old_tmp.cleanup)
        path = os.path.join(self.old_tmp.name, "alt.db")
        conn = sqlite3.connect(path)
        conn.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                pw_hash TEXT NOT NULL, is_admin INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
            CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at INTEGER NOT NULL,
                last_used INTEGER NOT NULL);
            CREATE TABLE unlocks (user_id INTEGER NOT NULL, app TEXT NOT NULL, code TEXT, unlocked_at INTEGER NOT NULL,
                PRIMARY KEY (user_id, app));
            CREATE TABLE app_access (app TEXT PRIMARY KEY, access TEXT NOT NULL);
            INSERT INTO app_access VALUES ('manhunt/manhunt', 'code');
        """)
        conn.execute("INSERT INTO users (username, pw_hash, is_admin, created_at) VALUES (?, ?, 1, 0)",
                     ("ProfImpossible", ss.hash_password("altesPasswort")))
        conn.execute("INSERT INTO users (username, pw_hash, is_admin, created_at) VALUES ('anna', ?, 0, 0)",
                     (ss.hash_password("altesPasswort"),))
        conn.commit()
        conn.close()
        self.env = {"DB_PATH": path}
        self.setUp()
        self.config.db_path = path
        tok = self.call("POST", "/api/login", {"username": "ProfImpossible", "password": "altesPasswort"})[1]["token"]
        self.assertEqual(self.call("GET", "/api/me", token=tok)[1]["user"]["role"], "admin")
        self.assertEqual(self.users(tok)["anna"]["role"], "user")
        self.assertEqual(self.apps(tok)["Manhunt/manhunt"]["access"], "code")  # alte Freigabe übernommen
        self.assertFalse(self.register("neu")["first_admin"])

    def test_rechtstexte(self):
        status, page = self.call("GET", "/impressum", raw=True)
        self.assertEqual(status, 200)
        self.assertIn("OPERATOR_STREET", page.decode())  # fehlende Angaben sichtbar markiert
        for path in ("/datenschutz", "/agb", "/widerruf", "/", "/portal"):
            self.assertEqual(self.call("GET", path, raw=True)[0], 200, path)
        info = self.call("GET", "/api/info")[1]
        self.assertEqual(info["legal"]["impressum"], "https://store.test/impressum")


class LegalConfiguredTest(ServerTestCase):
    env = {"OPERATOR_NAME": "Erika Muster", "OPERATOR_STREET": "Hauptstr. 1", "OPERATOR_CITY": "12345 Berlin",
           "OPERATOR_EMAIL": "kontakt@example.org"}

    def test_impressum_vollstaendig(self):
        page = self.call("GET", "/impressum", raw=True)[1].decode()
        self.assertIn("Erika Muster", page)
        self.assertIn("Hauptstr. 1", page)
        self.assertNotIn('class="missing"', page)
        admin = self.admin()
        self.assertEqual(self.call("GET", "/api/admin/overview", token=admin)[1]["legal_missing"], [])


# ---------------------------------------------------------------------------
# Entwickler-Apps
# ---------------------------------------------------------------------------

class DeveloperTest(ServerTestCase):
    def setUp(self):
        super().setUp()
        self.admin_tok = self.admin()
        self.verify("chef@example.org")
        self.dev = self.developer(self.admin_tok)

    def create(self, slug="spiel", **extra):
        status, r = self.call("POST", "/api/dev/apps", {"slug": slug, "name": "Mein Spiel", "description": "Toll",
                                                        **extra}, self.dev)
        self.assertEqual(status, 200, r)
        return r

    def test_upload_app_mit_pruefung(self):
        app = self.create()
        self.assertEqual((app["id"], app["review"], app["source_type"]), ("anna/spiel", "pending", "upload"))
        self.assertTrue(any("zur Prüfung" in m["subject"] for m in self.mail.to("chef@example.org")))

        status, r = self.upload(self.dev, "anna/spiel", make_apk("com.anna.spiel", "1.0.0", 1), notes="Erste Version")
        self.assertEqual(status, 200, r)
        self.assertEqual((r["version"], r["package"], r["version_code"]), ("1.0.0", "com.anna.spiel", 1))

        user = self.register("bert")["token"]
        self.assertNotIn("anna/spiel", self.apps(user))       # noch nicht geprüft
        self.assertIn("anna/spiel", self.apps(self.dev))      # Entwickler sieht sie
        self.assertEqual(self.call("GET", "/api/apps/anna/spiel/download", token=user)[0], 404)

        status, r = self.call("PUT", "/api/admin/apps/anna/spiel", {"review": "approved"}, self.admin_tok)
        self.assertEqual((status, r["review"]), (200, "approved"))
        self.assertTrue(any("freigegeben" in m["subject"] for m in self.mail.to("anna@example.org")))
        app = self.apps(user)["anna/spiel"]
        self.assertEqual((app["release"]["tag"], app["release"]["notes"], app["owner"]), ("1.0.0", "Erste Version",
                                                                                          "anna"))
        status, data = self.call("GET", "/api/apps/anna/spiel/download", token=user, raw=True)
        self.assertEqual(status, 200)
        self.assertEqual(apk_info.read_apk_info(self._save(data))["package"], "com.anna.spiel")
        self.assertEqual(self.call("GET", "/api/dev/apps/anna/spiel", token=self.dev)[1]["downloads"], 1)

    def _save(self, data):
        path = os.path.join(self.tmp.name, "dl.apk")
        with open(path, "wb") as f:
            f.write(data)
        return path

    def test_upload_regeln(self):
        self.create()
        up = lambda apk, **kw: self.upload(self.dev, "anna/spiel", apk, **kw)  # noqa: E731
        self.assertEqual(up(b"kein zip")[0], 400)
        status, r = up(make_apk("com.anna.spiel", "1.0.0", 1), version="1.1.0")
        self.assertEqual(status, 400)
        self.assertIn("versionName", r["error"])
        self.assertEqual(up(make_apk("com.anna.spiel", "1.0.0", 5))[0], 200)
        status, r = up(make_apk("com.anna.spiel", "1.0.1", 5))
        self.assertIn("versionCode", r["error"])
        status, r = up(make_apk("com.anderes.paket", "1.0.1", 6))
        self.assertIn("Falsche App", r["error"])
        self.assertEqual(up(make_apk("com.anna.spiel", "v1.1.0", 6), version="1.1.0")[0], 200)  # v-Präfix egal
        releases = self.call("GET", "/api/dev/apps/anna/spiel/releases", token=self.dev)[1]["releases"]
        self.assertEqual([r["version"] for r in releases], ["1.1.0", "1.0.0"])
        self.assertEqual(self.call("DELETE", f"/api/dev/apps/anna/spiel/releases/{releases[0]['id']}",
                                   token=self.dev)[0], 200)

    def test_fremde_apps_tabu(self):
        self.create()
        other = self.developer(self.admin_tok, "carl")
        self.assertEqual(self.call("PUT", "/api/dev/apps/anna/spiel", {"name": "Hack"}, other)[0], 403)
        self.assertEqual(self.upload(other, "anna/spiel", make_apk())[0], 403)
        self.assertEqual(self.call("GET", "/api/dev/apps/anna/spiel/codes", token=other)[0], 403)
        self.assertEqual(self.call("PUT", "/api/dev/apps/Manhunt/manhunt", {"name": "Hack"}, other)[0], 403)
        # Admin darf alles
        self.assertEqual(self.call("PUT", "/api/dev/apps/anna/spiel", {"name": "Neu"}, self.admin_tok)[0], 200)

    def test_quelle_github(self):
        app = self.create("wetter", source_url="https://github.com/anna/wetter.git")
        self.assertEqual((app["source_type"], app["stable"]), ("github", "v3.1.0"))
        self.assertEqual(self.upload(self.dev, "anna/wetter", make_apk())[0], 400)  # Versionen kommen aus Quelle
        self.call("PUT", "/api/admin/apps/anna/wetter", {"review": "approved"}, self.admin_tok)
        status, data = self.call("GET", "/api/apps/anna/wetter/download", raw=True)
        self.assertEqual(data, b"APK:http://gh/wetter.apk")
        status, r = self.call("POST", "/api/dev/apps", {"slug": "leer", "name": "Leer",
                                                        "source_url": "https://github.com/anna/gibtsnicht"}, self.dev)
        self.assertEqual(status, 404, r)

    def test_server_token_nicht_fuer_entwickler_quellen(self):
        self.config.forgejo_token = "server-geheim"
        self.call("POST", "/api/dev/apps", {"slug": "fremd", "name": "Fremd",
                                            "source_url": f"{FORGEJO}/Mrcoolgamer11/Geheim"}, self.dev)
        dev_calls = [h for url, h in self.remote.calls if "Geheim" in url and h.get("Authorization")]
        self.store.sources.last_discovery = 0
        self.apps()
        auto_calls = [h for url, h in self.remote.calls if "repos/search" in url]
        self.assertEqual(dev_calls, [])  # kein Server-Token bei Entwickler-Quellen
        self.assertEqual(auto_calls[-1]["Authorization"], "token server-geheim")  # aber beim Import

    def test_ssrf_schutz(self):
        self.config.allow_private_sources = False
        status, r = self.call("POST", "/api/dev/apps", {"slug": "boese", "name": "Böse",
                                                        "source_url": "http://127.0.0.1:8080/a/b"}, self.dev)
        self.assertEqual(status, 400, r)
        status, r = self.call("POST", "/api/dev/apps", {"slug": "boese", "name": "Böse",
                                                        "source_url": "https://localhost/a/b"}, self.dev)
        self.assertEqual(status, 400, r)

    def test_codes_und_closed_beta_eigene_app(self):
        self.create(beta="closed")
        self.upload(self.dev, "anna/spiel", make_apk("com.anna.spiel", "1.0.0", 1))
        self.upload(self.dev, "anna/spiel", make_apk("com.anna.spiel", "1.1.0-beta", 2), channel="beta")
        self.call("PUT", "/api/admin/apps/anna/spiel", {"review": "approved", "access": "code"}, self.admin_tok)
        user = self.register("bert")["token"]
        self.verify("bert@example.org")
        self.assertEqual(self.call("POST", "/api/apps/anna/spiel/beta", {}, user)[0], 403)  # geschlossen
        self.call("POST", "/api/dev/apps/anna/spiel/testers", {"username": "bert"}, self.dev)
        self.assertTrue(any("Beta" in m["subject"] for m in self.mail.to("bert@example.org")))
        app = self.apps(user)["anna/spiel"]
        self.assertEqual((app["release"]["tag"], app["unlocked"]), ("1.1.0-beta", False))
        code = self.call("POST", "/api/dev/apps/anna/spiel/codes", {"count": 1}, self.dev)[1]["codes"][0]
        self.call("POST", "/api/redeem", {"code": code}, user)
        status, data = self.call("GET", "/api/apps/anna/spiel/download", token=user, raw=True)
        self.assertEqual(apk_info.read_apk_info(self._save(data))["version_name"], "1.1.0-beta")
        self.assertEqual(self.call("DELETE", f"/api/dev/codes/{code}", token=self.dev)[0], 200)

    def test_update_mail_an_nutzer(self):
        self.create()
        self.upload(self.dev, "anna/spiel", make_apk("com.anna.spiel", "1.0.0", 1))
        self.call("PUT", "/api/admin/apps/anna/spiel", {"review": "approved"}, self.admin_tok)
        user = self.register("bert")["token"]
        self.verify("bert@example.org")
        self.call("GET", "/api/apps/anna/spiel/download", token=user, raw=True)
        self.upload(self.dev, "anna/spiel", make_apk("com.anna.spiel", "1.1.0", 2), notes="Neue Level")
        mail = self.mail.to("bert@example.org")[-1]
        self.assertEqual(mail["subject"], "Update: Mein Spiel 1.1.0")
        self.assertIn("Neue Level", mail["text"])
        # abgeschaltet -> keine Mail
        self.call("PUT", "/api/me", {"notify_updates": False}, user)
        n = len(self.mail.sent)
        self.upload(self.dev, "anna/spiel", make_apk("com.anna.spiel", "1.2.0", 3))
        self.assertEqual(len(self.mail.to("bert@example.org")), len([m for m in self.mail.sent[:n]
                                                                     if m["to"] == "bert@example.org"]))

    def test_api_schluessel_fuer_ci(self):
        self.create()
        key = self.call("POST", "/api/dev/keys", {"label": "GitHub Actions"}, self.dev)[1]["token"]
        self.assertEqual(self.upload(key, "anna/spiel", make_apk("com.anna.spiel", "1.0.0", 1))[0], 200)
        keys = self.call("GET", "/api/dev/keys", token=self.dev)[1]["keys"]
        self.assertEqual(keys[0]["label"], "GitHub Actions")
        self.call("DELETE", f"/api/dev/keys/{keys[0]['id']}", token=self.dev)
        self.assertEqual(self.call("GET", "/api/dev/apps", token=key)[0], 401)

    def test_icon(self):
        self.create()
        png = b"\x89PNG\r\n\x1a\n" + b"\0" * 32
        r = self.call("POST", "/api/dev/apps/anna/spiel/icon", data=png, token=self.dev)[1]
        self.assertIn("/api/apps/anna/spiel/icon", r["avatar_url"])
        self.assertEqual(self.call("GET", "/api/apps/anna/spiel/icon", raw=True), (200, png))
        self.assertEqual(self.call("POST", "/api/dev/apps/anna/spiel/icon", data=b"GIF89a", token=self.dev)[0], 400)

    def test_entwickler_loeschen_versteckt_apps(self):
        self.create()
        anna = self.users(self.admin_tok)["anna"]
        self.call("DELETE", f"/api/admin/users/{anna['id']}", token=self.admin_tok)
        app = {a["id"]: a for a in self.call("GET", "/api/admin/apps", token=self.admin_tok)[1]["apps"]}["anna/spiel"]
        self.assertEqual((app["developer"], app["access"]), (None, "hidden"))


# ---------------------------------------------------------------------------
# Kostenpflichtige Apps
# ---------------------------------------------------------------------------

class PaidAppTest(ServerTestCase):
    env = {"STRIPE_SECRET_KEY": "sk_test_x", "STRIPE_WEBHOOK_SECRET": WEBHOOK_SECRET,
           "OPERATOR_EMAIL": "betreiber@example.org"}

    def setUp(self):
        super().setUp()
        self.admin_tok = self.admin()
        self.call("PUT", "/api/admin/apps/Manhunt/manhunt", {"price_cents": 199}, self.admin_tok)
        self.user = self.register("bert")["token"]
        self.uid = self.users(self.admin_tok)["bert"]["id"]

    def test_kauf_ablauf(self):
        app = self.apps(self.user)["Manhunt/manhunt"]
        self.assertEqual((app["price"], app["unlocked"], app["can_buy"]), ("1,99 €", False, True))
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=self.user)[0], 402)
        self.assertEqual(self.call("POST", "/api/apps/Manhunt/manhunt/purchase", {}, self.user)[0], 400)  # Zustimmung
        status, r = self.call("POST", "/api/apps/Manhunt/manhunt/purchase", {"accept_waiver": True}, self.user)
        self.assertEqual(r["checkout_url"], "https://checkout.stripe.com/c/pay/cs_test_1")
        params = self.stripe.calls[-1][2]
        self.assertEqual(params["line_items[0][price_data][unit_amount]"], "199")
        self.assertEqual(params["metadata[app]"], "manhunt/manhunt")

        self.assertEqual(self.pay(self.uid, "manhunt/manhunt")[0], 200)
        self.assertEqual(self.pay(self.uid, "manhunt/manhunt")[0], 200)  # doppelt zugestellt
        self.assertTrue(self.apps(self.user)["Manhunt/manhunt"]["unlocked"])
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=self.user, raw=True)[0], 200)
        purchases = self.call("GET", "/api/me/purchases", token=self.user)[1]["purchases"]
        self.assertEqual(len(purchases), 1)
        self.assertTrue(purchases[0]["can_withdraw"])
        self.assertTrue(any(m["subject"] == "Kaufbeleg: manhunt" for m in self.mail.to("bert@example.org")))
        self.assertEqual(self.call("POST", "/api/apps/Manhunt/manhunt/purchase", {"accept_waiver": True},
                                   self.user)[0], 409)

        # Widerruf über die App, dann Erstattung durch den Admin
        self.assertEqual(self.call("POST", f"/api/me/purchases/{purchases[0]['id']}/withdraw", {}, self.user)[0], 200)
        self.assertEqual(self.call("POST", f"/api/me/purchases/{purchases[0]['id']}/withdraw", {}, self.user)[0], 400)
        self.assertTrue(any("Widerruf" in m["subject"] for m in self.mail.to("bert@example.org")))
        self.assertTrue(any("Widerruf" in m["subject"] for m in self.mail.to("betreiber@example.org")))
        self.assertEqual(self.call("POST", f"/api/admin/purchases/{purchases[0]['id']}/refund", {},
                                   self.admin_tok)[0], 200)
        self.assertEqual(self.stripe.calls[-1][1:], ("/v1/refunds", {"payment_intent": "pi_1"}))
        self.assertFalse(self.apps(self.user)["Manhunt/manhunt"]["unlocked"])

    def test_falsche_signatur(self):
        status, _ = self.call("POST", "/api/stripe/webhook", data=b"{}", headers={"Stripe-Signature": "t=1,v1=00"})
        self.assertEqual(status, 400)

    def test_code_als_gutschein(self):
        code = self.call("POST", "/api/admin/apps/Manhunt/manhunt/codes", {"count": 1}, self.admin_tok)[1]["codes"][0]
        self.call("POST", "/api/redeem", {"code": code}, self.user)
        self.assertTrue(self.apps(self.user)["Manhunt/manhunt"]["unlocked"])


class PaidWithoutStripeTest(ServerTestCase):
    def test_ohne_zahlungsanbieter(self):
        admin = self.admin()
        self.call("PUT", "/api/admin/apps/Manhunt/manhunt", {"price_cents": 199}, admin)
        user = self.register("bert")["token"]
        self.assertFalse(self.apps(user)["Manhunt/manhunt"]["can_buy"])
        self.assertEqual(self.call("POST", "/api/apps/Manhunt/manhunt/purchase", {"accept_waiver": True},
                                   user)[0], 503)
        self.assertEqual(self.call("PUT", "/api/admin/apps/Manhunt/manhunt", {"price_cents": 10}, admin)[0], 400)


# ---------------------------------------------------------------------------
# Einheiten
# ---------------------------------------------------------------------------

class CliTest(ServerTestCase):
    def test_rolle_per_kommandozeile(self):
        import contextlib
        admin = self.admin()
        self.register("Mrcoolgamer11")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(ss.cli(self.config, ["set-role", "mrcoolgamer11", "admin"]), 0)
            self.assertEqual(ss.cli(self.config, ["users"]), 0)
        self.assertIn("user -> admin", out.getvalue())
        self.assertEqual(self.users(admin)["Mrcoolgamer11"]["role"], "admin")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ss.cli(self.config, ["set-role", "niemand", "admin"]), 1)
            self.assertEqual(ss.cli(self.config, ["set-role", "chef", "chef"]), 2)
            ss.cli(self.config, ["set-role", "Mrcoolgamer11", "user"])
            self.assertEqual(ss.cli(self.config, ["set-role", "chef", "user"]), 1)  # letzter Admin
        with contextlib.redirect_stdout(out):
            self.assertEqual(ss.cli(self.config, ["reset-password", "chef"]), 0)
        pw = out.getvalue().rsplit(": ", 1)[1].strip()
        self.assertEqual(self.call("POST", "/api/login", {"username": "chef", "password": pw})[0], 200)
        self.assertEqual(self.call("GET", "/api/me", token=admin)[0], 401)  # alte Sitzung beendet


class HelperTest(unittest.TestCase):
    def test_passwort_hash(self):
        h = ss.hash_password("geheim123")
        self.assertTrue(ss.verify_password("geheim123", h))
        self.assertFalse(ss.verify_password("geheim124", h))

    def test_code_format(self):
        self.assertRegex(ss.new_code(), r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertEqual(ss.normalize_code(" ab cd-efgh "), "ABCD-EFGH")

    def test_apk_info(self):
        info = apk_info.parse_manifest(axml_manifest("com.x.y", "2.5.0", 42))
        self.assertEqual(info, {"package": "com.x.y", "version_name": "2.5.0", "version_code": 42, "icon": None,
                                "round_icon": None})
        with self.assertRaises(apk_info.ApkError):
            apk_info.parse_manifest(b"<manifest/>")

    def test_quelle_parsen(self):
        self.assertEqual(ss.parse_source("https://github.com/a/b.git"), ("github", "https://github.com", "a/b"))
        self.assertEqual(ss.parse_source("https://codeberg.org/a/b/releases"),
                         ("forgejo", "https://codeberg.org", "a/b"))
        with self.assertRaises(ss.HttpError):
            ss.parse_source("github.com/a")

    def test_preis(self):
        self.assertEqual(ss.format_price(199), "1,99 €")
        self.assertEqual(ss.format_price(1000, "usd"), "10,00 $")

    def test_mail_vorlage_escaped(self):
        cfg = ss.Config({"PUBLIC_URL": "https://s.test"})
        html_body, text = ss.mail.render(cfg, title="Hallo <b>", intro="x & y", button=("Los", "https://s.test/a"))
        self.assertIn("Hallo &lt;b&gt;", html_body)
        self.assertIn("Los: https://s.test/a", text)
        self.assertIn("https://s.test/impressum", html_body)


if __name__ == "__main__":
    unittest.main()
