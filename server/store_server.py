#!/usr/bin/env python3
"""ByteDroide-Server (App Store).

- Konten mit Rollen: Benutzer, Entwickler (vom Admin freizugeben), Admin. Das erste Konto wird automatisch Admin.
- Entwickler veröffentlichen Apps per Quelle (GitHub, Forgejo/Gitea) oder per APK-Upload; neue Apps prüft ein Admin.
- Freigaben pro App: offen / mit Einmal-Code / versteckt, dazu Preis (kostenpflichtig) und Beta-Kanal.
- Optional: automatischer Import aller Forgejo-Repos mit APK-Release (wie bisher).
- E-Mails (Bestätigung, Passwort vergessen, Freigaben, Updates, Kaufbelege …), Rechtstexte, Entwickler-Portal.

Nur Python-Standardbibliothek. Konfiguration über Umgebungsvariablen (siehe README / .env.example).
"""

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import re
import secrets
import socket
import sys
import sqlite3
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import apk_info
import legal
import mailer as mail

log = logging.getLogger("store")
HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Konfiguration
# ---------------------------------------------------------------------------

ACCESS_MODES = ("open", "code", "hidden")
ROLES = ("user", "developer", "admin")
BETA_MODES = ("off", "open", "closed")
CHANNELS = ("stable", "beta")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,39}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
VERSION_RE = re.compile(r"^[A-Za-z0-9._+-]{1,40}$")
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # ohne 0/O/1/I
SESSION_IDLE_DAYS = 90
WITHDRAWAL_DAYS = 14


def _flag(env, name, default="0") -> bool:
    return env.get(name, default).strip().lower() in ("1", "true", "yes", "ja", "on")


class Config:
    def __init__(self, env=None):
        env = os.environ if env is None else env
        g = lambda k, d="": env.get(k, d).strip()  # noqa: E731
        self.public_url = g("PUBLIC_URL", "https://apps.nebendahl.eu").rstrip("/")
        self.forgejo_url = g("FORGEJO_URL", "https://git.nebendahl.eu").rstrip("/")
        self.forgejo_token = g("FORGEJO_TOKEN")
        self.forgejo_auto_import = _flag(env, "FORGEJO_AUTO_IMPORT", "1")
        self.github_token = g("GITHUB_TOKEN")
        self.owners = {o.strip().lower() for o in re.split(r"[,; ]+", g("OWNERS")) if o.strip()}
        self.db_path = g("DB_PATH", "store.db")
        self.data_dir = g("DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(self.db_path)), "files")
        self.host = g("HOST", "0.0.0.0")
        self.port = int(g("PORT", "8080"))
        self.catalog_ttl = int(g("CATALOG_TTL", "300"))
        self.default_access = g("DEFAULT_ACCESS", "open")
        self.trust_proxy = _flag(env, "TRUST_PROXY")
        self.max_upload_mb = int(g("MAX_UPLOAD_MB", "200"))
        self.allow_private_sources = _flag(env, "ALLOW_PRIVATE_SOURCES")
        self.store_app_id = g("STORE_APP_ID")  # z. B. "ProfImpossible/bytedroide" für /download
        # E-Mail
        self.smtp_host = g("SMTP_HOST")
        self.smtp_port = int(g("SMTP_PORT", "587"))
        self.smtp_user = g("SMTP_USER")
        self.smtp_password = env.get("SMTP_PASSWORD", "")
        self.smtp_from = g("SMTP_FROM") or self.smtp_user or "noreply@localhost"
        self.smtp_security = g("SMTP_SECURITY", "starttls").lower()  # starttls | ssl | none
        # Betreiber (Impressum, Datenschutz)
        for key in ("name", "street", "city", "country", "email", "phone", "vat_id", "responsible",
                    "hosting", "mail_provider", "authority"):
            setattr(self, "operator_" + key, g("OPERATOR_" + key.upper()))
        self.kleinunternehmer = _flag(env, "KLEINUNTERNEHMER")
        # Bezahlung
        self.stripe_secret_key = g("STRIPE_SECRET_KEY")
        self.stripe_webhook_secret = g("STRIPE_WEBHOOK_SECRET")
        self.currency = g("CURRENCY", "eur").lower()
        if self.default_access not in ACCESS_MODES:
            raise ValueError(f"DEFAULT_ACCESS muss eins von {ACCESS_MODES} sein")


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


def normalize_version(tag: str) -> str:
    return re.sub(r"^[vV](?=\d)", "", (tag or "").strip())


def format_price(cents: int, currency: str = "eur") -> str:
    symbol = {"eur": "€", "usd": "$", "chf": "CHF", "gbp": "£"}.get(currency, currency.upper())
    return f"{cents // 100},{cents % 100:02d} {symbol}"


def format_ts(ts) -> str:
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(ts or 0))


class HttpError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def parse_source(url: str):
    """Repo-URL -> (Typ, Basis-URL, "owner/repo"). Unterstützt GitHub sowie Forgejo/Gitea/Codeberg."""
    url = (url or "").strip().rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = urllib.parse.urlsplit(url)
    path = [p for p in parts.path.split("/") if p]
    if parts.scheme not in ("http", "https") or not parts.hostname or len(path) < 2:
        raise HttpError(400, "Quelle: bitte die Repo-Adresse angeben, z. B. https://github.com/name/app")
    repo = f"{path[0]}/{path[1]}"
    if parts.hostname.lower() in ("github.com", "www.github.com"):
        return "github", "https://github.com", repo
    return "forgejo", f"{parts.scheme}://{parts.netloc}", repo


def _same_host(a: str, b: str) -> bool:
    return (urllib.parse.urlsplit(a).hostname or "").lower() == (urllib.parse.urlsplit(b).hostname or "").lower()


class _StripAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Authorization-Header nicht an fremde Hosts weitergeben (z. B. GitHub -> S3)."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and not _same_host(req.full_url, newurl):
            new.headers.pop("Authorization", None)
            new.unredirected_hdrs.pop("Authorization", None)
        return new


_opener = urllib.request.build_opener(_StripAuthOnRedirect)


