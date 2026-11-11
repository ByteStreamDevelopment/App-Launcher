"""Tests für Bewertungen, Screenshots, ntfy, Rollouts, Versions-Prüfung, Virenscan und Web-Store."""

import os
import socket
import struct
import sys
import threading
import time
import unittest
import urllib.request

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
        self.assertIn("<svg", page)  # QR für /download
        self.assertIn("Mein Spiel", self.call("GET", "/apps?kategorie=Spiele", raw=True)[1].decode())
        self.assertNotIn("Mein Spiel</div>", self.call("GET", "/apps?q=gibtsnicht", raw=True)[1].decode())
        status, page = self.call("GET", "/app/anna/spiel", raw=True)
        page = page.decode()
        self.assertIn("APK direkt laden", page)
        self.assertIn("&lt;b&gt;fett", page)  # escaped
        self.assertNotIn("<b>fett", page)
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


# ---------------------------------------------------------------------------
# Runde 2: Reihenfolge, Nachrichten, Kontakt, Web-Seiten
# ---------------------------------------------------------------------------

class ScreenshotOrderTest(FeatureCase):
    def test_reihenfolge(self):
        self.upload_app()
        for i in range(3):
            self.call("POST", "/api/dev/apps/anna/spiel/screenshots", data=PNG + bytes([i]), token=self.dev)
        ids = [s["id"] for s in self.call("GET", "/api/dev/apps/anna/spiel", token=self.dev)[1]["screenshots"]]
        status, r = self.call("PUT", "/api/dev/apps/anna/spiel/screenshots", {"order": ids[::-1]}, self.dev)
        self.assertEqual([s["id"] for s in r["screenshots"]], ids[::-1])
        urls = self.apps()["anna/spiel"]["screenshots"]
        self.assertTrue(urls[0].endswith(f"/{ids[2]}"))
        self.assertEqual(self.call("PUT", "/api/dev/apps/anna/spiel/screenshots", {"order": ids[:2]}, self.dev)[0], 400)
        other = self.developer(self.admin_tok, "carl")
        self.assertEqual(self.call("PUT", "/api/dev/apps/anna/spiel/screenshots", {"order": ids}, other)[0], 403)


class ThreadTest(FeatureCase):
    def test_nachrichten(self):
        self.upload_app()
        user = self.register("bert")["token"]
        self.verify("bert@example.org")
        self.assertEqual(self.call("POST", "/api/apps/anna/spiel/threads", {"kind": "bug", "subject": "",
                                                                             "message": "x"}, user)[0], 400)
        status, t = self.call("POST", "/api/apps/anna/spiel/threads",
                              {"kind": "bug", "subject": "Absturz beim Start", "message": "Stürzt sofort ab",
                               "device": "Pixel 7 · Android 14 · App 1.0.0"}, user)
        self.assertEqual((status, t["role"], len(t["messages"])), (200, "user", 1))
        mail = self.mail.to("anna@example.org")[-1]
        self.assertIn("Absturz beim Start", mail["subject"])
        self.assertIn("Pixel 7", mail["text"])
        self.assertIn(f"/konto#/nachrichten/{t['id']}", mail["text"])
        # Entwickler sieht ungelesene Nachricht und antwortet
        r = self.call("GET", "/api/threads", token=self.dev)[1]
        self.assertEqual((r["unread"], r["threads"][0]["role"], r["threads"][0]["with"]), (1, "dev", "bert"))
        self.assertEqual(self.call("GET", "/api/apps", token=self.dev)[1]["unread_messages"], 1)
        status, t2 = self.call("POST", f"/api/threads/{t['id']}/messages", {"message": "Danke, ist behoben!"}, self.dev)
        self.assertTrue(t2["messages"][-1]["from_dev"])
        self.assertEqual(self.call("GET", "/api/threads", token=self.dev)[1]["unread"], 0)
        self.assertIn("Antwort zu", self.mail.to("bert@example.org")[-1]["subject"])
        self.assertEqual(self.call("GET", "/api/threads", token=user)[1]["unread"], 1)
        self.call("GET", f"/api/threads/{t['id']}", token=user)
        self.assertEqual(self.call("GET", "/api/threads", token=user)[1]["unread"], 0)
        # Fremde sehen das Gespräch nicht, eigene App geht nicht
        other = self.register("carl")["token"]
        self.assertEqual(self.call("GET", f"/api/threads/{t['id']}", token=other)[0], 404)
        self.assertEqual(self.call("POST", "/api/apps/anna/spiel/threads", {"subject": "x", "message": "y"},
                                   self.dev)[0], 400)
        # schließen und durch Antwort wieder öffnen
        self.assertEqual(self.call("PUT", f"/api/threads/{t['id']}", {"status": "closed"}, user)[1]["status"], "closed")
        self.assertEqual(self.call("POST", f"/api/threads/{t['id']}/messages", {"message": "Doch nicht"},
                                   user)[1]["status"], "open")

    def test_admin_betreut_apps_ohne_entwickler(self):
        user = self.register("bert")["token"]
        self.call("POST", "/api/apps/Manhunt/manhunt/threads", {"kind": "question", "subject": "Frage",
                                                                "message": "Wie geht das?"}, user)
        self.assertTrue(any("Frage" in m["subject"] for m in self.mail.to("chef@example.org")))
        self.assertEqual(self.call("GET", "/api/threads", token=self.admin_tok)[1]["unread"], 1)
        self.assertEqual(self.call("GET", "/api/threads", token=self.dev)[1]["threads"], [])


