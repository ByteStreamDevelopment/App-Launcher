"""Virenscan über einen ClamAV-Daemon (clamd, INSTREAM-Protokoll). Nur Standardbibliothek.

Ohne CLAMAV_HOST ist der Scan aus. Ist clamd eingerichtet, aber nicht erreichbar, wird je nach
CLAMAV_REQUIRED abgelehnt (1) oder nur gewarnt (0, Standard).
"""

import logging
import socket
import struct

log = logging.getLogger("store.scan")


class ScanError(Exception):
    pass


class Scanner:
    def __init__(self, host: str = "", port: int = 3310, timeout: int = 120):
        self.host = host
        self.port = port
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.host)

    def scan_stream(self, read_chunk) -> str | None:
        """Schickt Daten an clamd. read_chunk(n) liefert bytes (b"" = Ende).

        Rückgabe: None = sauber, sonst Name des Fundes. ScanError, wenn clamd nicht antwortet.
        """
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                sock.sendall(b"zINSTREAM\0")
                while True:
                    chunk = read_chunk(64 * 1024)
                    if not chunk:
                        break
                    sock.sendall(struct.pack("!I", len(chunk)) + chunk)
                sock.sendall(struct.pack("!I", 0))
                reply = b""
                while not reply.endswith(b"\0"):
                    part = sock.recv(4096)
                    if not part:
                        break
                    reply += part
        except OSError as e:
            raise ScanError(f"ClamAV nicht erreichbar ({e})")
        text = reply.rstrip(b"\0").decode("utf-8", "replace").strip()
        # "stream: OK" | "stream: Eicar-Test-Signature FOUND" | "INSTREAM size limit exceeded. ERROR"
        if text.endswith("OK"):
            return None
        if text.endswith("FOUND"):
            return text.split(":", 1)[-1].replace("FOUND", "").strip() or "Schadsoftware"
        raise ScanError(f"ClamAV-Fehler: {text or 'keine Antwort'}")

    def scan_file(self, path: str) -> str | None:
        with open(path, "rb") as f:
            return self.scan_stream(f.read)
