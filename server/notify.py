"""Push-Benachrichtigungen über ntfy (https://ntfy.sh oder eigener Server) – ohne Google-Dienste.

Jeder Benutzer kann in der App ein (geheimes, zufälliges) Thema hinterlegen und es in der ntfy-App abonnieren.
Versand im Hintergrund, Fehler werden nur geloggt.
"""

import json
import logging
import queue
import threading
import urllib.request

log = logging.getLogger("store.ntfy")


class Pusher:
    def __init__(self, base_url: str = "https://ntfy.sh", token: str = ""):
        self.base_url = (base_url or "").rstrip("/")
        self.token = token
        self._queue: "queue.Queue" = queue.Queue()
        self._thread = None

    @property
    def enabled(self) -> bool:
        return bool(self.base_url)

    def topic_url(self, topic: str) -> str:
        return f"{self.base_url}/{topic}"

    def send(self, topic: str, title: str, message: str, click: str = "", tags=("robot",), priority: int = 3):
        if not topic or not self.enabled:
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._worker, daemon=True, name="ntfy")
            self._thread.start()
        self._queue.put({"topic": topic, "title": title[:250], "message": message[:3500] or title,
                         "click": click, "tags": list(tags), "priority": priority})

    def _worker(self):
        while True:
            payload = self._queue.get()
            try:
                self._deliver(payload)
            except Exception as e:  # nie den Server stören
                log.warning("ntfy an %s fehlgeschlagen: %s", payload["topic"][:6] + "…", e)

    def _deliver(self, payload: dict):
        if not payload.get("click"):
            payload.pop("click", None)
        headers = {"Content-Type": "application/json", "User-Agent": "ByteDroide-Server"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        # JSON-Veröffentlichung an die Basis-URL (UTF-8-sicher, anders als Header)
        req = urllib.request.Request(self.base_url, data=json.dumps(payload).encode(), headers=headers,
                                     method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
