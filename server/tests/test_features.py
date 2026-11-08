"""Tests für Bewertungen, Screenshots, ntfy, Rollouts, Versions-Prüfung, Virenscan und Web-Store."""

import os
import socket
import struct
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import scanner  # noqa: E402
import store_server as ss  # noqa: E402
from test_store_server import ServerTestCase, make_apk  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\0" * 40
EICAR_MARK = b"EICAR-TEST"


class FakePusher:
    enabled = True
    base_url = "https://ntfy.test"

    def __init__(self):
        self.sent = []

    def topic_url(self, topic):
        return f"{self.base_url}/{topic}"

    def send(self, topic, title, message, click="", **_):
        self.sent.append({"topic": topic, "title": title, "message": message, "click": click})


class FakeScanner:
    enabled = True

    def scan_file(self, path):
        with open(path, "rb") as f:
            return "Eicar-Test-Signature" if EICAR_MARK in f.read() else None

    def scan_stream(self, read):
        data = b""
        while True:
            chunk = read(65536)
            if not chunk:
                break
            data += chunk
        return "Eicar-Test-Signature" if b"infected" in data else None


def infected_apk(package, version, code):
    import io
    import zipfile
    buf = io.BytesIO(make_apk(package, version, code))
    with zipfile.ZipFile(buf, "a") as zf:
        zf.writestr("assets/x.txt", EICAR_MARK)
    return buf.getvalue()


class FeatureCase(ServerTestCase):
    """Wie ServerTestCase, aber mit Fake-Push und optional Fake-Virenscanner."""
    use_scanner = False

    def setUp(self):
        self.pusher = FakePusher()
        original = ss.make_server

        def patched(config, sources=None, mailer=None, stripe=None, **_):
            return original(config, sources, mailer, stripe, pusher=self.pusher,
                            virus_scanner=FakeScanner() if self.use_scanner else None)
        ss.make_server = patched
        try:
            super().setUp()
        finally:
            ss.make_server = original
        self.admin_tok = self.admin()
        self.verify("chef@example.org")
        self.dev = self.developer(self.admin_tok)

    def upload_app(self, slug="spiel", versions=(("1.0.0", 1),), **extra):
        status, r = self.call("POST", "/api/dev/apps", {"slug": slug, "name": "Mein Spiel", **extra}, self.dev)
        self.assertEqual(status, 200, r)
        for v, code in versions:
            status, r = self.upload(self.dev, f"anna/{slug}", make_apk(f"com.anna.{slug}", v, code))
            self.assertEqual(status, 200, r)
        self.call("PUT", f"/api/admin/apps/anna/{slug}", {"review": "approved"}, self.admin_tok)


# ---------------------------------------------------------------------------

class ReviewTest(FeatureCase):
    def test_bewertungen(self):
        self.upload_app()
        user = self.register("bert")["token"]
        self.verify("bert@example.org")
        self.assertEqual(self.call("PUT", "/api/apps/anna/spiel/reviews", {"rating": 5}, user)[0], 403)  # nicht geladen
        self.call("GET", "/api/apps/anna/spiel/download", token=user, raw=True)
        self.assertTrue(self.call("GET", "/api/apps/anna/spiel/reviews", token=user)[1]["can_review"])
        self.assertEqual(self.call("PUT", "/api/apps/anna/spiel/reviews", {"rating": 7}, user)[0], 400)
        status, r = self.call("PUT", "/api/apps/anna/spiel/reviews", {"rating": 4, "text": "Super Spiel"}, user)
        self.assertEqual((status, r["average"], r["count"], r["mine"]["text"]), (200, 4, 1, "Super Spiel"))
        self.assertTrue(any("Neue Bewertung" in m["subject"] for m in self.mail.to("anna@example.org")))
        # zweite Bewertung ersetzt die erste
        self.call("PUT", "/api/apps/anna/spiel/reviews", {"rating": 2, "text": "Doch nicht"}, user)
        app = self.apps()["anna/spiel"]
        self.assertEqual(app["rating"], {"average": 2.0, "count": 1})
        # Entwickler darf nicht selbst bewerten, aber antworten
        self.call("GET", "/api/apps/anna/spiel/download", token=self.dev, raw=True)
        self.assertEqual(self.call("PUT", "/api/apps/anna/spiel/reviews", {"rating": 5}, self.dev)[0], 403)
        bert_id = self.users(self.admin_tok)["bert"]["id"]
        status, r = self.call("PUT", f"/api/dev/apps/anna/spiel/reviews/{bert_id}/reply", {"text": "Danke!"}, self.dev)
        self.assertEqual(r["reviews"][0]["reply"], "Danke!")
        self.assertTrue(any("Antwort" in m["subject"] for m in self.mail.to("bert@example.org")))
        # Admin moderiert
        self.assertEqual(self.call("DELETE", f"/api/admin/apps/anna/spiel/reviews/{bert_id}", token=self.admin_tok)[0],
                         200)
        self.assertEqual(self.call("GET", "/api/apps/anna/spiel/reviews")[1]["count"], 0)