# ---------------------------------------------------------------------------
# Datenbank
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY,
    username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    pw_hash         TEXT NOT NULL,
    created_at      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  INTEGER NOT NULL,
    last_used   INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS tokens (
    token_hash  TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose     TEXT NOT NULL,
    data        TEXT NOT NULL DEFAULT '',
    expires_at  INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS app_access (
    app         TEXT PRIMARY KEY,
    access      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS apps (
    key             TEXT PRIMARY KEY,
    id              TEXT NOT NULL,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL DEFAULT '',
    category        TEXT NOT NULL DEFAULT '',
    homepage        TEXT NOT NULL DEFAULT '',
    developer_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    source_type     TEXT NOT NULL,
    source_url      TEXT NOT NULL DEFAULT '',
    source_repo     TEXT NOT NULL DEFAULT '',
    source_token    TEXT NOT NULL DEFAULT '',
    package_name    TEXT,
    access          TEXT NOT NULL DEFAULT 'open',
    price_cents     INTEGER NOT NULL DEFAULT 0,
    beta            TEXT NOT NULL DEFAULT 'off',
    review          TEXT NOT NULL DEFAULT 'pending',
    review_note     TEXT NOT NULL DEFAULT '',
    icon_path       TEXT,
    notified_tag    TEXT,
    notified_beta   TEXT,
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS releases (
    id              INTEGER PRIMARY KEY,
    app_key         TEXT NOT NULL REFERENCES apps(key) ON DELETE CASCADE,
    version         TEXT NOT NULL,
    version_code    INTEGER,
    notes           TEXT NOT NULL DEFAULT '',
    channel         TEXT NOT NULL DEFAULT 'stable',
    file_name       TEXT NOT NULL,
    size            INTEGER NOT NULL,
    sha256          TEXT NOT NULL,
    path            TEXT NOT NULL,
    created_at      INTEGER NOT NULL
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
CREATE TABLE IF NOT EXISTS beta_testers (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    app         TEXT NOT NULL,
    joined_at   INTEGER NOT NULL,
    PRIMARY KEY (user_id, app)
);
CREATE TABLE IF NOT EXISTS purchases (
    id              INTEGER PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    username        TEXT NOT NULL,
    email           TEXT NOT NULL DEFAULT '',
    app             TEXT NOT NULL,
    app_name        TEXT NOT NULL,
    amount_cents    INTEGER NOT NULL,
    currency        TEXT NOT NULL,
    provider        TEXT NOT NULL,
    provider_ref    TEXT NOT NULL UNIQUE,
    payment_ref     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'paid',
    created_at      INTEGER NOT NULL,
    withdrawn_at    INTEGER
);
CREATE TABLE IF NOT EXISTS downloads (
    id          INTEGER PRIMARY KEY,
    app         TEXT NOT NULL,
    user_id     INTEGER REFERENCES users(id) ON DELETE CASCADE,
    version     TEXT NOT NULL,
    channel     TEXT NOT NULL,
    ts          INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS downloads_app ON downloads(app);
"""

# Spalten, die ältere Datenbanken nachträglich bekommen (Migration ohne Datenverlust).
USER_COLUMNS = {
    "email": "TEXT",
    "email_verified": "INTEGER NOT NULL DEFAULT 0",
    "role": "TEXT NOT NULL DEFAULT 'user'",
    "dev_requested_at": "INTEGER",
    "dev_note": "TEXT NOT NULL DEFAULT ''",
    "notify_updates": "INTEGER NOT NULL DEFAULT 1",
    "notify_news": "INTEGER NOT NULL DEFAULT 0",
    "terms_accepted_at": "INTEGER",
}
SESSION_COLUMNS = {"label": "TEXT"}
UNLOCK_COLUMNS = {"source": "TEXT NOT NULL DEFAULT 'code'"}


class Database:
    def __init__(self, path: str):
        self.path = path
        with self.connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(SCHEMA)
            self._migrate(conn)

    @staticmethod
    def _add_columns(conn, table, columns):
        have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, decl in columns.items():
            if name not in have:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")
        return have

    def _migrate(self, conn):
        had = self._add_columns(conn, "users", USER_COLUMNS)
        if "is_admin" in had and "role" not in had:  # Datenbank aus Version 1.x
            conn.execute("UPDATE users SET role = 'admin' WHERE is_admin = 1")
        self._add_columns(conn, "sessions", SESSION_COLUMNS)
        self._add_columns(conn, "unlocks", UNLOCK_COLUMNS)
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_email ON users(email COLLATE NOCASE) "
                     "WHERE email IS NOT NULL")

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
# Quellen: Forgejo/Gitea und GitHub
# ---------------------------------------------------------------------------

class Sources:
    """Holt Releases von Forgejo/Gitea/GitHub (mit Zwischenspeicher) und öffnet APK-Downloads."""

    def __init__(self, config: Config, fetcher=None):
        self.config = config
        self._fetch = fetcher or self._http_json
        self._lock = threading.Lock()
        self._cache: dict = {}       # app key -> {"at", "sig", "stable", "beta", "error"}
        self.avatars: dict = {}      # app key -> Avatar-URL (Forgejo-Import)
        self.repo_urls: dict = {}    # app key -> Repo-Webadresse
        self.last_discovery = 0.0
        self.last_error = None

    # --- HTTP ---------------------------------------------------------------

    def headers_for(self, base_url: str, token: str = "", github: bool = False, server_token: bool = False) -> dict:
        """server_token: den Forgejo-Token des Servers verwenden – NUR für den automatischen Import.
        Quellen von Entwicklern nutzen ausschließlich deren eigenen Token, sonst könnten sie fremde private
        Repos veröffentlichen."""
        h = {"Accept": "application/vnd.github+json" if github else "application/json",
             "User-Agent": "ByteDroide-Server"}
        if github:
            token = token or self.config.github_token
            if token:
                h["Authorization"] = f"Bearer {token}"
        else:
            if not token and server_token and _same_host(base_url, self.config.forgejo_url):
                token = self.config.forgejo_token
            if token:
                h["Authorization"] = f"token {token}"
        return h

    def _http_json(self, url: str, headers: dict):
        req = urllib.request.Request(url, headers=headers)
        try:
            with _opener.open(req, timeout=20) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise

    def open_download(self, url: str, headers: dict):
        req = urllib.request.Request(url, headers=headers)
        return _opener.open(req, timeout=60)

    def check_url_allowed(self, url: str):
        """Schutz vor Zugriffen auf interne Netze (SSRF) bei vom Entwickler angegebenen Quellen."""
        if self.config.allow_private_sources or _same_host(url, self.config.forgejo_url):
            return
        parts = urllib.parse.urlsplit(url)
        if parts.scheme != "https":
            raise HttpError(400, "Quelle muss per https erreichbar sein")
        try:
            infos = socket.getaddrinfo(parts.hostname, parts.port or 443, proto=socket.IPPROTO_TCP)
        except OSError:
            raise HttpError(400, f"Server {parts.hostname} nicht gefunden")
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise HttpError(400, "Quelle zeigt auf ein internes Netz – nicht erlaubt")

    # --- Releases -----------------------------------------------------------

    def fetch_releases(self, source_type: str, base: str, repo: str, token: str = "") -> dict:
        owner, name = repo.split("/", 1)
        q = lambda s: urllib.parse.quote(s, safe="")  # noqa: E731
        github = source_type == "github"
        if github:
            url = f"https://api.github.com/repos/{q(owner)}/{q(name)}/releases?per_page=15"
        else:
            url = f"{base}/api/v1/repos/{q(owner)}/{q(name)}/releases?limit=15"
        headers = self.headers_for(base, token, github, server_token=source_type == "forgejo_auto")
        data = self._fetch(url, headers)
        if data is None:
            raise HttpError(404, f"Repository {repo} nicht gefunden (privat? dann Token angeben)")
        stable = beta = None
        for rel in data if isinstance(data, list) else []:
            if rel.get("draft"):
                continue
            apks = []
            for a in rel.get("assets") or []:
                if not a.get("name", "").lower().endswith(".apk"):
                    continue
                if github and token:  # private GitHub-Repos: über die API laden
                    fetch = (a.get("url", ""), {**headers, "Accept": "application/octet-stream"})
                else:
                    fetch = (a.get("browser_download_url", ""), {**headers, "Accept": "*/*"})
                apks.append({"name": a["name"], "size": a.get("size", 0), "fetch": fetch})
            if not apks:
                continue
            item = {
                "tag": rel.get("tag_name", ""),
                "name": rel.get("name") or rel.get("tag_name", ""),
                "notes": rel.get("body") or "",
                "published_at": rel.get("published_at") or "",
                "html_url": rel.get("html_url") or "",
                "apks": apks,
            }
            if rel.get("prerelease"):
                if beta is None and stable is None:
                    beta = item
            elif stable is None:
                stable = item
            if stable is not None:
                break
        return {"stable": stable, "beta": beta}

    def cached(self, row) -> dict:
        return self._cache.get(row["key"]) or {}

    def sig(self, row):
        return (row["source_type"], row["source_url"], row["source_repo"], row["source_token"])

    def stale(self, row, force=False) -> bool:
        entry = self._cache.get(row["key"])
        return (force or not entry or entry["sig"] != self.sig(row)
                or time.time() - entry["at"] > self.config.catalog_ttl)

    def refresh(self, row) -> dict:
        try:
            result = self.fetch_releases(row["source_type"], row["source_url"], row["source_repo"],
                                         row["source_token"])
            entry = {**result, "error": None}
        except Exception as e:
            log.warning("Quelle von %s nicht ladbar: %s", row["id"], e)
            old = self._cache.get(row["key"]) or {}
            msg = e.message if isinstance(e, HttpError) else str(e)
            entry = {"stable": old.get("stable"), "beta": old.get("beta"), "error": msg}
        entry.update(at=time.time(), sig=self.sig(row))
        self._cache[row["key"]] = entry
        return entry

    def discover(self) -> list:
        """Forgejo-Repos (für den automatischen Import)."""
        repos, page = [], 1
        headers = self.headers_for(self.config.forgejo_url, server_token=True)
        while page <= 20:
            body = self._fetch(f"{self.config.forgejo_url}/api/v1/repos/search?limit=50&page={page}", headers) or {}
            data = body.get("data") or []
            repos.extend(data)
            if len(data) < 50:
                break
            page += 1
        result = []
        for repo in repos:
            owner = (repo.get("owner") or {}).get("login", "").lower()
            if repo.get("release_counter", 1) > 0 and not repo.get("empty") and (
                    not self.config.owners or owner in self.config.owners):
                result.append(repo)
        return result


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
                raise HttpError(429, "Zu viele Versuche – bitte in 15 Minuten erneut versuchen")

    def fail(self, key: str):
        with self._lock:
            self._failures.setdefault(key, []).append(time.time())


# ---------------------------------------------------------------------------
# Geschäftslogik
# ---------------------------------------------------------------------------

class Store:
    def __init__(self, config: Config, db: Database, sources: Sources, mailer=None, stripe=None):
        self.config = config
        self.db = db
        self.sources = sources
        self.mailer = mailer or mail.Mailer(config)
        self.stripe = stripe or self._stripe_request
        self.limiter = RateLimiter()
        self.signup_limiter = RateLimiter(max_failures=20, window=3600)
        self._refresh_lock = threading.RLock()
        self._last_cleanup = 0.0
        os.makedirs(os.path.join(config.data_dir, "apks"), exist_ok=True)
        os.makedirs(os.path.join(config.data_dir, "icons"), exist_ok=True)

    # --- E-Mails ---------------------------------------------------------------

    def _mail(self, to, subject, reason="", **kw):
        if not to:
            return
        html_body, text = mail.render(self.config, title=subject, reason=reason, **kw)
        self.mailer.send(to, subject, html_body, text)

    def _mail_user(self, user, subject, require_verified=True, **kw):
        if user and user["email"] and (user["email_verified"] or not require_verified):
            self._mail(user["email"], subject, **kw)

    def _mail_admins(self, subject, **kw):
        with self.db.connect() as conn:
            admins = conn.execute("SELECT * FROM users WHERE role = 'admin'").fetchall()
        for a in admins:
            self._mail_user(a, subject, reason="Du erhältst diese E-Mail als Admin von ByteDroide.", **kw)

    def _send_verification(self, conn, user_row, email):
        token = self._new_token(conn, user_row["id"], "verify", 7 * 86400, email)
        self._mail(email, "Bitte bestätige deine E-Mail-Adresse",
                   intro=f"Hallo {user_row['username']}, schön, dass du bei ByteDroide bist!",
                   paragraphs=["Bitte bestätige kurz deine E-Mail-Adresse. Erst dann können wir dir wichtige "
                               "Hinweise, Kaufbelege und auf Wunsch Update-Benachrichtigungen schicken."],
                   button=("E-Mail-Adresse bestätigen", f"{self.config.public_url}/verify?token={token}"),
                   note="Der Link ist 7 Tage gültig. Du hast dich nicht registriert? Dann ignoriere diese E-Mail.",
                   reason="Du erhältst diese E-Mail, weil diese Adresse bei ByteDroide angegeben wurde.")

    # --- Benutzer & Sitzungen ------------------------------------------------

    @staticmethod
    def user_json(row) -> dict:
        role = row["role"]
        return {
            "id": row["id"],
            "username": row["username"],
            "email": row["email"] or "",
            "email_verified": bool(row["email_verified"]),
            "role": role,
            "is_admin": role == "admin",
            "is_developer": role in ("developer", "admin"),
            "dev_requested": row["dev_requested_at"] is not None,
            "notify_updates": bool(row["notify_updates"]),
            "notify_news": bool(row["notify_news"]),
        }

    def _new_session(self, conn, user_id: int, label=None) -> str:
        token = secrets.token_urlsafe(32)
        conn.execute("INSERT INTO sessions (token_hash, user_id, created_at, last_used, label) VALUES (?, ?, ?, ?, ?)",
                     (token_hash(token), user_id, now(), now(), label))
        return token

    def _new_token(self, conn, user_id, purpose, ttl, data="") -> str:
        token = secrets.token_urlsafe(32)
        conn.execute("DELETE FROM tokens WHERE user_id = ? AND purpose = ?", (user_id, purpose))
        conn.execute("INSERT INTO tokens VALUES (?, ?, ?, ?, ?)", (token_hash(token), user_id, purpose, data,
                                                                     now() + ttl))
        return token

    def _take_token(self, conn, token, purpose):
        row = conn.execute("SELECT * FROM tokens WHERE token_hash = ? AND purpose = ?",
                           (token_hash(token or ""), purpose)).fetchone()
        if not row or row["expires_at"] < now():
            return None
        conn.execute("DELETE FROM tokens WHERE token_hash = ?", (row["token_hash"],))
        return row

    @staticmethod
    def _check_password(password):
        if len(password or "") < 8:
            raise HttpError(400, "Passwort muss mindestens 8 Zeichen haben")
        if len(password) > 200:
            raise HttpError(400, "Passwort ist zu lang")

    @staticmethod
    def _check_email(email) -> str:
        email = (email or "").strip()
        if not EMAIL_RE.match(email):
            raise HttpError(400, "Bitte eine gültige E-Mail-Adresse angeben")
        return email

    def register(self, ip: str, b: dict) -> dict:
        self.signup_limiter.check(ip)
        username = (b.get("username") or "").strip()
        if not USERNAME_RE.match(username):
            raise HttpError(400, "Benutzername: 3–32 Zeichen, nur Buchstaben, Zahlen, _ . -")
        email = self._check_email(b.get("email"))
        password = b.get("password") or ""
        self._check_password(password)
        if not b.get("accept_terms"):
            raise HttpError(400, "Bitte den Nutzungsbedingungen zustimmen")
        wants_dev = bool(b.get("developer"))
        note = (b.get("developer_note") or "").strip()[:500]
        self.signup_limiter.fail(ip)  # gegen Massen-Anlage von Konten
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            first = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0
            role = "admin" if first else "user"
            try:
                cur = conn.execute(
                    "INSERT INTO users (username, pw_hash, created_at, email, role, dev_requested_at, dev_note, "
                    "terms_accepted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (username, hash_password(password), now(), email, role,
                     now() if wants_dev and not first else None, note, now()))
            except sqlite3.IntegrityError as e:
                conn.execute("ROLLBACK")
                if "email" in str(e):
                    raise HttpError(409, "Diese E-Mail-Adresse wird schon verwendet")
                raise HttpError(409, "Benutzername ist schon vergeben")
            user_id = cur.lastrowid
            token = self._new_session(conn, user_id)
            conn.execute("COMMIT")
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            self._send_verification(conn, row, email)
        if first:
            log.info("Erstes Konto %s ist Admin", username)
        elif wants_dev:
            self._notify_dev_request(row, note)
        return {"token": token, "user": self.user_json(row), "first_admin": first}

    def _notify_dev_request(self, row, note):
        self._mail_admins("Neue Entwickler-Anfrage",
                          intro=f"{row['username']} möchte Apps in ByteDroide veröffentlichen.",
                          facts=[("Benutzer", row["username"]), ("E-Mail", row["email"] or "–")] +
                                ([("Nachricht", note)] if note else []),
                          paragraphs=["Du kannst die Anfrage in der App unter Admin-Bereich → Anfragen annehmen "
                                      "oder ablehnen."])

    def login(self, ip: str, username: str, password: str) -> dict:
        self.limiter.check(ip)
        login = (username or "").strip()
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ? OR (email = ? COLLATE NOCASE)",
                               (login, login)).fetchone()
            if not row or not verify_password(password or "", row["pw_hash"]):
                self.limiter.fail(ip)
                raise HttpError(401, "Benutzername oder Passwort falsch")
            token = self._new_session(conn, row["id"])
        return {"token": token, "user": self.user_json(row)}

    def logout(self, token: str):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))

    def user_for_token(self, token):
        if not token:
            return None
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT u.*, s.last_used AS s_last_used, s.label AS s_label FROM sessions s "
                "JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?", (token_hash(token),)).fetchone()
            if not row:
                return None
            if row["s_label"] is None and row["s_last_used"] < now() - SESSION_IDLE_DAYS * 86400:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
                return None
            if now() - row["s_last_used"] > 60:
                conn.execute("UPDATE sessions SET last_used = ? WHERE token_hash = ?", (now(), token_hash(token)))
        return row

    def _user(self, conn, user_id):
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

    def update_me(self, user, b: dict) -> dict:
        with self.db.connect() as conn:
            if "notify_updates" in b:
                conn.execute("UPDATE users SET notify_updates = ? WHERE id = ?", (int(bool(b["notify_updates"])),
                                                                                 user["id"]))
            if "notify_news" in b:
                conn.execute("UPDATE users SET notify_news = ? WHERE id = ?", (int(bool(b["notify_news"])), user["id"]))
            if "email" in b and (b["email"] or "").strip().lower() != (user["email"] or "").lower():
                email = self._check_email(b["email"])
                try:
                    conn.execute("UPDATE users SET email = ?, email_verified = 0 WHERE id = ?", (email, user["id"]))
                except sqlite3.IntegrityError:
                    raise HttpError(409, "Diese E-Mail-Adresse wird schon verwendet")
                if user["email"] and user["email_verified"]:
                    self._mail(user["email"], "Deine E-Mail-Adresse wurde geändert",
                               intro=f"Hallo {user['username']}, die E-Mail-Adresse deines Kontos wurde auf "
                                     f"{email} geändert.",
                               paragraphs=["Warst du das nicht? Dann ändere bitte sofort dein Passwort und melde "
                                           "dich bei uns."])
                self._send_verification(conn, self._user(conn, user["id"]), email)
            row = self._user(conn, user["id"])
        return {"user": self.user_json(row)}

    def resend_verification(self, ip, user):
        self.limiter.check(ip)
        self.limiter.fail(ip)
        if user["email_verified"]:
            raise HttpError(400, "Deine E-Mail-Adresse ist schon bestätigt")
        if not user["email"]:
            raise HttpError(400, "Bitte zuerst eine E-Mail-Adresse eintragen")
        with self.db.connect() as conn:
            self._send_verification(conn, user, user["email"])
        return {"ok": True, "mail_enabled": self.mailer.enabled}

    def verify_email(self, token) -> bool:
        with self.db.connect() as conn:
            row = self._take_token(conn, token, "verify")
            if not row:
                return False
            user = self._user(conn, row["user_id"])
            if not user or (user["email"] or "").lower() != row["data"].lower():
                return False
            conn.execute("UPDATE users SET email_verified = 1 WHERE id = ?", (user["id"],))
        return True

    def change_password(self, user, old, new):
        self._check_password(new)
        if not verify_password(old or "", user["pw_hash"]):
            raise HttpError(403, "Aktuelles Passwort ist falsch")
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (hash_password(new), user["id"]))
            # alle anderen App-Sitzungen beenden (API-Schlüssel bleiben)
            conn.execute("DELETE FROM sessions WHERE user_id = ? AND label IS NULL AND last_used < ?",
                         (user["id"], now() - 5))
        self._mail_user(user, "Dein Passwort wurde geändert",
                        intro=f"Hallo {user['username']}, das Passwort deines ByteDroide-Kontos wurde gerade geändert.",
                        paragraphs=["Warst du das nicht? Dann setze dein Passwort über „Passwort vergessen“ zurück "
                                    "und melde dich bei uns."])

    def forgot_password(self, ip, login):
        self.limiter.check(ip)
        self.limiter.fail(ip)
        login = (login or "").strip()
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ? OR (email = ? COLLATE NOCASE)",
                               (login, login)).fetchone()
            if row and row["email"]:
                token = self._new_token(conn, row["id"], "reset", 3600)
                self._mail(row["email"], "Passwort zurücksetzen",
                           intro=f"Hallo {row['username']}, du hast ein neues Passwort für ByteDroide angefordert.",
                           button=("Neues Passwort festlegen", f"{self.config.public_url}/reset?token={token}"),
                           note="Der Link ist eine Stunde gültig. Wenn du das nicht angefordert hast, kannst du "
                                "diese E-Mail ignorieren – dein Passwort bleibt unverändert.")
        # Immer gleiche Antwort (verrät nicht, ob ein Konto existiert)
        return {"ok": True}

    def reset_password(self, token, password) -> str:
        self._check_password(password)
        with self.db.connect() as conn:
            row = self._take_token(conn, token, "reset")
            if not row:
                raise HttpError(400, "Der Link ist ungültig oder abgelaufen. Bitte fordere einen neuen an.")
            conn.execute("UPDATE users SET pw_hash = ?, email_verified = 1 WHERE id = ?",
                         (hash_password(password), row["user_id"]))
            conn.execute("DELETE FROM sessions WHERE user_id = ? AND label IS NULL", (row["user_id"],))
            user = self._user(conn, row["user_id"])
        self._mail_user(user, "Dein Passwort wurde zurückgesetzt",
                        intro=f"Hallo {user['username']}, dein Passwort wurde erfolgreich zurückgesetzt. "
                              "Du kannst dich jetzt in der App neu anmelden.")
        return user["username"]

    def request_developer(self, user, note):
        if user["role"] != "user":
            raise HttpError(400, "Du hast schon Entwickler-Rechte")
        note = (note or "").strip()[:500]
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET dev_requested_at = ?, dev_note = ? WHERE id = ?", (now(), note, user["id"]))
            row = self._user(conn, user["id"])
        self._notify_dev_request(row, note)
        return {"user": self.user_json(row)}

    def delete_me(self, user, password):
        if not verify_password(password or "", user["pw_hash"]):
            raise HttpError(403, "Passwort ist falsch")
        self._delete_user(user["id"])
        self._mail_user(user, "Dein Konto wurde gelöscht",
                        intro=f"Hallo {user['username']}, dein ByteDroide-Konto und die zugehörigen Daten wurden "
                              "gelöscht. Schade, dass du gehst!",
                        paragraphs=["Kaufbelege bewahren wir nur so lange auf, wie es gesetzlich vorgeschrieben ist."])

    def _delete_user(self, user_id):
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            target = self._user(conn, user_id)
            if not target:
                conn.execute("ROLLBACK")
                raise HttpError(404, "Benutzer nicht gefunden")
            if target["role"] == "admin" and conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0] <= 1:
                conn.execute("ROLLBACK")
                raise HttpError(400, "Das letzte Admin-Konto kann nicht gelöscht werden – "
                                     "mache zuerst jemand anderen zum Admin")
            # Apps bleiben erhalten, werden aber versteckt und vom Admin verwaltet
            conn.execute("UPDATE apps SET developer_id = NULL, access = 'hidden' WHERE developer_id = ?", (user_id,))
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.execute("COMMIT")

    def export_me(self, user) -> dict:
        with self.db.connect() as conn:
            q = lambda sql: [dict(r) for r in conn.execute(sql, (user["id"],))]  # noqa: E731
            data = {
                "konto": {**self.user_json(user), "created_at": user["created_at"],
                          "terms_accepted_at": user["terms_accepted_at"]},
                "freischaltungen": q("SELECT app, code, source, unlocked_at FROM unlocks WHERE user_id = ?"),
                "beta_teilnahmen": q("SELECT app, joined_at FROM beta_testers WHERE user_id = ?"),
                "kaeufe": q("SELECT app, app_name, amount_cents, currency, status, created_at FROM purchases "
                            "WHERE user_id = ?"),
                "downloads": q("SELECT app, version, channel, ts FROM downloads WHERE user_id = ?"),
                "eigene_apps": q("SELECT id, name, description, created_at FROM apps WHERE developer_id = ?"),
                "api_schluessel": q("SELECT label, created_at, last_used FROM sessions "
                                    "WHERE user_id = ? AND label IS NOT NULL"),
            }
        data["exportiert_am"] = now()
        return data

    # --- API-Schlüssel (für CI-Uploads) ----------------------------------------

    def list_api_keys(self, user) -> list:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT token_hash, label, created_at, last_used FROM sessions "
                                "WHERE user_id = ? AND label IS NOT NULL ORDER BY created_at DESC", (user["id"],))
            return [{"id": r["token_hash"][:16], "label": r["label"], "created_at": r["created_at"],
                     "last_used": r["last_used"]} for r in rows]

    def create_api_key(self, user, label) -> dict:
        label = (label or "").strip()[:60] or "API-Schlüssel"
        with self.db.connect() as conn:
            if conn.execute("SELECT COUNT(*) FROM sessions WHERE user_id = ? AND label IS NOT NULL",
                            (user["id"],)).fetchone()[0] >= 20:
                raise HttpError(400, "Höchstens 20 API-Schlüssel")
            token = self._new_session(conn, user["id"], label)
        return {"token": token, "label": label}

    def delete_api_key(self, user, key_id):
        with self.db.connect() as conn:
            n = conn.execute("DELETE FROM sessions WHERE user_id = ? AND label IS NOT NULL AND token_hash LIKE ?",
                             (user["id"], re.sub(r"[^0-9a-f]", "", key_id)[:16] + "%")).rowcount
        if not n:
            raise HttpError(404, "Schlüssel nicht gefunden")

    # --- Katalog ---------------------------------------------------------------

    def _app_rows(self, conn):
        return conn.execute("SELECT a.*, u.username AS developer FROM apps a "
                            "LEFT JOIN users u ON u.id = a.developer_id").fetchall()

    def _app_row(self, conn, app_id, retry=True):
        row = conn.execute("SELECT a.*, u.username AS developer FROM apps a LEFT JOIN users u ON u.id = a.developer_id "
                           "WHERE a.key = ?", ((app_id or "").lower(),)).fetchone()
        if not row and retry and self.config.forgejo_auto_import:
            self.refresh_catalog()  # evtl. noch nicht importiertes Forgejo-Repo
            return self._app_row(conn, app_id, retry=False)
        if not row:
            raise HttpError(404, "App nicht gefunden")
        return row

    def refresh_catalog(self, force: bool = False):
        """Importiert neue Forgejo-Repos und aktualisiert Releases der Quell-Apps (mit Zwischenspeicher)."""
        with self._refresh_lock:
            if self.config.forgejo_auto_import and (
                    force or time.time() - self.sources.last_discovery > self.config.catalog_ttl):
                self._import_forgejo()
            with self.db.connect() as conn:
                rows = [r for r in self._app_rows(conn) if r["source_type"] != "upload"]
            todo = [r for r in rows if self.sources.stale(r, force)]
            if todo:
                with ThreadPoolExecutor(max_workers=6) as pool:
                    list(pool.map(self.sources.refresh, todo))
                for row in todo:
                    self._check_new_release(row, self.sources.cached(row))
            if time.time() - self._last_cleanup > 86400:
                self._cleanup()

    def _import_forgejo(self):
        try:
            repos = self.sources.discover()
            self.sources.last_error = None
        except Exception as e:
            log.warning("Forgejo-Import fehlgeschlagen: %s", e)
            self.sources.last_error = str(e)
            self.sources.last_discovery = time.time()
            return
        self.sources.last_discovery = time.time()
        with self.db.connect() as conn:
            known = {r["key"] for r in conn.execute("SELECT key FROM apps")}
            legacy = {r["app"]: r["access"] for r in conn.execute("SELECT * FROM app_access")}
        for repo in repos:
            full = repo.get("full_name", "")
            key = full.lower()
            if "/" not in full:
                continue
            if repo.get("avatar_url"):
                self.sources.avatars[key] = repo["avatar_url"]
            self.sources.repo_urls[key] = repo.get("html_url") or ""
            if key in known:
                continue
            try:
                rel = self.sources.fetch_releases("forgejo_auto", self.config.forgejo_url, full)
            except Exception as e:
                log.warning("Repo %s übersprungen: %s", full, e)
                continue
            if not rel["stable"] and not rel["beta"]:
                continue
            with self.db.connect() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO apps (key, id, name, description, source_type, source_url, source_repo, "
                    "access, review, notified_tag, notified_beta, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, 'forgejo_auto', ?, ?, ?, 'approved', ?, ?, ?, ?)",
                    (key, full, repo.get("name") or full.split("/")[1], repo.get("description") or "",
                     self.config.forgejo_url, full, legacy.get(key, self.config.default_access),
                     (rel["stable"] or {}).get("tag"), (rel["beta"] or {}).get("tag"), now(), now()))
                row = self._app_row(conn, key, retry=False)
            self.sources._cache[key] = {**rel, "error": None, "at": time.time(), "sig": self.sources.sig(row)}

    def _cleanup(self):
        self._last_cleanup = time.time()
        with self.db.connect() as conn:
            conn.execute("DELETE FROM downloads WHERE ts < ?", (now() - 365 * 86400,))
            conn.execute("DELETE FROM tokens WHERE expires_at < ?", (now(),))
            conn.execute("DELETE FROM sessions WHERE label IS NULL AND last_used < ?",
                         (now() - SESSION_IDLE_DAYS * 86400,))

    def _upload_releases(self, conn, key) -> dict:
        rows = conn.execute("SELECT * FROM releases WHERE app_key = ? ORDER BY created_at DESC, id DESC",
                            (key,)).fetchall()
        stable = beta = None
        for r in rows:
            item = {"tag": r["version"], "name": r["version"], "notes": r["notes"],
                    "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(r["created_at"])),
                    "html_url": "", "release_id": r["id"],
                    "apks": [{"name": r["file_name"], "size": r["size"], "path": r["path"]}]}
            if r["channel"] == "beta":
                if beta is None and stable is None:
                    beta = item
            elif stable is None:
                stable = item
                break
        return {"stable": stable, "beta": beta}

    def _releases(self, conn, row) -> dict:
        if row["source_type"] == "upload":
            return self._upload_releases(conn, row["key"])
        c = self.sources.cached(row)
        return {"stable": c.get("stable"), "beta": c.get("beta")}

    def _user_sets(self, conn, user):
        if not user:
            return set(), set()
        unl = {r["app"] for r in conn.execute("SELECT app FROM unlocks WHERE user_id = ?", (user["id"],))}
        beta = {r["app"] for r in conn.execute("SELECT app FROM beta_testers WHERE user_id = ?", (user["id"],))}
        return unl, beta

    @staticmethod
    def can_manage(user, row) -> bool:
        return bool(user) and (user["role"] == "admin" or (
            user["role"] in ("developer", "admin") and row["developer_id"] == user["id"]))

    def _icon_url(self, row):
        if row["icon_path"]:
            return f"{self.config.public_url}/api/apps/{row['id']}/icon?v={os.path.basename(row['icon_path'])[:8]}"
        return self.sources.avatars.get(row["key"])

    def _html_url(self, row):
        if row["source_type"] == "upload":
            return row["homepage"]
        if row["source_type"] == "github":
            return f"https://github.com/{row['source_repo']}"
        return self.sources.repo_urls.get(row["key"]) or f"{row['source_url']}/{row['source_repo']}"

    def _view(self, row, rels, user, unlocks, betas):
        """App aus Sicht des Benutzers – None, wenn sie für ihn unsichtbar ist."""
        manage = self.can_manage(user, row)
        if not manage and (row["review"] != "approved" or row["access"] == "hidden"):
            return None
        joined = row["key"] in betas
        beta_rel = rels["beta"] if row["beta"] != "off" else None
        use_beta = beta_rel is not None and (joined or (manage and rels["stable"] is None))
        rel = beta_rel if use_beta else rels["stable"]
        if rel is None:
            return None
        paid = row["price_cents"] > 0
        needs_unlock = row["access"] == "code" or paid
        unlocked = manage or not needs_unlock or row["key"] in unlocks
        owner = row["developer"] or row["id"].split("/")[0]
        return {
            "id": row["id"],
            "owner": owner,
            "developer": row["developer"],
            "name": row["name"],
            "description": row["description"],
            "category": row["category"],
            "homepage": row["homepage"],
            "html_url": self._html_url(row),
            "avatar_url": self._icon_url(row),
            "release": {"tag": rel["tag"], "name": rel["name"], "notes": rel["notes"],
                        "published_at": rel["published_at"], "html_url": rel["html_url"],
                        "channel": "beta" if use_beta else "stable"},
            "apks": [{"name": a["name"], "size": a["size"]} for a in rel["apks"]],
            "access": row["access"],
            "price_cents": row["price_cents"],
            "currency": self.config.currency,
            "price": format_price(row["price_cents"], self.config.currency) if paid else "",
            "can_buy": paid and bool(self.config.stripe_secret_key),
            "unlocked": unlocked,
            "beta": {
                "mode": row["beta"],
                "available": beta_rel is not None,
                "joined": joined,
                "version": beta_rel["tag"] if beta_rel else "",
            },
            "review": row["review"],
            "can_manage": manage,
        }

    def list_apps(self, user) -> list:
        self.refresh_catalog()
        with self.db.connect() as conn:
            unlocks, betas = self._user_sets(conn, user)
            result = []
            for row in self._app_rows(conn):
                view = self._view(row, self._releases(conn, row), user, unlocks, betas)
                if view:
                    result.append(view)
        return sorted(result, key=lambda a: a["name"].lower())

    def app_for(self, user, app_id):
        self.refresh_catalog()
        with self.db.connect() as conn:
            row = self._app_row(conn, app_id)
            unlocks, betas = self._user_sets(conn, user)
            view = self._view(row, self._releases(conn, row), user, unlocks, betas)
        if not view:
            raise HttpError(404, "App nicht gefunden")
        return row, view

    def resolve_download(self, user, app_id: str, asset: str):
        self.refresh_catalog()
        with self.db.connect() as conn:
            row = self._app_row(conn, app_id)
            unlocks, betas = self._user_sets(conn, user)
            rels = self._releases(conn, row)
            view = self._view(row, rels, user, unlocks, betas)
            if not view:
                raise HttpError(404, "App nicht gefunden")
            if not view["unlocked"]:
                if not user:
                    raise HttpError(401, "Bitte zuerst anmelden")
                if row["price_cents"] > 0:
                    raise HttpError(402, f"Diese App kostet {view['price']} – bitte zuerst kaufen")
                raise HttpError(403, "Für diese App ist ein Freischalt-Code nötig")
            channel = view["release"]["channel"]
            rel = rels[channel]
            apk = next((a for a in rel["apks"] if a["name"] == asset), rel["apks"][0])
            conn.execute("INSERT INTO downloads (app, user_id, version, channel, ts) VALUES (?, ?, ?, ?, ?)",
                         (row["key"], user["id"] if user else None, rel["tag"], channel, now()))
        return apk

    # --- Benachrichtigung bei neuen Versionen --------------------------------

    def _check_new_release(self, row, rels):
        for channel, column in (("stable", "notified_tag"), ("beta", "notified_beta")):
            rel = rels.get(channel)
            if not rel or rel["tag"] == row[column]:
                continue
            with self.db.connect() as conn:
                conn.execute(f"UPDATE apps SET {column} = ? WHERE key = ?", (rel["tag"], row["key"]))
            if row[column] is not None:  # beim ersten Mal nur merken
                self._notify_release(row, rel, channel)

    def _notify_release(self, row, rel, channel):
        if row["review"] != "approved" or row["access"] == "hidden":
            return
        with self.db.connect() as conn:
            if channel == "beta":
                if row["beta"] == "off":
                    return
                users = conn.execute(
                    "SELECT u.* FROM beta_testers b JOIN users u ON u.id = b.user_id "
                    "WHERE b.app = ? AND u.notify_updates = 1 AND u.email_verified = 1", (row["key"],)).fetchall()
            else:
                users = conn.execute(
                    "SELECT DISTINCT u.* FROM downloads d JOIN users u ON u.id = d.user_id "
                    "WHERE d.app = ? AND u.notify_updates = 1 AND u.email_verified = 1", (row["key"],)).fetchall()
            unlocked = {r["user_id"] for r in conn.execute("SELECT user_id FROM unlocks WHERE app = ?", (row["key"],))}
        needs_unlock = row["access"] == "code" or row["price_cents"] > 0
        notes = (rel["notes"] or "").strip()
        if len(notes) > 600:
            notes = notes[:600].rsplit(" ", 1)[0] + " …"
        version = normalize_version(rel["tag"])
        for u in users:
            if needs_unlock and u["id"] not in unlocked and u["role"] != "admin":
                continue
            beta = channel == "beta"
            self._mail_user(
                u, f"{'Neue Beta' if beta else 'Update'}: {row['name']} {version}",
                intro=f"Hallo {u['username']}, für {row['name']} gibt es eine neue "
                      f"{'Beta-Version' if beta else 'Version'}: {version}.",
                paragraphs=[notes] if notes else ["Öffne ByteDroide und tippe auf „Aktualisieren“."],
                button=("In ByteDroide ansehen", f"{self.config.public_url}/app/{row['id']}"),
                reason="Du erhältst diese E-Mail, weil du Update-Benachrichtigungen eingeschaltet hast. "
                       "Abschalten: ByteDroide → Konto → Benachrichtigungen.")

    # --- Einmal-Codes ------------------------------------------------------------

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
            conn.execute("INSERT OR IGNORE INTO unlocks (user_id, app, code, unlocked_at, source) "
                         "VALUES (?, ?, ?, ?, 'code')", (user["id"], row["app"], code, now()))
            conn.execute("COMMIT")
            app = conn.execute("SELECT id, name FROM apps WHERE key = ?", (row["app"],)).fetchone()
        return {"app": app["id"] if app else row["app"], "name": app["name"] if app else row["app"]}

    def list_codes(self, app_id: str) -> list:
        with self.db.connect() as conn:
            row = self._app_row(conn, app_id)
            rows = conn.execute("SELECT * FROM codes WHERE app = ? ORDER BY used_at IS NOT NULL, created_at DESC",
                                (row["key"],)).fetchall()
        return [{"code": r["code"], "note": r["note"], "created_at": r["created_at"],
                 "used_at": r["used_at"], "used_by": r["used_by_name"]} for r in rows]

    def create_codes(self, actor, app_id: str, count, note: str) -> list:
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 1
        if not 1 <= count <= 50:
            raise HttpError(400, "Anzahl muss zwischen 1 und 50 liegen")
        codes = []
        with self.db.connect() as conn:
            row = self._app_row(conn, app_id)
            while len(codes) < count:
                code = new_code()
                try:
                    conn.execute("INSERT INTO codes (code, app, note, created_at, created_by) VALUES (?, ?, ?, ?, ?)",
                                 (code, row["key"], (note or "")[:100], now(), actor["id"]))
                    codes.append(code)
                except sqlite3.IntegrityError:
                    continue
        return codes

    def delete_code(self, actor, code: str):
        with self.db.connect() as conn:
            row = conn.execute("SELECT c.code, a.developer_id FROM codes c LEFT JOIN apps a ON a.key = c.app "
                               "WHERE c.code = ?", (normalize_code(code),)).fetchone()
            if not row:
                raise HttpError(404, "Code nicht gefunden")
            if actor["role"] != "admin" and row["developer_id"] != actor["id"]:
                raise HttpError(403, "Nicht deine App")
            conn.execute("DELETE FROM codes WHERE code = ?", (row["code"],))

    # --- Beta ------------------------------------------------------------------

    def set_beta(self, user, app_id, join: bool) -> dict:
        row, view = self.app_for(user, app_id)
        with self.db.connect() as conn:
            if join:
                if row["beta"] == "off":
                    raise HttpError(400, "Für diese App gibt es kein Beta-Programm")
                if row["beta"] == "closed" and not self.can_manage(user, row):
                    raise HttpError(403, "Das Beta-Programm ist geschlossen – nur auf Einladung")
                conn.execute("INSERT OR IGNORE INTO beta_testers VALUES (?, ?, ?)", (user["id"], row["key"], now()))
            else:
                conn.execute("DELETE FROM beta_testers WHERE user_id = ? AND app = ?", (user["id"], row["key"]))
        return {"joined": join}

    def list_testers(self, app_id) -> list:
        with self.db.connect() as conn:
            row = self._app_row(conn, app_id)
            return [{"id": r["id"], "username": r["username"], "joined_at": r["joined_at"]} for r in conn.execute(
                "SELECT u.id, u.username, b.joined_at FROM beta_testers b JOIN users u ON u.id = b.user_id "
                "WHERE b.app = ? ORDER BY b.joined_at DESC", (row["key"],))]

    def add_tester(self, app_id, username):
        with self.db.connect() as conn:
            row = self._app_row(conn, app_id)
            user = conn.execute("SELECT * FROM users WHERE username = ?", ((username or "").strip(),)).fetchone()
            if not user:
                raise HttpError(404, "Benutzer nicht gefunden")
            conn.execute("INSERT OR IGNORE INTO beta_testers VALUES (?, ?, ?)", (user["id"], row["key"], now()))
        self._mail_user(user, f"Einladung zur Beta von {row['name']}",
                        intro=f"Hallo {user['username']}, du wurdest eingeladen, die Beta-Version von "
                              f"{row['name']} zu testen.",
                        paragraphs=["In ByteDroide bekommst du ab sofort die neuesten Vorabversionen dieser App. "
                                    "Beta-Versionen können Fehler enthalten – Feedback hilft dem Entwickler sehr!",
                                    "Du kannst die Teilnahme jederzeit auf der App-Seite beenden."],
                        button=("App ansehen", f"{self.config.public_url}/app/{row['id']}"))

    def remove_tester(self, app_id, user_id):
        with self.db.connect() as conn:
            row = self._app_row(conn, app_id)
            conn.execute("DELETE FROM beta_testers WHERE user_id = ? AND app = ?", (user_id, row["key"]))

    # --- Entwickler: Apps -------------------------------------------------------

    def _require_manage(self, user, app_id):
        with self.db.connect() as conn:
            row = self._app_row(conn, app_id)
        if not self.can_manage(user, row):
            raise HttpError(403, "Nicht deine App")
        return row

    def _dev_view(self, conn, row) -> dict:
        rels = self._releases(conn, row)
        c = self.sources.cached(row) if row["source_type"] != "upload" else {}
        key = row["key"]
        stats = conn.execute(
            "SELECT COUNT(*) AS n, COUNT(DISTINCT user_id) AS users, SUM(ts > ?) AS recent FROM downloads WHERE app = ?",
            (now() - 30 * 86400, key)).fetchone()
        sales = conn.execute("SELECT COUNT(*) AS n, COALESCE(SUM(amount_cents), 0) AS total FROM purchases "
                             "WHERE app = ? AND status != 'refunded'", (key,)).fetchone()
        codes = conn.execute("SELECT SUM(used_at IS NULL) AS open, SUM(used_at IS NOT NULL) AS used FROM codes "
                             "WHERE app = ?", (key,)).fetchone()
        testers = conn.execute("SELECT COUNT(*) FROM beta_testers WHERE app = ?", (key,)).fetchone()[0]
        unlocked = conn.execute("SELECT COUNT(*) FROM unlocks WHERE app = ?", (key,)).fetchone()[0]
        source = "" if row["source_type"] == "upload" else self._html_url(row)
        return {
            "id": row["id"], "name": row["name"], "description": row["description"], "category": row["category"],
            "homepage": row["homepage"], "developer": row["developer"], "source_type": row["source_type"],
            "source_url": source, "has_source_token": bool(row["source_token"]), "package_name": row["package_name"],
            "access": row["access"], "price_cents": row["price_cents"], "beta": row["beta"],
            "review": row["review"], "review_note": row["review_note"], "avatar_url": self._icon_url(row),
            "stable": (rels["stable"] or {}).get("tag"), "beta_version": (rels["beta"] or {}).get("tag"),
            "source_error": c.get("error"),
            "downloads": stats["n"], "downloads_30d": stats["recent"] or 0, "download_users": stats["users"],
            "sales": sales["n"], "revenue_cents": sales["total"], "currency": self.config.currency,
            "codes_open": codes["open"] or 0, "codes_used": codes["used"] or 0, "testers": testers,
            "unlocked_users": unlocked, "created_at": row["created_at"],
        }

    def dev_apps(self, user, all_apps=False) -> list:
        if all_apps:
            self.refresh_catalog()
        with self.db.connect() as conn:
            rows = [r for r in self._app_rows(conn) if all_apps or r["developer_id"] == user["id"]]
            return sorted((self._dev_view(conn, r) for r in rows), key=lambda a: a["name"].lower())

    def dev_app(self, user, app_id) -> dict:
        row = self._require_manage(user, app_id)
        with self.db.connect() as conn:
            return self._dev_view(conn, row)

    def _apply_fields(self, b: dict, fields: dict, user, row=None):
        """Prüft änderbare Felder und schreibt sie nach fields."""
        if "name" in b:
            name = (b["name"] or "").strip()
            if not 1 <= len(name) <= 60:
                raise HttpError(400, "Name: 1–60 Zeichen")
            fields["name"] = name
        if "description" in b:
            fields["description"] = (b["description"] or "").strip()[:4000]
        if "category" in b:
            fields["category"] = (b["category"] or "").strip()[:40]
        if "homepage" in b:
            hp = (b["homepage"] or "").strip()[:300]
            if hp and not hp.startswith(("https://", "http://")):
                raise HttpError(400, "Webseite muss mit https:// beginnen")
            fields["homepage"] = hp
        if "access" in b:
            if b["access"] not in ACCESS_MODES:
                raise HttpError(400, "access muss open, code oder hidden sein")
            fields["access"] = b["access"]
        if "beta" in b:
            if b["beta"] not in BETA_MODES:
                raise HttpError(400, "beta muss off, open oder closed sein")
            fields["beta"] = b["beta"]
        if "price_cents" in b:
            try:
                price = int(b["price_cents"] or 0)
            except (TypeError, ValueError):
                raise HttpError(400, "Preis ungültig")
            if price != 0 and not 50 <= price <= 100000:
                raise HttpError(400, "Preis: 0 (kostenlos) oder 0,50 € bis 1000 €")
            fields["price_cents"] = price
        if "source_token" in b and b["source_token"] is not None:
            fields["source_token"] = (b["source_token"] or "").strip()[:200]
        if b.get("source_url"):
            stype, base, repo = parse_source(b["source_url"])
            self.sources.check_url_allowed(base)
            token = fields.get("source_token", row["source_token"] if row else "")
            try:
                rel = self.sources.fetch_releases(stype, base, repo, token)
            except HttpError:
                raise
            except Exception as e:
                raise HttpError(400, f"Quelle nicht erreichbar: {e}")
            if not rel["stable"] and not rel["beta"]:
                raise HttpError(400, "In der Quelle wurde kein Release mit .apk-Datei gefunden")
            fields.update(source_type=stype, source_url=base, source_repo=repo)

    def create_app(self, user, b: dict) -> dict:
        slug = (b.get("slug") or "").strip().lower()
        if not SLUG_RE.match(slug):
            raise HttpError(400, "Kurzname: 2–40 Zeichen, nur a–z, 0–9 und Bindestrich")
        fields = {"source_type": "upload"}
        self._apply_fields({"name": b.get("name", ""), **b}, fields, user)
        if fields.get("source_type") == "upload" and fields.get("source_token"):
            fields["source_token"] = ""
        app_id = f"{user['username']}/{slug}"
        review = "approved" if user["role"] == "admin" else "pending"
        cols = {"key": app_id.lower(), "id": app_id, "developer_id": user["id"], "review": review,
                "created_at": now(), "updated_at": now(), **fields}
        with self.db.connect() as conn:
            try:
                conn.execute(f"INSERT INTO apps ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                             list(cols.values()))
            except sqlite3.IntegrityError:
                raise HttpError(409, "Es gibt schon eine App mit diesem Kurznamen")
            row = self._app_row(conn, app_id)
        if row["source_type"] != "upload":
            self.sources.refresh(row)
            self._check_new_release(row, self.sources.cached(row))
        if review == "pending":
            self._notify_review_needed(row, user)
        return self.dev_app(user, app_id)

    def _notify_review_needed(self, row, user):
        self._mail_admins(f"Neue App zur Prüfung: {row['name']}",
                          intro=f"{user['username']} hat die App „{row['name']}“ eingereicht.",
                          facts=[("App", row["id"]), ("Quelle", "Upload" if row["source_type"] == "upload"
                                                       else f"{row['source_url']}/{row['source_repo']}"),
                                 ("Preis", format_price(row["price_cents"], self.config.currency)
                                  if row["price_cents"] else "kostenlos")],
                          paragraphs=["Bitte prüfe die App in ByteDroide unter Admin-Bereich → Anfragen."])

    def update_app(self, user, app_id, b: dict) -> dict:
        row = self._require_manage(user, app_id)
        fields = {}
        self._apply_fields(b, fields, user, row)
        if b.get("source_url") == "" and row["source_type"] != "upload":
            raise HttpError(400, "Die Quelle kann nicht entfernt werden – lege dafür eine neue App an")
        if fields.get("source_type") and row["source_type"] == "upload":
            raise HttpError(400, "Upload-Apps können nicht auf eine Quelle umgestellt werden")
        if row["source_type"] == "forgejo_auto":
            fields.pop("source_type", None)
        if fields:
            fields["updated_at"] = now()
            with self.db.connect() as conn:
                conn.execute(f"UPDATE apps SET {', '.join(k + ' = ?' for k in fields)} WHERE key = ?",
                             [*fields.values(), row["key"]])
        return self.dev_app(user, app_id)

    def delete_app(self, user, app_id):
        row = self._require_manage(user, app_id)
        with self.db.connect() as conn:
            paths = [r["path"] for r in conn.execute("SELECT path FROM releases WHERE app_key = ?", (row["key"],))]
            conn.execute("DELETE FROM apps WHERE key = ?", (row["key"],))
            for table in ("codes", "unlocks", "beta_testers"):
                conn.execute(f"DELETE FROM {table} WHERE app = ?", (row["key"],))
        for p in paths + ([row["icon_path"]] if row["icon_path"] else []):
            try:
                os.remove(os.path.join(self.config.data_dir, p))
            except OSError:
                pass
        if row["source_type"] == "forgejo_auto":
            log.info("Forgejo-App %s gelöscht – wird beim nächsten Import wieder angelegt, falls OWNERS passt",
                     row["id"])

    def list_releases(self, user, app_id) -> list:
        row = self._require_manage(user, app_id)
        with self.db.connect() as conn:
            return [{"id": r["id"], "version": r["version"], "version_code": r["version_code"], "notes": r["notes"],
                     "channel": r["channel"], "file_name": r["file_name"], "size": r["size"], "sha256": r["sha256"],
                     "created_at": r["created_at"]}
                    for r in conn.execute("SELECT * FROM releases WHERE app_key = ? ORDER BY created_at DESC, id DESC",
                                          (row["key"],))]

    def add_release(self, user, app_id, tmp_path, size, sha256, version, channel, notes) -> dict:
        row = self._require_manage(user, app_id)
        if row["source_type"] != "upload":
            raise HttpError(400, "Diese App bezieht ihre Versionen aus der Quelle – dort ein Release anlegen")
        if channel not in CHANNELS:
            raise HttpError(400, "Kanal muss stable oder beta sein")
        try:
            info = apk_info.read_apk_info(tmp_path)
        except apk_info.ApkError as e:
            raise HttpError(400, str(e))
        apk_version = info["version_name"]
        version = (version or "").strip()
        if not version:
            if not apk_version:
                raise HttpError(400, "Version konnte nicht aus der APK gelesen werden – bitte angeben")
            version = apk_version
        if not VERSION_RE.match(version):
            raise HttpError(400, "Version: z. B. 1.2.0 (Buchstaben, Zahlen, . _ + -)")
        if apk_version and normalize_version(version) != normalize_version(apk_version):
            raise HttpError(400, f"Version {version} passt nicht zum versionName der APK ({apk_version}). "
                                 "Sonst erkennt die App Updates nicht richtig.")
        if row["package_name"] and info["package"] != row["package_name"]:
            raise HttpError(400, f"Falsche App: Paket {info['package']} statt {row['package_name']}")
        with self.db.connect() as conn:
            other = conn.execute("SELECT key FROM apps WHERE package_name = ? AND key != ?",
                                 (info["package"], row["key"])).fetchone()
            if other:
                raise HttpError(409, "Dieses Paket gehört schon zu einer anderen App im Store")
            last = conn.execute("SELECT MAX(version_code) FROM releases WHERE app_key = ?", (row["key"],)).fetchone()[0]
            if last is not None and info["version_code"] is not None and info["version_code"] <= last:
                raise HttpError(400, f"versionCode {info['version_code']} muss größer sein als beim letzten Upload "
                                     f"({last}), sonst installiert Android das Update nicht")
            if conn.execute("SELECT 1 FROM releases WHERE app_key = ? AND version = ? AND channel = ?",
                            (row["key"], version, channel)).fetchone():
                raise HttpError(409, f"Version {version} gibt es in diesem Kanal schon")
            rel_path = os.path.join("apks", f"{row['key'].replace('/', '_')}-{sha256[:12]}.apk")
            os.replace(tmp_path, os.path.join(self.config.data_dir, rel_path))
            suffix = "-beta" if channel == "beta" and "beta" not in version.lower() else ""
            file_name = f"{row['key'].split('/')[1]}-{normalize_version(version)}{suffix}.apk"
            cur = conn.execute(
                "INSERT INTO releases (app_key, version, version_code, notes, channel, file_name, size, sha256, path, "
                "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row["key"], version, info["version_code"], (notes or "").strip()[:4000], channel, file_name, size,
                 sha256, rel_path, now()))
            conn.execute("UPDATE apps SET package_name = ?, updated_at = ? WHERE key = ?",
                         (info["package"], now(), row["key"]))
            rels = self._upload_releases(conn, row["key"])
            row = self._app_row(conn, row["key"])
        self._check_new_release(row, rels)
        return {"id": cur.lastrowid, "version": version, "version_code": info["version_code"],
                "package": info["package"], "channel": channel, "size": size, "sha256": sha256}

    def delete_release(self, user, app_id, release_id):
        row = self._require_manage(user, app_id)
        with self.db.connect() as conn:
            rel = conn.execute("SELECT * FROM releases WHERE id = ? AND app_key = ?", (release_id, row["key"])).fetchone()
            if not rel:
                raise HttpError(404, "Version nicht gefunden")
            conn.execute("DELETE FROM releases WHERE id = ?", (release_id,))
        try:
            os.remove(os.path.join(self.config.data_dir, rel["path"]))
        except OSError:
            pass

    def set_icon(self, user, app_id, data: bytes):
        row = self._require_manage(user, app_id)
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            ext = "png"
        elif data.startswith(b"\xff\xd8\xff"):
            ext = "jpg"
        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            ext = "webp"
        else:
            raise HttpError(400, "Icon muss PNG, JPEG oder WebP sein")
        path = os.path.join("icons", f"{hashlib.sha256(data).hexdigest()[:24]}.{ext}")
        with open(os.path.join(self.config.data_dir, path), "wb") as f:
            f.write(data)
        with self.db.connect() as conn:
            conn.execute("UPDATE apps SET icon_path = ?, updated_at = ? WHERE key = ?", (path, now(), row["key"]))
        if row["icon_path"] and row["icon_path"] != path:
            try:
                os.remove(os.path.join(self.config.data_dir, row["icon_path"]))
            except OSError:
                pass
        return {"avatar_url": f"{self.config.public_url}/api/apps/{row['id']}/icon?v={os.path.basename(path)[:8]}"}

    # --- Admin -----------------------------------------------------------------

    def admin_apps(self, force=False, user=None) -> dict:
        if force:
            self.refresh_catalog(force=True)
        apps = self.dev_apps(user, all_apps=True)
        return {"apps": apps, "default_access": self.config.default_access,
                "catalog_error": self.sources.last_error,
                "pending": sum(1 for a in apps if a["review"] == "pending")}

    def admin_update_app(self, actor, app_id, b: dict) -> dict:
        fields = {}
        if "review" in b:
            if b["review"] not in ("approved", "rejected", "pending"):
                raise HttpError(400, "review muss approved, rejected oder pending sein")
            fields["review"] = b["review"]
            fields["review_note"] = (b.get("review_note") or "").strip()[:1000]
        if "developer" in b:
            name = (b["developer"] or "").strip()
            with self.db.connect() as conn:
                dev = conn.execute("SELECT * FROM users WHERE username = ?", (name,)).fetchone() if name else None
            if name and (not dev or dev["role"] == "user"):
                raise HttpError(400, "Entwickler nicht gefunden (Konto muss Entwickler-Rechte haben)")
            fields["developer_id"] = dev["id"] if dev else None
        with self.db.connect() as conn:
            before = self._app_row(conn, app_id)
            if fields:
                conn.execute(f"UPDATE apps SET {', '.join(k + ' = ?' for k in fields)} WHERE key = ?",
                             [*fields.values(), before["key"]])
            dev = self._user(conn, before["developer_id"]) if before["developer_id"] else None
        rest = {k: v for k, v in b.items() if k not in ("review", "review_note", "developer")}
        result = self.update_app(actor, app_id, rest) if rest else self.dev_app(actor, app_id)
        if "review" in fields and fields["review"] != before["review"] and dev:
            approved = fields["review"] == "approved"
            if fields["review"] != "pending":
                self._mail_user(
                    dev, f"{before['name']}: {'freigegeben 🎉' if approved else 'nicht freigegeben'}",
                    intro=(f"Gute Nachricht, {dev['username']}: Deine App „{before['name']}“ ist jetzt im Store "
                           "sichtbar." if approved else
                           f"Hallo {dev['username']}, deine App „{before['name']}“ wurde leider nicht freigegeben."),
                    paragraphs=[f"Begründung: {fields['review_note']}"] if fields["review_note"] else [],
                    button=("App ansehen", f"{self.config.public_url}/app/{before['id']}") if approved else None,
                    note="" if approved else "Du kannst die App überarbeiten; ein Admin prüft sie dann erneut.")
        return result

    def list_users(self) -> list:
        with self.db.connect() as conn:
            users = conn.execute(
                "SELECT * FROM users ORDER BY dev_requested_at IS NULL, "
                "CASE role WHEN 'admin' THEN 0 WHEN 'developer' THEN 1 ELSE 2 END, username COLLATE NOCASE").fetchall()
            unlocks = conn.execute("SELECT un.user_id, un.app, un.source, a.id, a.name FROM unlocks un "
                                   "LEFT JOIN apps a ON a.key = un.app").fetchall()
            app_counts = {r["developer_id"]: r["n"] for r in conn.execute(
                "SELECT developer_id, COUNT(*) AS n FROM apps WHERE developer_id IS NOT NULL GROUP BY developer_id")}
        by_user: dict = {}
        for u in unlocks:
            by_user.setdefault(u["user_id"], []).append(
                {"id": u["id"] or u["app"], "name": u["name"] or u["app"], "source": u["source"]})
        return [{**self.user_json(u), "created_at": u["created_at"], "dev_note": u["dev_note"],
                 "dev_requested_at": u["dev_requested_at"], "apps": app_counts.get(u["id"], 0),
                 "unlocked": by_user.get(u["id"], [])} for u in users]

    def set_role(self, actor, user_id: int, role: str) -> dict:
        if role not in ROLES:
            raise HttpError(400, "Rolle muss user, developer oder admin sein")
        with self.db.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            target = self._user(conn, user_id)
            if not target:
                conn.execute("ROLLBACK")
                raise HttpError(404, "Benutzer nicht gefunden")
            if target["role"] == "admin" and role != "admin" and conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0] <= 1:
                conn.execute("ROLLBACK")
                raise HttpError(400, "Der letzte Admin kann nicht entfernt werden")
            conn.execute("UPDATE users SET role = ?, dev_requested_at = CASE WHEN ? = 'user' THEN dev_requested_at "
                         "ELSE NULL END WHERE id = ?", (role, role, user_id))
            conn.execute("COMMIT")
            row = self._user(conn, user_id)
        if role != target["role"]:
            texts = {
                "admin": ("Du bist jetzt Admin", "Du kannst jetzt Benutzer, Entwickler-Anfragen und alle Apps "
                                                 "verwalten. Den Admin-Bereich findest du oben in der App."),
                "developer": ("Du bist jetzt Entwickler 🎉", "Du kannst jetzt eigene Apps veröffentlichen – in der "
                              "App unter Konto → Entwickler-Bereich oder im Entwickler-Portal."),
                "user": ("Deine Rolle wurde geändert", "Dein Konto ist jetzt ein normales Benutzerkonto."),
            }
            title, text = texts[role]
            self._mail_user(row, title, intro=f"Hallo {row['username']}, {actor['username']} hat deine Rolle geändert.",
                            paragraphs=[text],
                            button=("Entwickler-Portal öffnen", f"{self.config.public_url}/portal")
                            if role == "developer" else None)
        return self.user_json(row)

    def decide_developer(self, actor, user_id, approve: bool, note: str) -> dict:
        with self.db.connect() as conn:
            target = self._user(conn, user_id)
        if not target:
            raise HttpError(404, "Benutzer nicht gefunden")
        if approve:
            return self.set_role(actor, user_id, "developer" if target["role"] == "user" else target["role"])
        with self.db.connect() as conn:
            conn.execute("UPDATE users SET dev_requested_at = NULL WHERE id = ?", (user_id,))
            row = self._user(conn, user_id)
        note = (note or "").strip()[:1000]
        self._mail_user(row, "Deine Entwickler-Anfrage",
                        intro=f"Hallo {row['username']}, deine Anfrage auf ein Entwickler-Konto wurde leider "
                              "abgelehnt.",
                        paragraphs=([f"Begründung: {note}"] if note else []) +
                                   ["Du kannst ByteDroide natürlich weiter als Benutzer nutzen und später eine neue "
                                    "Anfrage stellen."])
        return self.user_json(row)

    def delete_user(self, actor, user_id: int):
        if user_id == actor["id"]:
            raise HttpError(400, "Dein eigenes Konto löschst du unter Konto → Konto löschen")
        self._delete_user(user_id)

    def revoke_unlock(self, user_id: int, app_id: str):
        with self.db.connect() as conn:
            conn.execute("DELETE FROM unlocks WHERE user_id = ? AND app = ?", (user_id, app_id.lower()))

    def grant_unlock(self, user_id: int, app_id: str):
        with self.db.connect() as conn:
            row = self._app_row(conn, app_id)
            if not self._user(conn, user_id):
                raise HttpError(404, "Benutzer nicht gefunden")
            conn.execute("INSERT OR IGNORE INTO unlocks (user_id, app, unlocked_at, source) VALUES (?, ?, ?, 'grant')",
                         (user_id, row["key"], now()))

    def announce(self, actor, subject, message) -> dict:
        subject, message = (subject or "").strip()[:120], (message or "").strip()[:5000]
        if not subject or not message:
            raise HttpError(400, "Betreff und Nachricht angeben")
        with self.db.connect() as conn:
            users = conn.execute("SELECT * FROM users WHERE notify_news = 1 AND email_verified = 1").fetchall()
        for u in users:
            self._mail_user(u, subject, intro=f"Hallo {u['username']},", paragraphs=message.split("\n\n"),
                            reason="Du erhältst diese E-Mail, weil du Neuigkeiten von ByteDroide abonniert hast. "
                                   "Abschalten: ByteDroide → Konto → Benachrichtigungen.")
        return {"recipients": len(users), "mail_enabled": self.mailer.enabled}

    def overview(self) -> dict:
        with self.db.connect() as conn:
            one = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
            return {
                "users": one("SELECT COUNT(*) FROM users"),
                "developers": one("SELECT COUNT(*) FROM users WHERE role IN ('developer', 'admin')"),
                "dev_requests": one("SELECT COUNT(*) FROM users WHERE dev_requested_at IS NOT NULL"),
                "apps": one("SELECT COUNT(*) FROM apps"),
                "apps_pending": one("SELECT COUNT(*) FROM apps WHERE review = 'pending'"),
                "downloads_30d": conn.execute("SELECT COUNT(*) FROM downloads WHERE ts > ?",
                                              (now() - 30 * 86400,)).fetchone()[0],
                "revenue_cents": one("SELECT COALESCE(SUM(amount_cents), 0) FROM purchases WHERE status = 'paid'"),
                "withdrawals_open": one("SELECT COUNT(*) FROM purchases WHERE status = 'withdrawal_requested'"),
                "mail_enabled": self.mailer.enabled,
                "payments_enabled": bool(self.config.stripe_secret_key),
                "legal_missing": legal.missing_fields(self.config),
            }

    # --- Käufe (Stripe) ------------------------------------------------------------

    def _stripe_request(self, method, path, params=None):
        data = urllib.parse.urlencode(params or []).encode() if params is not None else None
        req = urllib.request.Request("https://api.stripe.com" + path, data=data, method=method, headers={
            "Authorization": f"Bearer {self.config.stripe_secret_key}",
            "Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = json.loads(e.read() or b"{}").get("error", {}).get("message", str(e))
            raise HttpError(502, f"Zahlungsanbieter: {detail}")

    def create_checkout(self, user, app_id, accept_waiver) -> dict:
        row, view = self.app_for(user, app_id)
        if row["price_cents"] <= 0:
            raise HttpError(400, "Diese App ist kostenlos")
        if view["unlocked"]:
            raise HttpError(409, "Du hast diese App schon")
        if not self.config.stripe_secret_key:
            raise HttpError(503, "Bezahlung ist noch nicht eingerichtet. Frage den Entwickler nach einem "
                                 "Freischalt-Code.")
        if not accept_waiver:
            raise HttpError(400, "Bitte stimme der sofortigen Bereitstellung zu (Hinweis zum Widerrufsrecht)")
        base = self.config.public_url
        params = [
            ("mode", "payment"),
            ("success_url", f"{base}/kauf/danke?session_id={{CHECKOUT_SESSION_ID}}"),
            ("cancel_url", f"{base}/kauf/abgebrochen"),
            ("client_reference_id", str(user["id"])),
            ("line_items[0][quantity]", "1"),
            ("line_items[0][price_data][currency]", self.config.currency),
            ("line_items[0][price_data][unit_amount]", str(row["price_cents"])),
            ("line_items[0][price_data][product_data][name]", f"{row['name']} (Android-App)"),
            ("metadata[user_id]", str(user["id"])),
            ("metadata[app]", row["key"]),
            ("metadata[waiver_accepted_at]", str(now())),
            ("payment_intent_data[metadata][app]", row["key"]),
        ]
        if user["email"]:
            params.append(("customer_email", user["email"]))
        session = self.stripe("POST", "/v1/checkout/sessions", params)
        return {"checkout_url": session["url"]}

    def verify_stripe_signature(self, payload: bytes, header: str):
        if not self.config.stripe_webhook_secret:
            raise HttpError(503, "Webhook nicht eingerichtet")
        parts = dict(p.split("=", 1) for p in (header or "").split(",") if "=" in p)
        sigs = [p.split("=", 1)[1] for p in (header or "").split(",") if p.startswith("v1=")]
        try:
            ts = int(parts.get("t", "0"))
        except ValueError:
            ts = 0
        expected = hmac.new(self.config.stripe_webhook_secret.encode(), f"{ts}.".encode() + payload,
                            hashlib.sha256).hexdigest()
        if not any(hmac.compare_digest(expected, s) for s in sigs) or abs(time.time() - ts) > 300:
            raise HttpError(400, "Ungültige Signatur")

    def stripe_webhook(self, payload: bytes, signature: str):
        self.verify_stripe_signature(payload, signature)
        event = json.loads(payload)
        if event.get("type") not in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
            return {"ok": True}
        obj = event["data"]["object"]
        if obj.get("payment_status") != "paid":
            return {"ok": True}
        meta = obj.get("metadata") or {}
        self.record_purchase(int(meta.get("user_id", 0)), meta.get("app", ""), obj.get("amount_total", 0),
                             obj.get("currency", self.config.currency), "stripe", obj["id"],
                             obj.get("payment_intent") or "")
        return {"ok": True}

    def record_purchase(self, user_id, app_key, amount, currency, provider, ref, payment_ref=""):
        with self.db.connect() as conn:
            user = self._user(conn, user_id)
            app = conn.execute("SELECT a.*, u.username AS developer FROM apps a LEFT JOIN users u "
                               "ON u.id = a.developer_id WHERE a.key = ?", (app_key,)).fetchone()
            if not user or not app:
                log.warning("Kauf %s: Benutzer %s oder App %s fehlt", ref, user_id, app_key)
                return
            cur = conn.execute(
                "INSERT OR IGNORE INTO purchases (user_id, username, email, app, app_name, amount_cents, currency, "
                "provider, provider_ref, payment_ref, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, user["username"], user["email"] or "", app_key, app["name"], amount, currency, provider,
                 ref, payment_ref, now()))
            if not cur.rowcount:
                return  # Webhook doppelt zugestellt
            purchase_id = cur.lastrowid
            conn.execute("INSERT OR IGNORE INTO unlocks (user_id, app, unlocked_at, source) VALUES (?, ?, ?, 'purchase')",
                         (user_id, app_key, now()))
            dev = self._user(conn, app["developer_id"]) if app["developer_id"] else None
        vat = ("Gemäß § 19 UStG wird keine Umsatzsteuer berechnet." if self.config.kleinunternehmer
               else "Der Betrag enthält die gesetzliche Umsatzsteuer.")
        self._mail_user(
            user, f"Kaufbeleg: {app['name']}", require_verified=False,
            intro=f"Danke für deinen Kauf, {user['username']}! {app['name']} ist jetzt für dein Konto freigeschaltet.",
            facts=[("Beleg-Nr.", f"BD-{purchase_id:06d}"), ("Datum", format_ts(now())), ("Artikel", app["name"]),
                   ("Betrag", format_price(amount, currency)), ("Zahlungsart", "Stripe"),
                   ("Verkäufer", self.config.operator_name or "ByteDroide")],
            paragraphs=[vat, "Du hast zugestimmt, dass die App sofort bereitgestellt wird, und bestätigt, dass dein "
                             "Widerrufsrecht damit vorzeitig erlischt (§ 356 Abs. 5 BGB). Diese E-Mail ist die "
                             "Bestätigung des Vertrags auf einem dauerhaften Datenträger."],
            button=("App in ByteDroide öffnen", f"{self.config.public_url}/app/{app['id']}"),
            note=f"Widerrufsbelehrung: {self.config.public_url}/widerruf · Nutzungsbedingungen: "
                 f"{self.config.public_url}/agb",
            reason="Du erhältst diese E-Mail als Beleg für deinen Kauf bei ByteDroide.")
        if dev:
            self._mail_user(dev, f"Verkauf: {app['name']}",
                            intro=f"Hallo {dev['username']}, jemand hat gerade {app['name']} gekauft. 🎉",
                            facts=[("Betrag", format_price(amount, currency)), ("Datum", format_ts(now()))])

    def my_purchases(self, user) -> list:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT p.*, a.id AS app_id FROM purchases p LEFT JOIN apps a ON a.key = p.app "
                                "WHERE p.user_id = ? ORDER BY p.created_at DESC", (user["id"],)).fetchall()
        return [{"id": r["id"], "app": r["app_id"] or r["app"], "app_name": r["app_name"],
                 "amount_cents": r["amount_cents"], "price": format_price(r["amount_cents"], r["currency"]),
                 "status": r["status"], "created_at": r["created_at"], "withdrawn_at": r["withdrawn_at"],
                 "can_withdraw": r["status"] == "paid" and now() - r["created_at"] <= WITHDRAWAL_DAYS * 86400}
                for r in rows]

    def withdraw_purchase(self, user, purchase_id) -> dict:
        with self.db.connect() as conn:
            p = conn.execute("SELECT * FROM purchases WHERE id = ? AND user_id = ?", (purchase_id, user["id"])).fetchone()
            if not p:
                raise HttpError(404, "Kauf nicht gefunden")
            if p["status"] != "paid":
                raise HttpError(400, "Für diesen Kauf liegt schon ein Widerruf vor")
            if now() - p["created_at"] > WITHDRAWAL_DAYS * 86400:
                raise HttpError(400, "Die Widerrufsfrist von 14 Tagen ist abgelaufen")
            conn.execute("UPDATE purchases SET status = 'withdrawal_requested', withdrawn_at = ? WHERE id = ?",
                         (now(), purchase_id))
        facts = [("Beleg-Nr.", f"BD-{p['id']:06d}"), ("Artikel", p["app_name"]),
                 ("Betrag", format_price(p["amount_cents"], p["currency"])), ("Kaufdatum", format_ts(p["created_at"])),
                 ("Widerruf eingegangen", format_ts(now()))]
        self._mail_user(user, "Eingangsbestätigung deines Widerrufs", require_verified=False,
                        intro=f"Hallo {user['username']}, wir haben deinen Widerruf des folgenden Vertrags erhalten.",
                        facts=facts,
                        paragraphs=["Wir prüfen den Widerruf und melden uns. Steht dir ein Widerrufsrecht zu, "
                                    "erstatten wir den Betrag innerhalb von 14 Tagen über das ursprüngliche "
                                    "Zahlungsmittel."],
                        reason="Du erhältst diese E-Mail als Bestätigung deines Widerrufs.")
        if self.config.operator_email:
            self._mail(self.config.operator_email, f"Widerruf eingegangen: {p['app_name']}",
                       intro=f"{user['username']} ({user['email'] or 'keine E-Mail'}) hat einen Kauf widerrufen.",
                       facts=facts, paragraphs=["Bearbeiten: Admin-Bereich → Käufe."],
                       reason="Du erhältst diese E-Mail als Betreiber von ByteDroide.")
        return {"ok": True}

    def admin_purchases(self) -> list:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM purchases ORDER BY created_at DESC LIMIT 500").fetchall()
        return [{"id": r["id"], "username": r["username"], "email": r["email"], "app": r["app"],
                 "app_name": r["app_name"], "price": format_price(r["amount_cents"], r["currency"]),
                 "amount_cents": r["amount_cents"], "status": r["status"], "created_at": r["created_at"],
                 "withdrawn_at": r["withdrawn_at"], "provider": r["provider"]} for r in rows]

    def refund_purchase(self, actor, purchase_id) -> dict:
        with self.db.connect() as conn:
            p = conn.execute("SELECT * FROM purchases WHERE id = ?", (purchase_id,)).fetchone()
        if not p:
            raise HttpError(404, "Kauf nicht gefunden")
        if p["status"] == "refunded":
            raise HttpError(400, "Schon erstattet")
        if p["provider"] == "stripe" and p["payment_ref"] and self.config.stripe_secret_key:
            self.stripe("POST", "/v1/refunds", [("payment_intent", p["payment_ref"])])
        with self.db.connect() as conn:
            conn.execute("UPDATE purchases SET status = 'refunded' WHERE id = ?", (purchase_id,))
            if p["user_id"]:
                conn.execute("DELETE FROM unlocks WHERE user_id = ? AND app = ? AND source = 'purchase'",
                             (p["user_id"], p["app"]))
            user = self._user(conn, p["user_id"]) if p["user_id"] else None
        if user:
            self._mail_user(user, f"Erstattung: {p['app_name']}", require_verified=False,
                            intro=f"Hallo {user['username']}, wir haben dir "
                                  f"{format_price(p['amount_cents'], p['currency'])} für {p['app_name']} erstattet.",
                            paragraphs=["Die Gutschrift erfolgt über das ursprüngliche Zahlungsmittel und kann je nach "
                                        "Bank einige Tage dauern. Die App ist für dein Konto nicht mehr freigeschaltet."])
        return {"ok": True}


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

APP_ID = r"(?P<owner>[^/]+)/(?P<repo>[^/]+)"
ROUTES = []
AUTH_LEVELS = ("none", "user", "developer", "admin")


def route(method: str, pattern: str, auth: str = "none"):
    """auth: none (optional angemeldet), user (Anmeldung nötig), developer, admin."""
    regex = re.compile("^" + pattern + "$")

    def deco(fn):
        ROUTES.append((method, regex, auth, fn))
        return fn
    return deco


def app_id(params) -> str:
    return f"{urllib.parse.unquote(params['owner'])}/{urllib.parse.unquote(params['repo'])}"


HTML_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
                               "img-src * data:; connect-src 'self'; frame-ancestors 'none'; form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


FAVICON_SVG = (b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" '
               b'fill="#3D5AFE"/><rect x="14" y="22" width="36" height="28" rx="8" fill="#fff"/><circle cx="25" cy="35" '
               b'r="4" fill="#3D5AFE"/><circle cx="39" cy="35" r="4" fill="#3D5AFE"/><path d="M24 22l-4-8M40 22l4-8" '
               b'stroke="#fff" stroke-width="3" stroke-linecap="round"/></svg>')


class Handler(BaseHTTPRequestHandler):
    store: Store = None  # wird in make_server gesetzt
    protocol_version = "HTTP/1.1"
    server_version = "ByteDroideServer/2.0"

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

    def content_length(self, limit: int) -> int:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise HttpError(400, "Ungültige Länge")
        if length > limit:
            self.close_connection = True
            raise HttpError(413, "Anfrage zu groß")
        return length

    def raw_body(self, limit=1024 * 1024) -> bytes:
        length = min(self.content_length(limit), self._body_left)
        data = self.rfile.read(length) if length else b""
        self._body_left -= len(data)
        return data

    def discard_body(self):
        """Nicht gelesenen Request-Body verwerfen. Sonst landet er bei Keep-Alive-Verbindungen (z. B. über Caddy)
        vor der nächsten Anfrage und macht sie kaputt."""
        left, self._body_left = self._body_left, 0
        if left <= 0 or self.close_connection:
            return
        if left > 1024 * 1024:  # z. B. abgelehnter Upload: nicht alles lesen, Verbindung schließen
            self.close_connection = True
            return
        try:
            while left > 0:
                chunk = self.rfile.read(min(left, 64 * 1024))
                if not chunk:
                    break
                left -= len(chunk)
        except OSError:
            self.close_connection = True

    def body(self) -> dict:
        raw = self.raw_body(64 * 1024)
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HttpError(400, "Ungültiges JSON")
        if not isinstance(data, dict):
            raise HttpError(400, "JSON-Objekt erwartet")
        return data

    def form(self) -> dict:
        return dict(urllib.parse.parse_qsl(self.raw_body(16 * 1024).decode("utf-8", "replace")))

    def send_bytes(self, status, data: bytes, content_type: str, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def send_json(self, status: int, payload):
        self.send_bytes(status, json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8",
                        {"Cache-Control": "no-store"})

    def send_html(self, html_text: str, status=200):
        self.send_bytes(status, html_text.encode(), "text/html; charset=utf-8",
                        {**HTML_HEADERS, "Cache-Control": "no-store"})

    def handle_any(self, method: str):
        split = urllib.parse.urlsplit(self.path)
        path, query = split.path, dict(urllib.parse.parse_qsl(split.query))
        try:
            self._body_left = max(0, int(self.headers.get("Content-Length") or 0))
        except ValueError:
            self._body_left = 0
            self.close_connection = True
        if self.headers.get("Transfer-Encoding"):  # chunked wird nicht unterstützt
            self.close_connection = True
        try:
            for m, regex, auth, fn in ROUTES:
                match = regex.match(path)
                if not match or m != method:
                    continue
                user = self.store.user_for_token(self.bearer())
                if auth != "none" and not user:
                    raise HttpError(401, "Bitte anmelden")
                if auth == "developer" and user["role"] not in ("developer", "admin"):
                    raise HttpError(403, "Nur für Entwickler – Freischaltung im Konto beantragen")
                if auth == "admin" and user["role"] != "admin":
                    raise HttpError(403, "Nur für Admins")
                result = fn(self, user=user, params=match.groupdict(), query=query)
                if result is not None:
                    self.send_json(200, result)
                return
            raise HttpError(404, "Nicht gefunden")
        except HttpError as e:
            if path.startswith("/api/") or path == "/healthz":
                self.send_json(e.status, {"error": e.message})
            else:
                self.send_html(legal.simple_page(self.store.config, "Fehler", e.message), e.status)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            log.exception("Fehler bei %s %s", method, path)
            try:
                self.send_json(500, {"error": "Interner Serverfehler"})
            except Exception:
                pass
        finally:
            self.discard_body()

    def do_GET(self):
        self.handle_any("GET")

    def do_HEAD(self):
        self.handle_any("GET")

    def do_POST(self):
        self.handle_any("POST")

    def do_PUT(self):
        self.handle_any("PUT")

    def do_DELETE(self):
        self.handle_any("DELETE")

    def stream_file(self, fileobj, length, name, content_type="application/vnd.android.package-archive"):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        if length:
            self.send_header("Content-Length", str(length))
        else:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        while self.command != "HEAD":
            chunk = fileobj.read(64 * 1024)
            if not chunk:
                break
            self.wfile.write(chunk)

    def send_apk(self, apk):
        if "path" in apk:
            path = os.path.join(self.store.config.data_dir, apk["path"])
            with open(path, "rb") as f:
                self.stream_file(f, os.path.getsize(path), apk["name"])
            return
        url, headers = apk["fetch"]
        try:
            upstream = self.store.sources.open_download(url, headers)
        except urllib.error.HTTPError as e:
            raise HttpError(502, f"Download von der Quelle fehlgeschlagen ({e.code})")
        with upstream:
            self.stream_file(upstream, upstream.headers.get("Content-Length"), apk["name"])

    # --- Webseiten -------------------------------------------------------------

    @route("GET", "/")
    def w_index(self, **_):
        self.send_html(legal.landing(self.store.config))

    @route("GET", "/robots.txt")
    def w_robots(self, **_):
        self.send_bytes(200, b"User-agent: *\nDisallow: /api/\nDisallow: /portal\nDisallow: /reset\nDisallow: /verify\n",
                        "text/plain; charset=utf-8", {"Cache-Control": "public, max-age=86400"})

    @route("GET", "/favicon.ico")
    def w_favicon(self, **_):
        self.send_bytes(200, FAVICON_SVG, "image/svg+xml", {"Cache-Control": "public, max-age=604800"})

    @route("GET", "/impressum")
    def w_impressum(self, **_):
        self.send_html(legal.impressum(self.store.config))

    @route("GET", "/datenschutz")
    def w_datenschutz(self, **_):
        self.send_html(legal.datenschutz(self.store.config))

    @route("GET", "/agb")
    def w_agb(self, **_):
        self.send_html(legal.agb(self.store.config))

    @route("GET", "/widerruf")
    def w_widerruf(self, **_):
        self.send_html(legal.widerruf(self.store.config))

    @route("GET", "/verify")
    def w_verify(self, query, **_):
        ok = self.store.verify_email(query.get("token", ""))
        self.send_html(legal.simple_page(
            self.store.config, "E-Mail bestätigt" if ok else "Link ungültig",
            "Danke! Deine E-Mail-Adresse ist bestätigt. Du kannst dieses Fenster schließen." if ok else
            "Der Link ist ungültig oder abgelaufen. In der App kannst du unter Konto eine neue Bestätigung anfordern."),
            200 if ok else 400)

    @route("GET", "/reset")
    def w_reset_form(self, query, **_):
        import html as h
        token = h.escape(query.get("token", ""))
        form = (f'<form method="post" action="/reset"><input type="hidden" name="token" value="{token}">'
                '<label>Neues Passwort (mind. 8 Zeichen)<input type="password" name="password" minlength="8" '
                'required autocomplete="new-password"></label><button type="submit">Passwort speichern</button></form>')
        self.send_html(legal.simple_page(self.store.config, "Neues Passwort", "Lege ein neues Passwort fest.", form))

    @route("POST", "/reset")
    def w_reset(self, **_):
        f = self.form()
        name = self.store.reset_password(f.get("token", ""), f.get("password", ""))
        self.send_html(legal.simple_page(self.store.config, "Passwort geändert",
                                         f"Fertig, {name}! Melde dich jetzt in der App mit dem neuen Passwort an."))

    @route("GET", "/kauf/danke")
    def w_thanks(self, **_):
        self.send_html(legal.simple_page(self.store.config, "Danke für deinen Kauf!",
                                         "Die App wird gleich für dein Konto freigeschaltet. Den Beleg bekommst du per "
                                         "E-Mail. Du kannst jetzt zurück zu ByteDroide wechseln."))

    @route("GET", "/kauf/abgebrochen")
    def w_cancel(self, **_):
        self.send_html(legal.simple_page(self.store.config, "Kauf abgebrochen",
                                         "Der Kauf wurde abgebrochen, es wurde nichts berechnet."))

    @route("GET", f"/app/{APP_ID}")
    def w_app(self, user, params, **_):
        import html as h
        _, view = self.store.app_for(None, app_id(params))
        deep = h.escape(f"bytedroide://app/{view['id']}")
        body = (f"<p><strong>{h.escape(view['name'])}</strong> von {h.escape(view['owner'])} · Version "
                f"{h.escape(normalize_version(view['release']['tag']))}</p><p>{h.escape(view['description'])}</p>"
                f'<p><a href="{deep}">In ByteDroide öffnen</a> · <a href="/download">ByteDroide herunterladen</a></p>')
        self.send_html(legal.page(self.store.config, view["name"], f"<section>{body}</section>"))

    @route("GET", "/download")
    def w_download_store(self, user, **_):
        if not self.store.config.store_app_id:
            raise HttpError(404, "Download noch nicht eingerichtet (STORE_APP_ID)")
        self.send_apk(self.store.resolve_download(None, self.store.config.store_app_id, ""))

    @route("GET", "/portal")
    def w_portal(self, **_):
        with open(os.path.join(HERE, "web", "portal.html"), encoding="utf-8") as f:
            self.send_html(f.read().replace("{{PUBLIC_URL}}", self.store.config.public_url))

    # --- API: allgemein & Konto -------------------------------------------------

    @route("GET", "/healthz")
    def health(self, **_):
        return {"ok": True}

    @route("GET", "/api/info")
    def r_info(self, **_):
        c = self.store.config
        base = c.public_url
        return {"name": "ByteDroide", "version": 2, "mail_enabled": self.store.mailer.enabled,
                "payments_enabled": bool(c.stripe_secret_key),
                "legal": {"impressum": f"{base}/impressum", "datenschutz": f"{base}/datenschutz",
                          "agb": f"{base}/agb", "widerruf": f"{base}/widerruf"},
                "portal": f"{base}/portal", "operator_email": c.operator_email}

    @route("POST", "/api/register")
    def r_register(self, **_):
        return self.store.register(self.client_ip(), self.body())

    @route("POST", "/api/login")
    def r_login(self, **_):
        b = self.body()
        return self.store.login(self.client_ip(), b.get("username", ""), b.get("password", ""))

    @route("POST", "/api/logout", auth="user")
    def r_logout(self, **_):
        self.store.logout(self.bearer())
        return {"ok": True}

    @route("POST", "/api/password/forgot")
    def r_forgot(self, **_):
        return self.store.forgot_password(self.client_ip(), self.body().get("login", ""))

    @route("GET", "/api/me", auth="user")
    def r_me(self, user, **_):
        return {"user": self.store.user_json(user)}

    @route("PUT", "/api/me", auth="user")
    def r_update_me(self, user, **_):
        return self.store.update_me(user, self.body())

    @route("DELETE", "/api/me", auth="user")
    def r_delete_me(self, user, **_):
        self.store.delete_me(user, self.body().get("password", ""))
        return {"ok": True}

    @route("POST", "/api/me/password", auth="user")
    def r_password(self, user, **_):
        b = self.body()
        self.store.change_password(user, b.get("old_password", ""), b.get("new_password", ""))
        return {"ok": True}

    @route("POST", "/api/me/verify", auth="user")
    def r_resend(self, user, **_):
        return self.store.resend_verification(self.client_ip(), user)

    @route("POST", "/api/me/developer", auth="user")
    def r_request_dev(self, user, **_):
        return self.store.request_developer(user, self.body().get("note", ""))

    @route("GET", "/api/me/export", auth="user")
    def r_export(self, user, **_):
        return self.store.export_me(user)

    @route("GET", "/api/me/purchases", auth="user")
    def r_purchases(self, user, **_):
        return {"purchases": self.store.my_purchases(user)}

    @route("POST", r"/api/me/purchases/(?P<id>\d+)/withdraw", auth="user")
    def r_withdraw(self, user, params, **_):
        return self.store.withdraw_purchase(user, int(params["id"]))

    # --- API: Katalog ----------------------------------------------------------------

    @route("GET", "/api/apps")
    def r_apps(self, user, **_):
        return {"apps": self.store.list_apps(user), "user": self.store.user_json(user) if user else None}

    @route("GET", f"/api/apps/{APP_ID}/download")
    def r_download(self, user, params, query, **_):
        self.send_apk(self.store.resolve_download(user, app_id(params), query.get("asset", "")))

    @route("GET", f"/api/apps/{APP_ID}/icon")
    def r_icon(self, params, **_):
        with self.store.db.connect() as conn:
            row = self.store._app_row(conn, app_id(params))
        if not row["icon_path"]:
            raise HttpError(404, "Kein Icon")
        path = os.path.join(self.store.config.data_dir, row["icon_path"])
        ext = path.rsplit(".", 1)[-1]
        with open(path, "rb") as f:
            self.send_bytes(200, f.read(), {"png": "image/png", "jpg": "image/jpeg", "webp": "image/webp"}[ext],
                            {"Cache-Control": "public, max-age=86400"})

    @route("POST", f"/api/apps/{APP_ID}/beta", auth="user")
    def r_beta_join(self, user, params, **_):
        return self.store.set_beta(user, app_id(params), True)

    @route("DELETE", f"/api/apps/{APP_ID}/beta", auth="user")
    def r_beta_leave(self, user, params, **_):
        return self.store.set_beta(user, app_id(params), False)

    @route("POST", f"/api/apps/{APP_ID}/purchase", auth="user")
    def r_purchase(self, user, params, **_):
        return self.store.create_checkout(user, app_id(params), self.body().get("accept_waiver"))

    @route("POST", "/api/redeem", auth="user")
    def r_redeem(self, user, **_):
        return self.store.redeem(self.client_ip(), user, self.body().get("code", ""))

    @route("POST", "/api/stripe/webhook")
    def r_stripe(self, **_):
        return self.store.stripe_webhook(self.raw_body(), self.headers.get("Stripe-Signature", ""))

    # --- API: Entwickler ---------------------------------------------------------------

    @route("GET", "/api/dev/apps", auth="developer")
    def r_dev_apps(self, user, **_):
        return {"apps": self.store.dev_apps(user)}

    @route("POST", "/api/dev/apps", auth="developer")
    def r_dev_create(self, user, **_):
        return self.store.create_app(user, self.body())

    @route("GET", f"/api/dev/apps/{APP_ID}", auth="developer")
    def r_dev_app(self, user, params, **_):
        return self.store.dev_app(user, app_id(params))

    @route("PUT", f"/api/dev/apps/{APP_ID}", auth="developer")
    def r_dev_update(self, user, params, **_):
        return self.store.update_app(user, app_id(params), self.body())

    @route("DELETE", f"/api/dev/apps/{APP_ID}", auth="developer")
    def r_dev_delete(self, user, params, **_):
        self.store.delete_app(user, app_id(params))
        return {"ok": True}

    @route("GET", f"/api/dev/apps/{APP_ID}/releases", auth="developer")
    def r_dev_releases(self, user, params, **_):
        return {"releases": self.store.list_releases(user, app_id(params))}

    @route("POST", f"/api/dev/apps/{APP_ID}/releases", auth="developer")
    def r_dev_upload(self, user, params, query, **_):
        aid = app_id(params)
        self.store._require_manage(user, aid)  # vor dem Hochladen prüfen
        limit = self.store.config.max_upload_mb * 1024 * 1024
        length = self.content_length(limit)
        if not length:
            raise HttpError(411, "APK als Request-Body mit Content-Length senden")
        tmp_dir = os.path.join(self.store.config.data_dir, "apks")
        fd, tmp = tempfile.mkstemp(dir=tmp_dir, suffix=".part")
        digest = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as out:
                left = length
                while left:
                    chunk = self.rfile.read(min(left, 256 * 1024))
                    if not chunk:
                        raise HttpError(400, "Upload abgebrochen")
                    out.write(chunk)
                    digest.update(chunk)
                    left -= len(chunk)
                    self._body_left -= len(chunk)
            notes = query.get("notes") or urllib.parse.unquote(self.headers.get("X-Release-Notes", ""))
            return self.store.add_release(user, aid, tmp, length, digest.hexdigest(), query.get("version", ""),
                                          query.get("channel", "stable"), notes)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    @route("DELETE", rf"/api/dev/apps/{APP_ID}/releases/(?P<rid>\d+)", auth="developer")
    def r_dev_delete_release(self, user, params, **_):
        self.store.delete_release(user, app_id(params), int(params["rid"]))
        return {"ok": True}

    @route("POST", f"/api/dev/apps/{APP_ID}/icon", auth="developer")
    def r_dev_icon(self, user, params, **_):
        return self.store.set_icon(user, app_id(params), self.raw_body(1024 * 1024))

    @route("GET", f"/api/dev/apps/{APP_ID}/codes", auth="developer")
    def r_dev_codes(self, user, params, **_):
        self.store._require_manage(user, app_id(params))
        return {"codes": self.store.list_codes(app_id(params))}

    @route("POST", f"/api/dev/apps/{APP_ID}/codes", auth="developer")
    def r_dev_new_codes(self, user, params, **_):
        self.store._require_manage(user, app_id(params))
        b = self.body()
        return {"codes": self.store.create_codes(user, app_id(params), b.get("count", 1), b.get("note", ""))}

    @route("DELETE", r"/api/dev/codes/(?P<code>[A-Za-z0-9-]+)", auth="developer")
    def r_dev_delete_code(self, user, params, **_):
        self.store.delete_code(user, params["code"])
        return {"ok": True}

    @route("GET", f"/api/dev/apps/{APP_ID}/testers", auth="developer")
    def r_dev_testers(self, user, params, **_):
        self.store._require_manage(user, app_id(params))
        return {"testers": self.store.list_testers(app_id(params))}

    @route("POST", f"/api/dev/apps/{APP_ID}/testers", auth="developer")
    def r_dev_add_tester(self, user, params, **_):
        self.store._require_manage(user, app_id(params))
        self.store.add_tester(app_id(params), self.body().get("username", ""))
        return {"testers": self.store.list_testers(app_id(params))}

    @route("DELETE", rf"/api/dev/apps/{APP_ID}/testers/(?P<uid>\d+)", auth="developer")
    def r_dev_remove_tester(self, user, params, **_):
        self.store._require_manage(user, app_id(params))
        self.store.remove_tester(app_id(params), int(params["uid"]))
        return {"ok": True}

    @route("GET", "/api/dev/keys", auth="developer")
    def r_keys(self, user, **_):
        return {"keys": self.store.list_api_keys(user)}

    @route("POST", "/api/dev/keys", auth="developer")
    def r_new_key(self, user, **_):
        return self.store.create_api_key(user, self.body().get("label", ""))

    @route("DELETE", r"/api/dev/keys/(?P<kid>[0-9a-f]+)", auth="developer")
    def r_delete_key(self, user, params, **_):
        self.store.delete_api_key(user, params["kid"])
        return {"ok": True}

    # --- API: Admin ------------------------------------------------------------------

    @route("GET", "/api/admin/overview", auth="admin")
    def r_overview(self, **_):
        return self.store.overview()

    @route("GET", "/api/admin/apps", auth="admin")
    def r_admin_apps(self, user, query, **_):
        return self.store.admin_apps(force=query.get("refresh") == "1", user=user)

    @route("PUT", f"/api/admin/apps/{APP_ID}", auth="admin")
    def r_admin_update_app(self, user, params, **_):
        return self.store.admin_update_app(user, app_id(params), self.body())

    @route("GET", f"/api/admin/apps/{APP_ID}/codes", auth="admin")
    def r_codes(self, params, **_):
        return {"codes": self.store.list_codes(app_id(params))}

    @route("POST", f"/api/admin/apps/{APP_ID}/codes", auth="admin")
    def r_new_codes(self, user, params, **_):
        b = self.body()
        return {"codes": self.store.create_codes(user, app_id(params), b.get("count", 1), b.get("note", ""))}

    @route("DELETE", r"/api/admin/codes/(?P<code>[A-Za-z0-9-]+)", auth="admin")
    def r_delete_code(self, user, params, **_):
        self.store.delete_code(user, params["code"])
        return {"ok": True}

    @route("GET", "/api/admin/users", auth="admin")
    def r_users(self, **_):
        return {"users": self.store.list_users()}

    @route("PUT", r"/api/admin/users/(?P<id>\d+)", auth="admin")
    def r_set_role(self, user, params, **_):
        b = self.body()
        role = b.get("role") or ("admin" if b.get("is_admin") else "user")
        return {"user": self.store.set_role(user, int(params["id"]), role)}

    @route("POST", r"/api/admin/users/(?P<id>\d+)/developer", auth="admin")
    def r_decide_dev(self, user, params, **_):
        b = self.body()
        return {"user": self.store.decide_developer(user, int(params["id"]), bool(b.get("approve")),
                                                    b.get("note", ""))}

    @route("DELETE", r"/api/admin/users/(?P<id>\d+)", auth="admin")
    def r_delete_user(self, user, params, **_):
        self.store.delete_user(user, int(params["id"]))
        return {"ok": True}

    @route("POST", rf"/api/admin/users/(?P<id>\d+)/unlocks/{APP_ID}", auth="admin")
    def r_grant(self, params, **_):
        self.store.grant_unlock(int(params["id"]), app_id(params))
        return {"ok": True}

    @route("DELETE", rf"/api/admin/users/(?P<id>\d+)/unlocks/{APP_ID}", auth="admin")
    def r_revoke(self, params, **_):
        self.store.revoke_unlock(int(params["id"]), app_id(params))
        return {"ok": True}

    @route("POST", "/api/admin/announce", auth="admin")
    def r_announce(self, user, **_):
        b = self.body()
        return self.store.announce(user, b.get("subject", ""), b.get("message", ""))

    @route("GET", "/api/admin/purchases", auth="admin")
    def r_admin_purchases(self, **_):
        return {"purchases": self.store.admin_purchases()}

    @route("POST", r"/api/admin/purchases/(?P<id>\d+)/refund", auth="admin")
    def r_refund(self, user, params, **_):
        return self.store.refund_purchase(user, int(params["id"]))


def make_server(config: Config, sources: Sources = None, mailer=None, stripe=None) -> ThreadingHTTPServer:
    store = Store(config, Database(config.db_path), sources or Sources(config), mailer=mailer, stripe=stripe)
    handler = type("BoundHandler", (Handler,), {"store": store})
    server = ThreadingHTTPServer((config.host, config.port), handler)
    server.daemon_threads = True
    server.store = store
    return server


def drop_privileges(config: Config):
    """Im Docker-Container als root gestartet: Datenordner dem Dienstbenutzer geben, dann Rechte abgeben.

    So funktioniert ein frisch angelegter ./data-Ordner (gehört root) ohne manuelles chown.
    """
    uid = int(os.environ.get("RUN_AS_UID", "0") or 0)
    if not uid or os.geteuid() != 0:
        return
    gid = int(os.environ.get("RUN_AS_GID", str(uid)) or uid)
    dirs = {os.path.dirname(os.path.abspath(config.db_path)), config.data_dir}
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        for root, subdirs, files in os.walk(d):
            for name in [root] + [os.path.join(root, f) for f in subdirs + files]:
                st = os.lstat(name)
                if (st.st_uid, st.st_gid) != (uid, gid):
                    os.lchown(name, uid, gid)
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)
    log.info("Datenordner %s gehören jetzt UID %s, Server läuft ohne Root-Rechte", ", ".join(sorted(dirs)), uid)


CLI_HELP = """Verwaltung auf der Kommandozeile (im Container: docker exec bytedroide python store_server.py …):
  users                         alle Konten mit Rolle anzeigen
  set-role BENUTZER ROLLE       Rolle setzen: user, developer oder admin
  reset-password BENUTZER       neues Zufallspasswort setzen und anzeigen
Ohne Befehl startet der Server."""


def cli(config: Config, args: list) -> int:
    """Kleine Admin-Kommandozeile, arbeitet direkt auf der Datenbank."""
    db = Database(config.db_path)
    cmd = args[0]
    with db.connect() as conn:
        if cmd == "users" and len(args) == 1:
            for r in conn.execute("SELECT username, role, email, email_verified, dev_requested_at FROM users "
                                  "ORDER BY role, username COLLATE NOCASE"):
                extra = " (möchte Entwickler werden)" if r["dev_requested_at"] else ""
                print(f"{r['username']:<24} {r['role']:<10} {r['email'] or '-'}"
                      f"{'' if r['email_verified'] else ' (unbestätigt)'}{extra}")
            return 0
        if cmd == "set-role" and len(args) == 3:
            name, role = args[1], args[2].lower()
            if role not in ROLES:
                print(f"Rolle muss eins von {', '.join(ROLES)} sein", file=sys.stderr)
                return 2
            row = conn.execute("SELECT * FROM users WHERE username = ?", (name,)).fetchone()
            if not row:
                print(f"Benutzer {name} nicht gefunden (Liste: users)", file=sys.stderr)
                return 1
            if row["role"] == "admin" and role != "admin" and conn.execute(
                    "SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0] <= 1:
                print("Das ist der letzte Admin – zuerst jemand anderen zum Admin machen", file=sys.stderr)
                return 1
            conn.execute("UPDATE users SET role = ?, dev_requested_at = CASE WHEN ? = 'user' THEN dev_requested_at "
                         "ELSE NULL END WHERE id = ?", (role, role, row["id"]))
            print(f"{row['username']}: {row['role']} -> {role}")
            return 0
        if cmd == "reset-password" and len(args) == 2:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (args[1],)).fetchone()
            if not row:
                print(f"Benutzer {args[1]} nicht gefunden (Liste: users)", file=sys.stderr)
                return 1
            password = secrets.token_urlsafe(12)
            conn.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (hash_password(password), row["id"]))
            conn.execute("DELETE FROM sessions WHERE user_id = ? AND label IS NULL", (row["id"],))
            print(f"Neues Passwort für {row['username']}: {password}")
            return 0
    print(CLI_HELP, file=sys.stderr)
    return 2


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    config = Config()
    drop_privileges(config)
    if len(sys.argv) > 1:
        raise SystemExit(cli(config, sys.argv[1:]))
    db_dir = os.path.dirname(os.path.abspath(config.db_path))
    if not os.access(db_dir, os.W_OK):
        log.error("Kein Schreibrecht auf %s (läuft als UID %s). Lösung auf dem Host: chown -R %s:%s data",
                  db_dir, os.getuid(), os.getuid(), os.getgid())
        raise SystemExit(1)
    if config.forgejo_auto_import and not config.forgejo_token:
        log.warning("FORGEJO_TOKEN ist nicht gesetzt – nur öffentliche Forgejo-Repos sind sichtbar.")
    if not config.smtp_host:
        log.warning("SMTP_HOST ist nicht gesetzt – es werden keine E-Mails verschickt.")
    missing = legal.missing_fields(config)
    if missing:
        log.warning("Impressum unvollständig, bitte in .env setzen: %s", ", ".join(missing))
    server = make_server(config)
    log.info("ByteDroide-Server läuft auf %s:%s (%s)", config.host, config.port, config.public_url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