class ContactTest(FeatureCase):
    env = {"OPERATOR_EMAIL": "betreiber@example.org"}

    def test_kontaktformular(self):
        body = {"name": "Erika", "email": "erika@example.org", "topic": "meldung", "subject": "Schadsoftware?",
                "message": "Die App XY verhält sich seltsam.", "privacy": True}
        self.assertEqual(self.call("POST", "/api/contact", dict(body, privacy=False))[0], 400)
        self.assertEqual(self.call("POST", "/api/contact", dict(body, message="kurz"))[0], 400)
        status, r = self.call("POST", "/api/contact", body)
        self.assertEqual(status, 200)
        self.assertIn("Schadsoftware?", self.mail.to("betreiber@example.org")[-1]["subject"])
        self.assertIn("erhalten", self.mail.to("erika@example.org")[-1]["subject"])
        # Honigtopf: wird still verworfen
        n = len(self.mail.sent)
        self.assertEqual(self.call("POST", "/api/contact", dict(body, website="spam.example"))[0], 200)
        self.assertEqual(len(self.mail.sent), n)
        msgs = self.call("GET", "/api/admin/contact", token=self.admin_tok)[1]["messages"]
        self.assertEqual((len(msgs), msgs[0]["topic_label"]), (1, "Rechtswidrigen Inhalt melden"))
        self.call("PUT", f"/api/admin/contact/{msgs[0]['id']}", {"status": "done"}, self.admin_tok)
        self.assertEqual(self.call("GET", "/api/admin/overview", token=self.admin_tok)[1]["contact_open"], 0)
        # HTML-Formular
        import urllib.parse
        req = urllib.request.Request(self.base + "/kontakt", method="POST", data=urllib.parse.urlencode(
            {**body, "privacy": "1", "email": "max@example.org"}).encode())
        with urllib.request.urlopen(req) as resp:
            self.assertIn("Danke", resp.read().decode())
        # Bremse: höchstens 5 pro Stunde und IP
        for _ in range(5):
            self.call("POST", "/api/contact", body)
        self.assertEqual(self.call("POST", "/api/contact", body)[0], 429)


class WebPagesTest(FeatureCase):
    def test_seiten(self):
        self.upload_app(category="Spiele")
        for path, text in [("/", "Warum ByteDroide"), ("/apps", "Mein Spiel"), ("/apps?sortierung=neu", "Mein Spiel"),
                           ("/hilfe", "Hilfe"), ("/hilfe/entwickler", "Entwickler"), ("/hilfe/ci", "curl"),
                           ("/hilfe/gibtsnicht", "nicht gefunden"), ("/kontakt", "Nachricht senden"),
                           ("/konto", "Mein Konto"), ("/app/anna/spiel", "Fehler gefunden")]:
            status, page = self.call("GET", path, raw=True)
            self.assertEqual(status, 200, path)
            self.assertIn(text, page.decode(), path)
        status, js = self.call("GET", "/static/store.js", raw=True)
        self.assertEqual(status, 200)
        self.assertEqual(self.call("GET", "/static/../store_server.py", raw=True)[0], 404)
        self.assertEqual(self.call("GET", "/static/fehlt.js", raw=True)[0], 404)
        status, view = self.call("GET", "/api/apps/anna/spiel")
        self.assertEqual((status, view["id"]), (200, "anna/spiel"))
        self.assertEqual(self.call("GET", "/portal", raw=True)[0], 200)  # Weiterleitung auf /konto


# ---------------------------------------------------------------------------
# Runde 3: App-Icons aus der APK, Versionen aus Tags, Downloads
# ---------------------------------------------------------------------------

