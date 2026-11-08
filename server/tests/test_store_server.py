import io
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import store_server as ss  # noqa: E402

ADMIN_PW = "test-admin-passwort"

REPOS = {"data": [
    {"full_name": "Manhunt/manhunt", "name": "manhunt", "owner": {"login": "Manhunt"},
     "release_counter": 4, "description": "Spiel", "html_url": "x", "private": False},
    {"full_name": "Mrcoolgamer11/Geheim", "name": "Geheim", "owner": {"login": "Mrcoolgamer11"},
     "release_counter": 1, "description": "", "html_url": "y", "private": True},
    {"full_name": "Mrcoolgamer11/Bot", "name": "Bot", "owner": {"login": "Mrcoolgamer11"},
     "release_counter": 0},
]}

RELEASES = {
    "/api/v1/repos/Manhunt/manhunt/releases/latest": {
        "tag_name": "v2.5.0", "name": "v2.5.0", "body": "Neu", "published_at": "2026-11-07T09:05:45+01:00",
        "assets": [{"name": "manhunt-v2.5.0.apk", "size": 11, "browser_download_url": "http://f/manhunt.apk"}]},
    "/api/v1/repos/Mrcoolgamer11/Geheim/releases/latest": {
        "tag_name": "v1.0", "assets": [{"name": "geheim.apk", "size": 6, "browser_download_url": "http://f/g.apk"},
                                       {"name": "notes.txt", "size": 1}]},
}


def fake_fetch(path):
    if path.startswith("/api/v1/repos/search"):
        return REPOS if "page=1" in path else {"data": []}
    return RELEASES.get(path)


class FakeCatalog(ss.Catalog):
    def open_download(self, url):
        data = b"APK:" + url.encode()
        resp = io.BytesIO(data)
        resp.headers = {"Content-Length": str(len(data))}
        return resp


class StoreServerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        config = ss.Config({"ADMIN_PASSWORD": ADMIN_PW, "DB_PATH": os.path.join(self.tmp.name, "t.db"),
                            "HOST": "127.0.0.1", "PORT": "0"})
        self.server = ss.make_server(config, FakeCatalog(config, fetcher=fake_fetch))
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def call(self, method, path, body=None, token=None, raw=False):
        req = urllib.request.Request(self.base + path, method=method,
                                     data=json.dumps(body).encode() if body is not None else None)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req) as r:
                data = r.read()
                return r.status, (data if raw else json.loads(data))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def register(self, name, pw="passwort123", admin_pw=None):
        body = {"username": name, "password": pw}
        if admin_pw:
            body["admin_password"] = admin_pw
        return self.call("POST", "/api/register", body)

    def admin(self):
        status, r = self.register("ProfImpossible", admin_pw=ADMIN_PW)
        self.assertEqual(status, 200, r)
        return r["token"]

    # --- Tests ---------------------------------------------------------------

    def test_katalog_nur_repos_mit_apk(self):
        status, r = self.call("GET", "/api/apps")
        self.assertEqual(status, 200)
        self.assertEqual([a["id"] for a in r["apps"]], ["Mrcoolgamer11/Geheim", "Manhunt/manhunt"])
        self.assertTrue(all(a["access"] == "open" and a["unlocked"] for a in r["apps"]))
        self.assertNotIn("url", r["apps"][0]["apks"][0])  # Forgejo-URL bleibt intern
        self.assertEqual(len(r["apps"][0]["apks"]), 1)

    def test_admin_registrierung_braucht_passwort(self):
        self.assertEqual(self.register("ProfImpossible")[0], 403)
        self.assertEqual(self.register("profimpossible", admin_pw="falsch")[0], 403)
        status, r = self.register("ProfImpossible", admin_pw=ADMIN_PW)
        self.assertEqual(status, 200)
        self.assertTrue(r["user"]["is_admin"])
        self.assertTrue(r["user"]["is_owner"])
        self.assertEqual(self.register("ProfImpossible", admin_pw=ADMIN_PW)[0], 409)

    def test_normale_registrierung_und_login(self):
        status, r = self.register("anna")
        self.assertEqual(status, 200)
        self.assertFalse(r["user"]["is_admin"])
        self.assertEqual(self.call("POST", "/api/login", {"username": "ANNA", "password": "passwort123"})[0], 200)
        self.assertEqual(self.call("POST", "/api/login", {"username": "anna", "password": "falsch!!"})[0], 401)
        self.assertEqual(self.register("anna")[0], 409)
        self.assertEqual(self.register("x")[0], 400)
        self.assertEqual(self.register("bert", pw="kurz")[0], 400)

    def test_nicht_admin_kein_adminbereich(self):
        token = self.register("anna")[1]["token"]
        self.assertEqual(self.call("GET", "/api/admin/apps", token=token)[0], 403)
        self.assertEqual(self.call("GET", "/api/admin/apps")[0], 401)

    def test_code_freischaltung(self):
        admin = self.admin()
        user = self.register("anna")[1]["token"]
        self.assertEqual(self.call("PUT", "/api/admin/apps/Manhunt/manhunt", {"access": "code"}, admin)[0], 200)

        apps = {a["id"]: a for a in self.call("GET", "/api/apps", token=user)[1]["apps"]}
        self.assertEqual(apps["Manhunt/manhunt"]["access"], "code")
        self.assertFalse(apps["Manhunt/manhunt"]["unlocked"])
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=user)[0], 403)
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download")[0], 401)
        # Admin darf immer
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=admin, raw=True)[0], 200)

        code = self.call("POST", "/api/admin/apps/Manhunt/manhunt/codes", {"count": 2, "note": "Für Anna"},
                         admin)[1]["codes"][0]
        status, r = self.call("POST", "/api/redeem", {"code": code.lower().replace("-", " ")}, user)
        self.assertEqual(status, 200, r)
        self.assertEqual(r["name"], "manhunt")

        status, data = self.call("GET", "/api/apps/Manhunt/manhunt/download?asset=manhunt-v2.5.0.apk",
                                 token=user, raw=True)
        self.assertEqual((status, data), (200, b"APK:http://f/manhunt.apk"))

        # Einmal-Code: zweites Einlösen schlägt fehl
        other = self.register("bert")[1]["token"]
        self.assertEqual(self.call("POST", "/api/redeem", {"code": code}, other)[0], 400)

        codes = self.call("GET", "/api/admin/apps/Manhunt/manhunt/codes", token=admin)[1]["codes"]
        self.assertEqual(len(codes), 2)
        used = [c for c in codes if c["used_by"]]
        self.assertEqual(used[0]["used_by"], "anna")
        self.assertEqual(used[0]["note"], "Für Anna")

        stats = {a["id"]: a for a in self.call("GET", "/api/admin/apps", token=admin)[1]["apps"]}
        self.assertEqual((stats["Manhunt/manhunt"]["codes_open"], stats["Manhunt/manhunt"]["codes_used"]), (1, 1))

        # Zugriff entziehen
        users = {u["username"]: u for u in self.call("GET", "/api/admin/users", token=admin)[1]["users"]}
        self.assertEqual(users["anna"]["unlocked"][0]["id"], "Manhunt/manhunt")
        self.call("DELETE", f"/api/admin/users/{users['anna']['id']}/unlocks/Manhunt/manhunt", token=admin)
        self.assertEqual(self.call("GET", "/api/apps/Manhunt/manhunt/download", token=user)[0], 403)

    def test_versteckte_app(self):
        admin = self.admin()
        user = self.register("anna")[1]["token"]
        self.call("PUT", "/api/admin/apps/Mrcoolgamer11/Geheim", {"access": "hidden"}, admin)
        ids = [a["id"] for a in self.call("GET", "/api/apps", token=user)[1]["apps"]]
        self.assertNotIn("Mrcoolgamer11/Geheim", ids)
        self.assertEqual(self.call("GET", "/api/apps/Mrcoolgamer11/Geheim/download", token=user)[0], 404)
        ids = [a["id"] for a in self.call("GET", "/api/apps", token=admin)[1]["apps"]]
        self.assertIn("Mrcoolgamer11/Geheim", ids)
        self.assertEqual(self.call("PUT", "/api/admin/apps/Mrcoolgamer11/Geheim", {"access": "x"}, admin)[0], 400)

    def test_benutzerverwaltung(self):
        admin = self.admin()
        self.register("anna")
        users = {u["username"]: u for u in self.call("GET", "/api/admin/users", token=admin)[1]["users"]}
        anna, owner = users["anna"], users["ProfImpossible"]

        status, r = self.call("PUT", f"/api/admin/users/{anna['id']}", {"is_admin": True}, admin)
        self.assertEqual(status, 200)
        self.assertTrue(r["user"]["is_admin"])
        anna_token = self.call("POST", "/api/login", {"username": "anna", "password": "passwort123"})[1]["token"]
        self.assertEqual(self.call("GET", "/api/admin/users", token=anna_token)[0], 200)

        # Haupt-Admin kann weder entzogen noch gelöscht werden
        self.assertEqual(self.call("PUT", f"/api/admin/users/{owner['id']}", {"is_admin": False}, anna_token)[0], 400)
        self.assertEqual(self.call("DELETE", f"/api/admin/users/{owner['id']}", token=anna_token)[0], 400)
        # Selbst löschen geht nicht
        self.assertEqual(self.call("DELETE", f"/api/admin/users/{anna['id']}", token=anna_token)[0], 400)

        self.assertEqual(self.call("PUT", f"/api/admin/users/{anna['id']}", {"is_admin": False}, admin)[0], 200)
        self.assertEqual(self.call("GET", "/api/admin/users", token=anna_token)[0], 403)
        self.assertEqual(self.call("DELETE", f"/api/admin/users/{anna['id']}", token=admin)[0], 200)
        self.assertEqual(self.call("GET", "/api/me", token=anna_token)[0], 401)

    def test_logout(self):
        token = self.register("anna")[1]["token"]
        self.assertEqual(self.call("GET", "/api/me", token=token)[0], 200)
        self.call("POST", "/api/logout", {}, token)
        self.assertEqual(self.call("GET", "/api/me", token=token)[0], 401)

    def test_fehlversuch_bremse(self):
        self.register("anna")
        for _ in range(10):
            self.call("POST", "/api/login", {"username": "anna", "password": "falsch!!"})
        self.assertEqual(self.call("POST", "/api/login", {"username": "anna", "password": "passwort123"})[0], 429)


class HelperTest(unittest.TestCase):
    def test_passwort_hash(self):
        h = ss.hash_password("geheim123")
        self.assertTrue(ss.verify_password("geheim123", h))
        self.assertFalse(ss.verify_password("geheim124", h))

    def test_code_format(self):
        code = ss.new_code()
        self.assertRegex(code, r"^[A-Z2-9]{4}-[A-Z2-9]{4}$")
        self.assertEqual(ss.normalize_code(" ab cd-efgh "), "ABCD-EFGH")


if __name__ == "__main__":
    unittest.main()