class ScreenshotTest(FeatureCase):
    def test_screenshots(self):
        self.upload_app()
        self.assertEqual(self.call("POST", "/api/dev/apps/anna/spiel/screenshots", data=b"GIF89a", token=self.dev)[0],
                         400)
        for i in range(8):
            status, r = self.call("POST", "/api/dev/apps/anna/spiel/screenshots", data=PNG + bytes([i]), token=self.dev)
            self.assertEqual(status, 200, r)
        self.assertEqual(self.call("POST", "/api/dev/apps/anna/spiel/screenshots", data=PNG + b"x", token=self.dev)[0],
                         400)
        urls = self.apps()["anna/spiel"]["screenshots"]
        self.assertEqual(len(urls), 8)
        path = urls[0].replace("https://store.test", "")
        self.assertEqual(self.call("GET", path, raw=True), (200, PNG + bytes([0])))
        shot_id = self.call("GET", "/api/dev/apps/anna/spiel", token=self.dev)[1]["screenshots"][0]["id"]
        status, r = self.call("DELETE", f"/api/dev/apps/anna/spiel/screenshots/{shot_id}", token=self.dev)
        self.assertEqual(len(r["screenshots"]), 7)
        self.assertEqual(len(self.call("GET", "/api/dev/apps/anna/spiel", token=self.dev)[1]["screenshots"]), 7)


class NtfyTest(FeatureCase):
    def test_push_ohne_bestaetigte_mail(self):
        self.upload_app()
        user = self.register("bert")["token"]  # E-Mail NICHT bestätigt
        status, r = self.call("POST", "/api/me/ntfy", {"enable": True}, user)
        topic = r["user"]["ntfy_topic"]
        self.assertTrue(topic.startswith("bytedroide-"))
        self.assertEqual(r["ntfy_url"], f"https://ntfy.test/{topic}")
        self.assertEqual(self.pusher.sent[-1]["topic"], topic)  # Begrüßung
        self.assertEqual(self.call("POST", "/api/me/ntfy/test", {}, user)[0], 200)
        self.call("GET", "/api/apps/anna/spiel/download", token=user, raw=True)
        self.upload(self.dev, "anna/spiel", make_apk("com.anna.spiel", "1.1.0", 2))
        push = [p for p in self.pusher.sent if p["topic"] == topic][-1]
        self.assertEqual(push["title"], "Update: Mein Spiel 1.1.0")
        self.assertIn("/app/anna/spiel", push["click"])
        self.assertEqual(self.mail.to("bert@example.org")[-1]["subject"], "Bitte bestätige deine E-Mail-Adresse")
        self.call("POST", "/api/me/ntfy", {"enable": False}, user)
        self.assertEqual(self.call("POST", "/api/me/ntfy/test", {}, user)[0], 400)


class RolloutTest(FeatureCase):
    def test_gestaffelter_rollout(self):
        self.upload_app()
        user = self.register("bert")["token"]
        self.verify("bert@example.org")
        self.call("GET", "/api/apps/anna/spiel/download", token=user, raw=True)
        mails_before = len(self.mail.to("bert@example.org"))
        status, r = self.call("POST", "/api/dev/apps/anna/spiel/releases?rollout=30",
                              data=make_apk("com.anna.spiel", "1.1.0", 2), token=self.dev)
        self.assertEqual((status, r["rollout"]), (200, 30))
        versions = []
        for i in range(60):
            apps = self.call("GET", "/api/apps", headers={"X-Install-Id": f"geraet-{i}"})[1]["apps"]
            versions.append({a["id"]: a for a in apps}["anna/spiel"]["release"]["tag"])
        share = versions.count("1.1.0") / len(versions)
        self.assertTrue(0.1 < share < 0.55, share)
        # gleiche Kennung -> immer gleiches Ergebnis (auch beim Download)
        new_ids = [f"geraet-{i}" for i, v in enumerate(versions) if v == "1.1.0"]
        self.assertTrue(self.call("GET", "/api/apps/anna/spiel/download", raw=True,
                                  headers={"X-Install-Id": new_ids[0]})[1].startswith(b"PK"))
        self.assertEqual(len(self.mail.to("bert@example.org")), mails_before)  # noch keine Update-Mail
        rid = self.call("GET", "/api/dev/apps/anna/spiel/releases", token=self.dev)[1]["releases"][0]["id"]
        self.assertEqual(self.call("PUT", f"/api/dev/apps/anna/spiel/releases/{rid}", {"rollout": 0}, self.dev)[0], 400)
        self.call("PUT", f"/api/dev/apps/anna/spiel/releases/{rid}", {"rollout": 100}, self.dev)
        self.assertEqual(self.mail.to("bert@example.org")[-1]["subject"], "Update: Mein Spiel 1.1.0")
        self.assertEqual(self.apps()["anna/spiel"]["release"]["tag"], "1.1.0")


