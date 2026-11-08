#!/usr/bin/env python3
"""App-Store-Server.

Sitzt zwischen der Android-App und Forgejo:
- liest die Apps (neuestes Release mit .apk) von Forgejo, auch aus privaten Repos (per Token)
- verwaltet Benutzer, Admins, App-Freigaben (offen / mit Einmal-Code / versteckt) und Einmal-Codes
- liefert APK-Downloads nur an Berechtigte aus

Nur Python-Standardbibliothek. Konfiguration über Umgebungsvariablen (siehe README).
"""

import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
import urllib.error
from contextlib import contextmanager
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

log = logging.getLogger("store")


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        self.forgejo_url = env.get("FORGEJO_URL", "https://git.nebendahl.eu").rstrip("/")
        self.forgejo_token = env.get("FORGEJO_TOKEN", "").strip()
        self.owners = {o.strip().lower() for o in re.split(r"[,; ]+", env.get("OWNERS", "")) if o.strip()}
        self.admin_username = env.get("ADMIN_USERNAME", "ProfImpossible").strip()
        self.admin_password = env.get("ADMIN_PASSWORD", "")
        self.db_path = env.get("DB_PATH", "store.db")
        self.host = env.get("HOST", "0.0.0.0")
        self.port = int(env.get("PORT", "8080"))
        self.catalog_ttl = int(env.get("CATALOG_TTL", "300"))
        self.default_access = env.get("DEFAULT_ACCESS", "open")
        self.trust_proxy = env.get("TRUST_PROXY", "0") == "1"
        if self.default_access not in ACCESS_MODES:
            raise ValueError(f"DEFAULT_ACCESS muss eins von {ACCESS_MODES} sein")