def axml(elements):
    """Binäres XML. elements: [("start", name, [(attr, res_id, raw|None, dtype, data)]) | ("end", name)]."""
    names = []
    for el in elements:
        if el[0] == "start":
            for a in el[2]:
                if a[1] and a[0] not in names:
                    names.append(a[0])
    strings = list(names)

    def idx(text):
        if text not in strings:
            strings.append(text)
        return strings.index(text)
    chunks = []
    for el in elements:
        if el[0] == "start":
            attrs = b""
            for name, _, raw, dtype, data in el[2]:
                raw_i = idx(raw) if raw is not None else 0xFFFFFFFF
                if dtype == 0x03 and raw is not None:
                    data = raw_i
                attrs += struct.pack("<IIIHBBI", 0xFFFFFFFF, idx(name), raw_i, 8, 0, dtype, data)
            body = struct.pack("<IIHHHHHH", 0xFFFFFFFF, idx(el[1]), 20, 20, len(el[2]), 0, 0, 0) + attrs
            chunks.append(struct.pack("<HHIII", 0x0102, 16, 16 + len(body), 1, 0xFFFFFFFF) + body)
        else:
            chunks.append(struct.pack("<HHIIIII", 0x0103, 16, 24, 1, 0xFFFFFFFF, 0xFFFFFFFF, idx(el[1])))
    pool = string_pool(strings)
    resmap = struct.pack("<HHI", 0x0180, 8, 8 + 4 * len(names)) + struct.pack(f"<{len(names)}I", *[
        next(a[1] for el in elements if el[0] == "start" for a in el[2] if a[0] == n) for n in names])
    content = pool + resmap + b"".join(chunks)
    return struct.pack("<HHI", 0x0003, 8, 8 + len(content)) + content


def string_pool(strings):
    data, offsets = b"", []
    for text in strings:
        offsets.append(len(data))
        data += struct.pack("<H", len(text)) + text.encode("utf-16-le") + b"\0\0"
    data += b"\0" * (-len(data) % 4)
    header = 28 + 4 * len(strings)
    return struct.pack("<HHIIIIII", 0x0001, 28, header + len(data), len(strings), 0, 0, header, 0) + \
        struct.pack(f"<{len(strings)}I", *offsets) + data


def arsc(entries):
    """resources.arsc mit Paket 0x7f. entries: {(type_id, entry_idx): [(density, dtype, value)]}; Strings global."""
    paths = []
    types = {}
    for (tid, eid), values in entries.items():
        for density, dtype, value in values:
            if dtype == 0x03:
                paths.append(value)
                value = len(paths) - 1
            types.setdefault((tid, density), {})[eid] = (dtype, value)
    chunks = b""
    for (tid, density), items in types.items():
        count = max(items) + 1
        config = struct.pack("<IHHHHBBH", 64, 0, 0, 0, 0, 0, 0, density).ljust(64, b"\0")
        head = 20 + len(config)
        offsets, body = [], b""
        for i in range(count):
            if i in items:
                offsets.append(len(body))
                dtype, value = items[i]
                body += struct.pack("<HHI", 8, 0, 0) + struct.pack("<HBBI", 8, 0, dtype, value)
            else:
                offsets.append(0xFFFFFFFF)
        start = head + 4 * count
        chunk = struct.pack("<HHIBBHII", 0x0201, head, start + len(body), tid, 0, 0, count, start) + config + \
            struct.pack(f"<{count}I", *offsets) + body
        chunks += chunk
    pkg_head = struct.pack("<HHII", 0x0200, 288, 288 + len(chunks), 0x7F) + b"\0" * 256 + struct.pack("<IIIII", 0, 0, 0, 0, 0)
    pkg = pkg_head + chunks
    pool = string_pool(paths)
    return struct.pack("<HHII", 0x0002, 12, 12 + len(pool) + len(pkg), 1) + pool + pkg


def manifest(package, version, code, icon_id):
    android = "http://schemas.android.com/apk/res/android"
    return axml([
        ("start", "manifest", [("versionCode", 0x0101021B, None, 0x10, code), ("versionName", 0x0101021C, version, 3, 0),
                               ("package", 0, package, 3, 0)]),
        ("start", "application", [("icon", 0x01010002, None, 0x01, icon_id)]),
        ("end", "application"), ("end", "manifest")])


ICON_PNG = b"\x89PNG\r\n\x1a\n" + b"ICON" * 10