class ReleaseReviewTest(FeatureCase):
    env = {"REVIEW_RELEASES": "1"}

    def test_upload_braucht_freigabe(self):
        self.upload_app()  # erste Version wartet ebenfalls
        self.assertNotIn("anna/spiel", self.apps())
        pending = self.call("GET", "/api/admin/releases", token=self.admin_tok)[1]["releases"]
        self.assertEqual([(p["app"], p["version"]) for p in pending], [("anna/spiel", "1.0.0")])
        self.assertTrue(any("zur Prüfung" in m["subject"] for m in self.mail.to("chef@example.org")))
        self.call("POST", "/api/admin/releases/decide", {"app": "anna/spiel", "approve": True,
                                                         "release_id": pending[0]["release_id"]}, self.admin_tok)
        self.assertEqual(self.apps()["anna/spiel"]["release"]["tag"], "1.0.0")
        # zweite Version: alte bleibt sichtbar, bis freigegeben bzw. abgelehnt
        self.upload(self.dev, "anna/spiel", make_apk("com.anna.spiel", "1.1.0", 2))
        self.assertEqual(self.apps()["anna/spiel"]["release"]["tag"], "1.0.0")
        rid = self.call("GET", "/api/admin/releases", token=self.admin_tok)[1]["releases"][0]["release_id"]
        self.call("POST", "/api/admin/releases/decide", {"app": "anna/spiel", "approve": False, "release_id": rid,
                                                         "note": "Absturz beim Start"}, self.admin_tok)
        self.assertEqual(self.apps()["anna/spiel"]["release"]["tag"], "1.0.0")
        self.assertIn("Absturz beim Start", self.mail.to("anna@example.org")[-1]["text"])
        releases = self.call("GET", "/api/dev/apps/anna/spiel/releases", token=self.dev)[1]["releases"]
        self.assertEqual(releases[0]["status"], "rejected")

    def test_quelle_neue_version_wartet(self):
        status, r = self.call("POST", "/api/dev/apps", {"slug": "wetter", "name": "Wetter",
                                                        "source_url": "https://github.com/anna/wetter"}, self.dev)
        self.call("PUT", "/api/admin/apps/anna/wetter", {"review": "approved"}, self.admin_tok)
        self.assertEqual(self.apps()["anna/wetter"]["release"]["tag"], "v3.1.0")
        url = "https://api.github.com/repos/anna/wetter/releases?per_page=15"
        new = dict(self.remote.releases[url][0], tag_name="v3.2.0",
                   assets=[{"name": "wetter.apk", "size": 6, "browser_download_url": "http://gh/wetter-32.apk"}])
        self.remote.releases[url] = [new] + self.remote.releases[url]
        self.call("GET", "/api/admin/apps?refresh=1", token=self.admin_tok)
        self.assertEqual(self.apps()["anna/wetter"]["release"]["tag"], "v3.1.0")  # alte bleibt
        self.assertEqual(self.call("GET", "/api/apps/anna/wetter/download", raw=True)[1], b"APK:http://gh/wetter.apk")
        pending = self.call("GET", "/api/admin/releases", token=self.admin_tok)[1]["releases"]
        self.assertEqual([(p["app"], p["version"]) for p in pending], [("anna/wetter", "v3.2.0")])
        self.call("POST", "/api/admin/releases/decide", {"app": "anna/wetter", "channel": "stable", "approve": True},
                  self.admin_tok)
        self.assertEqual(self.apps()["anna/wetter"]["release"]["tag"], "v3.2.0")
        self.assertEqual(self.call("GET", "/api/apps/anna/wetter/download", raw=True)[1], b"APK:http://gh/wetter-32.apk")

    def test_admin_apps_ohne_pruefung(self):
        status, r = self.call("POST", "/api/dev/apps", {"slug": "tool", "name": "Tool"}, self.admin_tok)
        self.assertEqual(self.upload(self.admin_tok, "chef/tool", make_apk("com.chef.tool", "1.0", 1))[1]["status"],
                         "approved")