ACCESS_MODES = ("open", "code", "hidden")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # ohne 0/O/1/I


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def now() -> int:
    return int(time.time())


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_code(code: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9]", "", code or "").upper()
    return f"{raw[:4]}-{raw[4:]}" if len(raw) == 8 else raw


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------------------
# Datenbank
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pw_hash     TEXT NOT NULL,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  INTEGER NOT NULL,
    last_used   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS app_access (
    app         TEXT PRIMARY KEY,           -- "owner/repo" in Kleinbuchstaben
    access      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS codes (
    code        TEXT PRIMARY KEY,
    app         TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    created_at  INTEGER NOT NULL,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    used_at     INTEGER,
    used_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    used_by_name TEXT
);
CREATE TABLE IF NOT EXISTS unlocks (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app         TEXT NOT NULL,
    code        TEXT,
    unlocked_at INTEGER NOT NULL,
    PRIMARY KEY (user_id, app)
);
"""


class Database:
    def __init__(self, path: str):
        self.path = path
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Forgejo-Katalog
# ---------------------------------------------------------------------------

class Catalog:
    """Holt Repos + neuestes Release von Forgejo, mit Zwischenspeicher."""

    def __init__(self, config: Config, fetcher=None):
        self.config = config
        self._fetch_json = fetcher or self._http_json
        self._lock = threading.Lock()
        self._apps: dict = {}
        self._fetched_at = 0.0
        self.last_error = None

    def _headers(self) -> dict:
        h = {"Accept": "application/json", "User-Agent": "App-Launcher-Store-Server"}
        if self.config.forgejo_token:
            h["Authorization"] = f"token {self.config.forgejo_token}"
        return h

    def _http_json(self, path: str):
        req = urllib.request.Request(self.config.forgejo_url + path, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def apps(self, force: bool = False) -> dict:
        with self._lock:
            stale = time.time() - self._fetched_at > self.config.catalog_ttl
            if force or stale or not self._apps:
                try:
                    self._apps = self._load()
                    self._fetched_at = time.time()
                    self.last_error = None
                except Exception as e:  # alten Stand behalten
                    log.warning("Katalog konnte nicht geladen werden: %s", e)
                    self.last_error = str(e)
                    if not self._apps:
                        raise HttpError(502, "Forgejo nicht erreichbar")
            return self._apps

    def _load(self) -> dict:
        repos, page = [], 1
        while page <= 20:
            body = self._fetch_json(f"/api/v1/repos/search?limit=50&page={page}") or {}
            data = body.get("data") or []
            repos.extend(data)
            if len(data) < 50:
                break
            page += 1

        def wanted(repo):
            owner = (repo.get("owner") or {}).get("login", "").lower()
            return (repo.get("release_counter", 1) > 0 and not repo.get("empty")
                    and (not self.config.owners or owner in self.config.owners))

        def load_one(repo):
            full = repo["full_name"]
            owner, name = full.split("/", 1)
            rel = self._fetch_json(
                f"/api/v1/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(name)}/releases/latest")
            if not rel:
                return None
            apks = [
                {"name": a.get("name", ""), "size": a.get("size", 0), "url": a.get("browser_download_url", "")}
                for a in rel.get("assets") or []
                if a.get("name", "").lower().endswith(".apk")
            ]
            if not apks:
                return None
            return {
                "id": full,
                "key": full.lower(),
                "owner": owner,
                "name": repo.get("name", name),
                "description": repo.get("description", ""),
                "html_url": repo.get("html_url", ""),
                "private": bool(repo.get("private")),
                "avatar_url": repo.get("avatar_url") or None,
                "release": {
                    "tag": rel.get("tag_name", ""),
                    "name": rel.get("name") or rel.get("tag_name", ""),
                    "notes": rel.get("body", ""),
                    "published_at": rel.get("published_at", ""),
                    "html_url": rel.get("html_url", ""),
                },
                "apks": apks,
            }

        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda r: _safe(load_one, r), [r for r in repos if wanted(r)]))
        return {a["key"]: a for a in results if a}

    def open_download(self, url: str):
        req = urllib.request.Request(url, headers={**self._headers(), "Accept": "*/*"})
        return urllib.request.urlopen(req, timeout=60)


def _safe(fn, arg):
    try:
        return fn(arg)
    except Exception as e:
        log.warning("Repo %s übersprungen: %s", arg.get("full_name"), e)
        return None


# ---------------------------------------------------------------------------
# Fehlversuch-Bremse (gegen Passwort-/Code-Raten)
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self, max_failures: int = 10, window: int = 900):
        self.max_failures = max_failures
        self.window = window
        self._failures: dict = {}
        self._lock = threading.Lock()

    def check(self, key: str):
        with self._lock:
            recent = [t for t in self._failures.get(key, []) if time.time() - t < self.window]
            self._failures[key] = recent
            if len(recent) >= self.max_failures:
                raise HttpError(429, "Zu viele Fehlversuche – bitte in 15 Minuten erneut versuchen")

    def fail(self, key: str):
        with self._lock:
            self._failures.setdefault(key, []).append(time.time())


# ---------------------------------------------------------------------------
# Geschäftslogik
# ---------------------------------------------------------------------------

class Store:
    def __init__(self, config: Config, db: Database, catalog: Catalog):
        self.config = config
        self.db = db
        self.catalog = catalog
        self.limiter = RateLimiter()

    # --- Benutzer & Sitzungen ------------------------------------------------

    def _user_json(self, row) -> dict:
        return {
            "id": row["id"],
            "username": row["username"],
            "is_admin": bool(row["is_admin"]),
            "is_owner": row["username"].lower() == self.config.admin_username.lower(),
        }

    def _new_session(self, conn, user_id: int) -> str:
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO sessions VALUES (?, ?, ?, ?)", (token_hash(token), user_id, now(), now()))
        return token

    def register(self, ip: str, username: str, password: str, admin_password: str = "") -> dict:
        self.limiter.check(ip)
        username = (username or "").strip()
        if not USERNAME_RE.match(username):
            raise HttpError(400, "Benutzername: 3–32 Zeichen, nur Buchstaben, Zahlen, _ . -")
        if len(password or "") < 8:
            raise HttpError(400, "Passwort muss mindestens 8 Zeichen haben")
        is_admin = 0
        if username.lower() == self.config.admin_username.lower():
            if not self.config.admin_password or not hmac.compare_digest(
                    (admin_password or "").encode(), self.config.admin_password.encode()):
                self.limiter.fail(ip)
                raise HttpError(403, "Für diesen Benutzernamen ist das Admin-Passwort nötig")
            is_admin = 1
        with self.db.connect() as conn:
            try:
                cur = conn.execute(
                    "INSERT INTO users (username, pw_hash, is_admin, created_at) VALUES (?, ?, ?, ?)",
                    (username, hash_password(password), is_admin, now()))
            except sqlite3.IntegrityError:
                raise HttpError(409, "Benutzername ist schon vergeben")
            token = self._new_session(conn, cur.lastrowid)
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
        return {"token": token, "user": self._user_json(row)}

    def login(self, ip: str, username: str, password: str) -> dict:
        self.limiter.check(ip)
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", ((username or "").strip(),)).fetchone()
            if not row or not verify_password(password or "", row["pw_hash"]):
                self.limiter.fail(ip)
                raise HttpError(401, "Benutzername oder Passwort falsch")
            token = self._new_session(conn, row["id"])
        return {"token": token, "user": self._user_json(row)}

    def logout(self, token: str):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))

    def user_for_token(self, token):
        if not token:
            return None
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
                (token_hash(token),)).fetchone()
            if row:
                conn.execute("UPDATE sessions SET last_used = ? WHERE token_hash = ?", (now(), token_hash(token)))
        return row

    # --- Apps ----------------------------------------------------------------

    def _access_map(self, conn) -> dict:
        return {r["app"]: r["access"] for r in conn.execute("SELECT * FROM app_access")}

    def _unlocked(self, conn, user) -> set:
        if not user:
            return set()
        return {r["app"] for r in conn.execute("SELECT app FROM unlocks WHERE user_id = ?", (user["id"],))}

    @staticmethod
    def _public_app(app: dict, access: str, unlocked: bool) -> dict:
        return {
            "id": app["id"],
            "owner": app["owner"],
            "name": app["name"],
            "description": app["description"],
            "html_url": app["html_url"],
            "avatar_url": app["avatar_url"],
            "release": app["release"],
            "apks": [{"name": a["name"], "size": a["size"]} for a in app["apks"]],
            "access": access,
            "unlocked": unlocked,
        }

    def list_apps(self, user) -> list:
        apps = self.catalog.apps()
        is_admin = bool(user and user["is_admin"])
        with self.db.connect() as conn:
            access = self._access_map(conn)
            unlocked = self._unlocked(conn, user)
        result = []
        for key, app in apps.items():
            mode = access.get(key, self.config.default_access)
            if mode == "hidden" and not is_admin:
                continue
            allowed = is_admin or mode == "open" or key in unlocked
            result.append(self._public_app(app, mode, allowed))
        return sorted(result, key=lambda a: a["name"].lower())

    def resolve_download(self, user, app_id: str, asset: str):
        key = app_id.lower()
        app = self.catalog.apps().get(key)
        if not app:
            raise HttpError(404, "App nicht gefunden")
        is_admin = bool(user and user["is_admin"])
        with self.db.connect() as conn:
            mode = self._access_map(conn).get(key, self.config.default_access)
            unlocked = key in self._unlocked(conn, user)
        if mode == "hidden" and not is_admin:
            raise HttpError(404, "App nicht gefunden")
        if mode == "code" and not (is_admin or unlocked):
            raise HttpError(403 if user else 401, "Für diese App ist ein Freischalt-Code nötig")
        apk = next((a for a in app["apks"] if a["name"] == asset), app["apks"][0])
        return apk

    def redeem(self, ip: str, user, code: str) -> dict:
        self.limiter.check(ip)
        code = normalize_code(code)
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("SELECT * FROM codes WHERE code = ?", (code,)).fetchone()
            if not row or row["used_at"] is not None:
                conn.execute("ROLLBACK")
                self.limiter.fail(ip)
                raise HttpError(400, "Code ungültig oder schon benutzt")
            conn.execute("UPDATE codes SET used_at = ?, used_by = ?, used_by_name = ? WHERE code = ?",
                         (now(), user["id"], user["username"], code))
            conn.execute("INSERT OR IGNORE INTO unlocks (user_id, app, code, unlocked_at) VALUES (?, ?, ?, ?)",
                         (user["id"], row["app"], code, now()))
            conn.execute("COMMIT")
        app = self.catalog.apps().get(row["app"])
        return {"app": app["id"] if app else row["app"], "name": app["name"] if app else row["app"]}

    # --- Admin: Apps & Codes -------------------------------------------------

    def admin_apps(self, force: bool = False) -> dict:
        apps = self.catalog.apps(force=force)
        with self.db.connect() as conn:
            access = self._access_map(conn)
            code_stats = {r["app"]: (r["open"], r["used"]) for r in conn.execute(
                "SELECT app, SUM(used_at IS NULL) AS open, SUM(used_at IS NOT NULL) AS used FROM codes GROUP BY app")}
            unlock_counts = {r["app"]: r["n"] for r in conn.execute(
                "SELECT app, COUNT(*) AS n FROM unlocks GROUP BY app")}
        result = []
        for key, app in apps.items():
            item = self._public_app(app, access.get(key, self.config.default_access), True)
            open_codes, used_codes = code_stats.get(key, (0, 0))
            item.update(private=app["private"], codes_open=open_codes or 0, codes_used=used_codes or 0,
                        unlocked_users=unlock_counts.get(key, 0))
            result.append(item)
        return {
            "apps": sorted(result, key=lambda a: a["name"].lower()),
            "default_access": self.config.default_access,
            "catalog_error": self.catalog.last_error,
        }

    def _require_app(self, app_id: str) -> dict:
        app = self.catalog.apps().get(app_id.lower())
        if not app:
            raise HttpError(404, "App nicht gefunden")
        return app

    def set_access(self, app_id: str, access: str):
        if access not in ACCESS_MODES:
            raise HttpError(400, "access muss open, code oder hidden sein")
        app = self._require_app(app_id)
        with self.db.connect() as conn:
            conn.execute("INSERT INTO app_access (app, access) VALUES (?, ?) "
                         "ON CONFLICT(app) DO UPDATE SET access = excluded.access", (app["key"], access))
        return {"id": app["id"], "access": access}

    def list_codes(self, app_id: str) -> list:
        app = self._require_app(app_id)
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM codes WHERE app = ? ORDER BY used_at IS NOT NULL, created_at DESC",
                                (app["key"],)).fetchall()
        return [{"code": r["code"], "note": r["note"], "created_at": r["created_at"],
                 "used_at": r["used_at"], "used_by": r["used_by_name"]} for r in rows]

    def create_codes(self, admin, app_id: str, count: int, note: str) -> list:
        app = self._require_app(app_id)
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 1
        if not 1 <= count <= 50:
            raise HttpError(400, "Anzahl muss zwischen 1 und 50 liegen")
        codes = []
        with self.db.connect() as conn:
            while len(codes) < count:
                code = new_code()
                try:
                    conn.execute("INSERT INTO codes (code, app, note, created_at, created_by) VALUES (?, ?, ?, ?, ?)",
                                 (code, app["key"], (note or "")[:100], now(), admin["id"]))
                    codes.append(code)
                except sqlite3.IntegrityError:
                    continue
        return codes

    def delete_code(self, code: str):
        with self.db.connect() as conn:
            if conn.execute("DELETE FROM codes WHERE code = ?", (normalize_code(code),)).rowcount == 0:
                raise HttpError(404, "Code nicht gefunden")

    # --- Admin: Benutzer -----------------------------------------------------

    def list_users(self) -> list:
        apps = self.catalog.apps()
        with self.db.connect() as conn:
            users = conn.execute("SELECT * FROM users ORDER BY is_admin DESC, username COLLATE NOCASE").fetchall()
            unlocks = conn.execute("SELECT user_id, app FROM unlocks").fetchall()
        by_user: dict = {}
        for u in unlocks:
            app = apps.get(u["app"])
            by_user.setdefault(u["user_id"], []).append(
                {"id": app["id"] if app else u["app"], "name": app["name"] if app else u["app"]})
        return [{**self._user_json(u), "created_at": u["created_at"], "unlocked": by_user.get(u["id"], [])}
                for u in users]

    def _target_user(self, conn, user_id: int):
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row:
            raise HttpError(404, "Benutzer nicht gefunden")
        return row

    def set_admin(self, actor, user_id: int, make_admin: bool) -> dict:
        with self.db.connect() as conn:
            target = self._target_user(conn, user_id)
            if not make_admin:
                if target["username"].lower() == self.config.admin_username.lower():
                    raise HttpError(400, f"{self.config.admin_username} bleibt immer Admin")
                admins = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1").fetchone()[0]
                if target["is_admin"] and admins <= 1:
                    raise HttpError(400, "Der letzte Admin kann nicht entfernt werden")
            conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (1 if make_admin else 0, user_id))
            row = self._target_user(conn, user_id)
        return self._user_json(row)

    def delete_user(self, actor, user_id: int):
        with self.db.connect() as conn:
            target = self._target_user(conn, user_id)
            if target["username"].lower() == self.config.admin_username.lower():
                raise HttpError(400, f"{self.config.admin_username} kann nicht gelöscht werden")
            if target["id"] == actor["id"]:
                raise HttpError(400, "Du kannst dich nicht selbst löschen")
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

    def revoke_unlock(self, user_id: int, app_id: str):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM unlocks WHERE user_id = ? AND app = ?", (user_id, app_id.lower()))


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

APP_ID = r"(?P<owner>[^/]+)/(?P<repo>[^/]+)"
ROUTES = []


def route(method: str, pattern: str, auth: str = "none"):
    """auth: none (optional angemeldet), user (Anmeldung nötig), admin."""
    regex = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, regex, auth, fn))
        return fn
    return deco


def app_id(params) -> str:
    return f"{urllib.parse.unquote(params['owner'])}/{urllib.parse.unquote(params['repo'])}"


class Handler(BaseHTTPRequestHandler):
    store: Store = None  # wird in make_server gesetzt
    protocol_version = "HTTP/1.1"
    server_version = "AppStoreServer/1.0"

    def log_message(self, fmt, *args):
        log.info("%s %s", self.client_ip(), fmt % args)

    def client_ip(self) -> str:
        if self.store and self.store.config.trust_proxy:
            fwd = self.headers.get("X-Forwarded-For")
            if fwd:
                return fwd.split(",")[0].strip()
        return self.client_address[0]

    def bearer(self):
        auth = self.headers.get("Authorization", "")
        return auth[7:].strip() if auth.startswith("Bearer ") else None

    def body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 64 * 1024:
            raise HttpError(413, "Anfrage zu groß")
        if not length:
            return {}
        try:
            data = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            raise HttpError(400, "Ungültiges JSON")
        if not isinstance(data, dict):
            raise HttpError(400, "JSON-Objekt erwartet")
        return data

    def send_json(self, status: int, payload):
        data = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def handle_any(self, method: str):
        path = urllib.parse.urlsplit(self.path).path
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        try:
            for m, regex, auth, fn in ROUTES:
                match = regex.match(path)
                if not match or m != method:
                    continue
                user = self.store.user_for_token(self.bearer())
                if auth in ("user", "admin") and not user:
                    raise HttpError(401, "Bitte anmelden")
                if auth == "admin" and not user["is_admin"]:
                    raise HttpError(403, "Nur für Admins")
                result = fn(self, user=user, params=match.groupdict(), query=query)
                if result is not None:
                    self.send_json(200, result)
                return
            raise HttpError(404, "Nicht gefunden")
        except HttpError as e:
            self.send_json(e.status, {"error": e.message})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            log.exception("Fehler bei %s %s", method, path)
            try:
                self.send_json(500, {"error": "Interner Serverfehler"})
            except Exception:
                pass

    def do_GET(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PUT(self):
        self.handle_any("PUT")

    def do_DELETE(self):
        self.handle_any("DELETE")

    # --- Endpunkte -----------------------------------------------------------

    @route("GET", "/healthz")
    def health(self, **_):
        return {"ok": True}

    @route("POST", "/api/register")
    def r_register(self, **_):
        b = self.body()
        return self.store.register(self.client_ip(), b.get("username", ""), b.get("password", ""),
                                   b.get("admin_password", ""))

    @route("POST", "/api/login")
    def r_login(self, **_):
        b = self.body()
        return self.store.login(self.client_ip(), b.get("username", ""), b.get("password", ""))

    @route("POST", "/api/logout", auth="user")
    def r_logout(self, **_):
        self.store.logout(self.bearer())
        return {"ok": True}

    @route("GET", "/api/me", auth="user")
    def r_me(self, user, **_):
        return {"user": self.store._user_json(user)}

    @route("GET", "/api/apps")
    def r_apps(self, user, **_):
        return {"apps": self.store.list_apps(user),
                "user": self.store._user_json(user) if user else None}

    @route("GET", f"/api/apps/{APP_ID}/download")
    def r_download(self, user, params, query, **_):
        apk = self.store.resolve_download(user, app_id(params), query.get("asset", ""))
        try:
            upstream = self.store.catalog.open_download(apk["url"])
        except urllib.error.HTTPError as e:
            raise HttpError(502, f"Forgejo-Download fehlgeschlagen ({e.code})")
        with upstream:
            length = upstream.headers.get("Content-Length")
            self.send_response(200)
            self.send_header("Content-Type", "application/vnd.android.package-archive")
            self.send_header("Content-Disposition", f'attachment; filename="{apk["name"]}"')
            if length:
                self.send_header("Content-Length", length)
            else:
                self.send_header("Connection", "close")
                self.close_connection = True
            self.end_headers()
            while True:
                chunk = upstream.read(64 * 1024)
                if not chunk:
                    break
                self.wfile.write(chunk)
        return None

    @route("POST", "/api/redeem", auth="user")
    def r_redeem(self, user, **_):
        return self.store.redeem(self.client_ip(), user, self.body().get("code", ""))

    # Admin
    @route("GET", "/api/admin/apps", auth="admin")
    def r_admin_apps(self, query, **_):
        return self.store.admin_apps(force=query.get("refresh") == "1")

    @route("PUT", f"/api/admin/apps/{APP_ID}", auth="admin")
    def r_set_access(self, params, **_):
        return self.store.set_access(app_id(params), self.body().get("access", ""))

    @route("GET", f"/api/admin/apps/{APP_ID}/codes", auth="admin")
    def r_codes(self, params, **_):
        return {"codes": self.store.list_codes(app_id(params))}

    @route("POST", f"/api/admin/apps/{APP_ID}/codes", auth="admin")
    def r_new_codes(self, user, params, **_):
        b = self.body()
        return {"codes": self.store.create_codes(user, app_id(params), b.get("count", 1), b.get("note", ""))}

    @route("DELETE", r"/api/admin/codes/(?P<code>[A-Za-z0-9-]+)", auth="admin")
    def r_delete_code(self, params, **_):
        self.store.delete_code(params["code"])
        return {"ok": True}

    @route("GET", "/api/admin/users", auth="admin")
    def r_users(self, **_):
        return {"users": self.store.list_users()}

    @route("PUT", r"/api/admin/users/(?P<id>\d+)", auth="admin")
    def r_set_admin(self, user, params, **_):
        return {"user": self.store.set_admin(user, int(params["id"]), bool(self.body().get("is_admin")))}

    @route("DELETE", r"/api/admin/users/(?P<id>\d+)", auth="admin")
    def r_delete_user(self, user, params, **_):
        self.store.delete_user(user, int(params["id"]))
        return {"ok": True}

    @route("DELETE", rf"/api/admin/users/(?P<id>\d+)/unlocks/{APP_ID}", auth="admin")
    def r_revoke(self, params, **_):
        self.store.revoke_unlock(int(params["id"]), app_id(params))
        return {"ok": True}


def make_server(config: Config, catalog: Catalog = None) -> ThreadingHTTPServer:
    store = Store(config, Database(config.db_path), catalog or Catalog(config))
    handler = type("BoundHandler", (Handler,), {"store": store})
    server = ThreadingHTTPServer((config.host, config.port), handler)
    server.daemon_threads = True
    return server


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = Config()
    if not config.admin_password:
        log.warning("ADMIN_PASSWORD ist nicht gesetzt – %s kann sich nicht registrieren!", config.admin_username)
    if not config.forgejo_token:
        log.warning("FORGEJO_TOKEN ist nicht gesetzt – nur öffentliche Repos sind sichtbar.")
    server = make_server(config)
    log.info("App-Store-Server läuft auf %s:%s (Forgejo: %s)", config.host, config.port, config.forgejo_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