def apk_with_icon(package, version, code, vector=False):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("AndroidManifest.xml", manifest(package, version, code, 0x7F010000))
        if vector:
            # adaptive-icon (anydpi) mit Farb-Hintergrund und Vektor-Vordergrund
            zf.writestr("res/ad.xml", axml([
                ("start", "adaptive-icon", []),
                ("start", "background", [("drawable", 0x01010199, None, 0x1D, 0xFF3D5AFE)]), ("end", "background"),
                ("start", "foreground", [("drawable", 0x01010199, None, 0x01, 0x7F020000)]), ("end", "foreground"),
                ("end", "adaptive-icon")]))
            zf.writestr("res/fg.xml", axml([
                ("start", "vector", [("viewportWidth", 0x01010402, None, 0x04, 0x42D80000),
                                     ("viewportHeight", 0x01010403, None, 0x04, 0x42D80000)]),
                ("start", "path", [("fillColor", 0x01010404, None, 0x1C, 0xFFFFFFFF),
                                   ("pathData", 0x01010405, "M30,30h48v48h-48z", 3, 0)]), ("end", "path"),
                ("end", "vector")]))
            zf.writestr("resources.arsc", arsc({(1, 0): [(0xFFFE, 0x03, "res/ad.xml")],
                                                (2, 0): [(0, 0x03, "res/fg.xml")]}))
        else:
            zf.writestr("res/lo.png", b"\x89PNG\r\n\x1a\nKLEIN")
            zf.writestr("res/hi.png", ICON_PNG)
            zf.writestr("res/ad.xml", b"wird ignoriert")
            zf.writestr("resources.arsc", arsc({(1, 0): [(160, 0x03, "res/lo.png"), (640, 0x03, "res/hi.png"),
                                                         (0xFFFE, 0x03, "res/ad.xml")]}))
        zf.writestr("classes.dex", b"dex\n035\0")
    return buf.getvalue()


import io  # noqa: E402
import zipfile  # noqa: E402
import apk_icon  # noqa: E402


class IconTest(FeatureCase):
    def test_icon_aus_apk(self):
        path = os.path.join(self.tmp.name, "i.apk")
        with open(path, "wb") as f:
            f.write(apk_with_icon("com.x.y", "1.0", 1))
        self.assertEqual(apk_icon.extract_icon(path), (ICON_PNG, "png"))  # größte Dichte, Bitmap vor XML
        with open(path, "wb") as f:
            f.write(apk_with_icon("com.x.y", "1.0", 1, vector=True))
        data, ext = apk_icon.extract_icon(path)
        self.assertEqual(ext, "svg")
        svg = data.decode()
        self.assertIn('fill="#3d5afe"', svg)
        self.assertIn('d="M30,30h48v48h-48z"', svg)
        self.assertIn('viewBox="18 18 72 72"', svg)
        with open(path, "wb") as f:
            f.write(make_apk())  # ohne Icon
        self.assertIsNone(apk_icon.extract_icon(path))

    def test_upload_setzt_icon(self):
        self.call("POST", "/api/dev/apps", {"slug": "spiel", "name": "Mein Spiel"}, self.dev)
        self.call("PUT", "/api/admin/apps/anna/spiel", {"review": "approved"}, self.admin_tok)
        self.upload(self.dev, "anna/spiel", apk_with_icon("com.anna.spiel", "1.0.0", 1))
        url = self.apps()["anna/spiel"]["avatar_url"]
        self.assertIn("/api/apps/anna/spiel/icon", url)
        self.assertEqual(self.call("GET", url.replace("https://store.test", ""), raw=True), (200, ICON_PNG))
        # hochgeladenes Icon hat Vorrang und wird von neuen Versionen nicht überschrieben
        self.call("POST", "/api/dev/apps/anna/spiel/icon", data=PNG, token=self.dev)
        self.upload(self.dev, "anna/spiel", apk_with_icon("com.anna.spiel", "1.1.0", 2, vector=True))
        url = self.apps()["anna/spiel"]["avatar_url"]
        self.assertEqual(self.call("GET", url.replace("https://store.test", ""), raw=True), (200, PNG))

    def test_vektor_icon_als_svg(self):
        self.call("POST", "/api/dev/apps", {"slug": "spiel", "name": "Mein Spiel"}, self.dev)
        self.call("PUT", "/api/admin/apps/anna/spiel", {"review": "approved"}, self.admin_tok)
        self.upload(self.dev, "anna/spiel", apk_with_icon("com.anna.spiel", "1.0.0", 1, vector=True))
        url = self.apps()["anna/spiel"]["avatar_url"].replace("https://store.test", "")
        req = urllib.request.Request(self.base + url)
        with urllib.request.urlopen(req) as r:
            self.assertEqual(r.headers["Content-Type"], "image/svg+xml")
            self.assertIn("default-src 'none'", r.headers["Content-Security-Policy"])


class VersionLabelTest(unittest.TestCase):
    def test_version_aus_tag(self):
        self.assertEqual(ss.normalize_version("android-v1.0.24"), "1.0.24")
        self.assertEqual(ss.normalize_version("v2.6.3"), "2.6.3")
        self.assertEqual(ss.normalize_version("1.1.0-beta2"), "1.1.0-beta2")
        self.assertEqual(ss.normalize_version("nightly-2"), "nightly-2")

    def test_downloads(self):
        self.assertEqual([ss.downloads_label(n) for n in (0, 3, 64, 999, 1234)], ["Neu", "1+", "50+", "500+", "1.000+"])