class ScanTest(FeatureCase):
    use_scanner = True

    def test_upload_mit_schadsoftware(self):
        self.upload_app()
        status, r = self.upload(self.dev, "anna/spiel", infected_apk("com.anna.spiel", "1.1.0", 2))
        self.assertEqual(status, 400)
        self.assertIn("Schadsoftware", r["error"])
        self.assertTrue(any("Schadsoftware" in m["subject"] for m in self.mail.to("chef@example.org")))
        releases = self.call("GET", "/api/dev/apps/anna/spiel/releases", token=self.dev)[1]["releases"]
        self.assertEqual([(x["version"], x["scan"]) for x in releases], [("1.0.0", "clean")])

    def test_quelle_wird_gescannt(self):
        self.call("POST", "/api/dev/apps", {"slug": "wetter", "name": "Wetter",
                                            "source_url": "https://github.com/anna/wetter"}, self.dev)
        self.call("PUT", "/api/admin/apps/anna/wetter", {"review": "approved"}, self.admin_tok)
        self.wait_for(lambda: "anna/wetter" in self.apps())
        url = "https://api.github.com/repos/anna/wetter/releases?per_page=15"
        bad = dict(self.remote.releases[url][0], tag_name="v9.9.9",
                   assets=[{"name": "w.apk", "size": 1, "browser_download_url": "http://gh/infected.apk"}])
        self.remote.releases[url] = [bad] + self.remote.releases[url]
        self.call("GET", "/api/admin/apps?refresh=1", token=self.admin_tok)
        self.wait_for(lambda: "v9.9.9" in self.call("GET", "/api/dev/apps/anna/wetter",
                                                    token=self.dev)[1]["blocked_versions"])
        self.assertEqual(self.apps()["anna/wetter"]["release"]["tag"], "v3.1.0")
        self.assertTrue(any("Schadsoftware" in m["subject"] for m in self.mail.to("chef@example.org")))

    def wait_for(self, cond, timeout=5):
        end = time.time() + timeout
        while time.time() < end:
            if cond():
                return
            time.sleep(0.05)
        self.fail("Bedingung nicht erfüllt")


class StorefrontTest(FeatureCase):
    env = {"STORE_APP_ID": "anna/spiel"}

    def test_web_store(self):
        self.upload_app(category="Spiele", description="Ein tolles Spiel <b>fett</b>")
        status, page = self.call("GET", "/", raw=True)
        page = page.decode()
        self.assertEqual(status, 200)
        self.assertIn("Mein Spiel", page)
        self.assertIn("&lt;b&gt;fett", page)  # escaped
        self.assertIn("<svg", page)  # QR für /download
        self.assertIn("Mein Spiel", self.call("GET", "/?kategorie=Spiele", raw=True)[1].decode())
        self.assertNotIn("Mein Spiel</div>", self.call("GET", "/?q=gibtsnicht", raw=True)[1].decode())
        status, page = self.call("GET", "/app/anna/spiel", raw=True)
        page = page.decode()
        self.assertIn("APK direkt laden", page)
        self.assertIn("<svg", page)
        status, svg = self.call("GET", "/app/anna/spiel/qr.svg", raw=True)
        self.assertTrue(svg.startswith(b"<svg"))
        self.assertEqual(self.call("GET", "/.well-known/assetlinks.json")[0], 404)

    def test_assetlinks(self):
        self.config.android_cert_sha256 = "aa:bb:cc"
        status, data = self.call("GET", "/.well-known/assetlinks.json")
        self.assertEqual(data[0]["target"]["sha256_cert_fingerprints"], ["AA:BB:CC"])
        self.assertEqual(data[0]["target"]["package_name"], "com.bytestreamdevelopment.applauncher")


class ClamdProtocolTest(unittest.TestCase):
    """Prüft den echten INSTREAM-Client gegen einen Mini-clamd."""

    def serve(self, reply):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        received = []

        def run():
            conn, _ = srv.accept()
            with conn:
                cmd = conn.recv(10)
                received.append(cmd)
                data = b""
                while True:
                    size = struct.unpack("!I", self._recv(conn, 4))[0]
                    if not size:
                        break
                    data += self._recv(conn, size)
                received.append(data)
                conn.sendall(reply)
            srv.close()
        threading.Thread(target=run, daemon=True).start()
        return srv.getsockname()[1], received

    @staticmethod
    def _recv(conn, n):
        buf = b""
        while len(buf) < n:
            buf += conn.recv(n - len(buf))
        return buf

    def test_sauber_und_fund(self):
        port, received = self.serve(b"stream: OK\0")
        chunks = iter([b"abc" * 30000, b""])
        self.assertIsNone(scanner.Scanner("127.0.0.1", port).scan_stream(lambda n: next(chunks)))
        self.assertEqual((received[0], len(received[1])), (b"zINSTREAM\0", 90000))
        port, _ = self.serve(b"stream: Eicar-Test-Signature FOUND\0")
        chunks = iter([b"x", b""])
        self.assertEqual(scanner.Scanner("127.0.0.1", port).scan_stream(lambda n: next(chunks)),
                         "Eicar-Test-Signature")

    def test_nicht_erreichbar(self):
        with self.assertRaises(scanner.ScanError):
            scanner.Scanner("127.0.0.1", 1).scan_stream(lambda n: b"")


if __name__ == "__main__":
    unittest.main()
