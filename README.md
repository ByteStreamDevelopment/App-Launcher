# ByteDroide

ByteDroide ist ein eigener kleiner App Store für Android, der deine selbst gebauten Apps von deinem
Forgejo-Server (**https://git.nebendahl.eu**) installiert und aktuell hält – mit Admin-Bereich,
Einmal-Codes und Benutzerverwaltung.

```
Android-App  ──►  Store-Server (server/)  ──►  Forgejo (git.nebendahl.eu)
                  Benutzer, Admins, Freigaben,
                  Einmal-Codes, APK-Downloads
```

## Was er kann

- **Entdecken**: Jedes Repo, dessen **neuestes Release** eine `.apk` enthält, erscheint automatisch.
- **Installieren / Aktualisieren / Öffnen / Deinstallieren** mit einem Tipp, „Alle aktualisieren“.
- **Updates**: Release-Tag (`v2.5.0`) wird mit der installierten Version (`2.5.0`) verglichen;
  Hintergrund-Prüfung alle 6 Stunden mit Benachrichtigung.
- **Konten**: Anmelden/Registrieren. Ohne Konto sind alle offenen Apps nutzbar.
- **Admin-Bereich** (nur für Admins):
  - pro App die Freigabe wählen: **Offen** (jeder), **Mit Code** (nur nach Einlösen eines Einmal-Codes),
    **Versteckt** (nur Admins)
  - **Einmal-Codes** erzeugen (mit Notiz, z. B. „für Anna“), teilen, kopieren, löschen, sehen wer sie eingelöst hat
  - **Benutzerverwaltung**: andere zu Admins machen/zurückstufen, Konten löschen, Freischaltungen entziehen
- **Haupt-Admin** ist `ProfImpossible`. Dieses Konto lässt sich nur mit dem **Admin-Passwort** registrieren,
  kann nie zurückgestuft oder gelöscht werden.

## Einmal-Codes – so funktioniert's

1. Admin stellt eine App auf **Mit Code** und erzeugt einen Code (z. B. `K7QM-3XPA`).
2. Code an die Person schicken (Teilen-Knopf).
3. Die Person registriert sich in der App und tippt bei der App auf **Code** (oder Konto → „Freischalt-Code einlösen“).
4. Der Code ist danach verbraucht; die App bleibt für dieses Konto **dauerhaft** freigeschaltet, inkl. Updates.

> **Wichtig:** Ist das Repo auf Forgejo **öffentlich**, kann jeder die APK dort direkt herunterladen.
> Für echten Schutz das Repo auf **privat** stellen und dem Store-Server einen Forgejo-Token geben –
> dann kommt man nur noch über den Store (und mit Code) an die APK.

## Store-Server einrichten

Liegt in [`server/`](server/), nur Python-Standardbibliothek + SQLite, am einfachsten per Docker:

```bash
cd server
cp .env.example .env      # nur FORGEJO_TOKEN eintragen
docker compose up -d --build
```

Der Server läuft dann auf Port `8080`. Die App erwartet ihn fest unter **`https://apps.nebendahl.eu`** –
also im Reverse-Proxy `apps.nebendahl.eu` → `http://localhost:8080` eintragen und in `.env` `TRUST_PROXY=1` setzen.

Das **Admin-Passwort ist fest im Server eingebaut** (nur als scrypt-Hash `ADMIN_PASSWORD_HASH` in `store_server.py`)
und steht nicht in der `.env`. Ändern: neuen Hash erzeugen
(`python3 -c "import store_server as s; print(s.hash_password('NEU'))"`) und dort eintragen.
Die Datenbank liegt in `server/data/store.db` (Backup = diese Datei kopieren).

| Variable | Bedeutung |
|---|---|
| `FORGEJO_URL` | Forgejo-Adresse, Standard `https://git.nebendahl.eu` |
| `FORGEJO_TOKEN` | Token mit `read:repository` – nötig für private Repos |
| `ADMIN_USERNAME` | Haupt-Admin, Standard `ProfImpossible` |
| `OWNERS` | optional: nur Repos dieser Benutzer/Orgs (kommagetrennt) |
| `DEFAULT_ACCESS` | Freigabe neu entdeckter Apps: `open`, `code` oder `hidden` |
| `TRUST_PROXY` | `1` hinter Reverse-Proxy (echte IP für die Fehlversuch-Bremse) |

Ohne Docker: `cd server && python3 store_server.py`

Tests: `python3 -m unittest discover -s server/tests`

### Erste Schritte nach dem Start

1. App installieren (die Server-Adresse ist schon eingebaut).
2. Konto → **Registrieren** mit Benutzername `ProfImpossible`, eigenem Passwort und dem **Admin-Passwort**.
3. Oben erscheint das Werkzeug-Symbol → Admin-Bereich.

### Server-API (Kurzfassung)

| Methode & Pfad | Wer | Zweck |
|---|---|---|
| `POST /api/register`, `POST /api/login`, `POST /api/logout`, `GET /api/me` | alle | Konto |
| `GET /api/apps` | alle | Katalog (für den Benutzer gefiltert) |
| `GET /api/apps/{owner}/{repo}/download?asset=` | Berechtigte | APK |
| `POST /api/redeem` | angemeldet | Einmal-Code einlösen |
| `GET /api/admin/apps`, `PUT /api/admin/apps/{owner}/{repo}` | Admin | Apps & Freigabe |
| `GET/POST /api/admin/apps/{owner}/{repo}/codes`, `DELETE /api/admin/codes/{code}` | Admin | Codes |
| `GET /api/admin/users`, `PUT/DELETE /api/admin/users/{id}`, `DELETE /api/admin/users/{id}/unlocks/{owner}/{repo}` | Admin | Benutzer |

## So veröffentlichst du eine App im Store

1. In Forgejo im Repo deiner App ein **Release** anlegen (kein Entwurf, kein Pre-Release).
2. Die gebaute **`.apk` als Anhang** hochladen.
3. Fertig – der Store zeigt immer das **neueste** Release.

Tipps:

- **Tag = Version**: Benenne das Tag wie den `versionName` der App (`v1.2.3` ↔ `1.2.3`), dann erkennt der Store Updates zuverlässig.
- **`versionCode` erhöhen**: Android installiert ein Update nur, wenn der `versionCode` größer ist.
- **Immer mit demselben Schlüssel signieren**, sonst schlägt das Update fehl (dann vorher deinstallieren).
- Mehrere APKs pro Release? Bevorzugt wird eine Datei mit `universal` im Namen, dann die passende ABI (`arm64-v8a` …), sonst die erste.
- **Icon im Store**: Vor der Installation wird der Repo-Avatar angezeigt (Forgejo → Repo-Einstellungen → Avatar),
  sonst ein farbiger Anfangsbuchstabe. Nach der Installation das echte App-Icon.
- **Beschreibung**: Die Repo-Beschreibung erscheint im Store.

## Store bauen und installieren

Voraussetzungen: JDK 17+ und Android SDK (oder einfach Android Studio).

```bash
./gradlew assembleRelease
```

Die APK liegt dann unter `app/build/outputs/apk/release/`. Auf das Handy kopieren und installieren.
Beim ersten Installieren einer App fragt Android, ob der Store „unbekannte Apps installieren“ darf – erlauben.

### Eigener Signaturschlüssel (empfohlen)

Ohne Konfiguration wird mit dem Debug-Schlüssel signiert. Für stabile Updates einen eigenen anlegen:

```bash
keytool -genkey -v -keystore release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias store
```

und `keystore.properties` im Projektordner anlegen (wird nicht eingecheckt):

```properties
storeFile=release.jks
storePassword=...
keyAlias=store
keyPassword=...
```

Version beim Bauen setzen: `./gradlew assembleRelease -PappVersionName=1.1.0 -PappVersionCode=2`

### Der Store aktualisiert sich selbst

Lege für den Store selbst ein Repo auf deinem Forgejo an und veröffentliche seine APK als Release –
dann taucht er in seiner eigenen Liste auf und kann sich selbst aktualisieren.

## Aufbau

| Datei | Aufgabe |
|---|---|
| `server/store_server.py` | Store-Server: Forgejo-Abruf, Benutzer, Freigaben, Codes, Downloads |
| `data/StoreApi.kt` | Client für den Store-Server |
| `data/Catalog.kt` | Katalog laden, APK auswählen, Installationsstatus bestimmen |
| `data/Versions.kt` | Versionsvergleich Tag ↔ installierte Version |
| `data/StoreSettings.kt` | feste Server-Adresse (`SERVER_URL`), Sitzung, Zuordnung Repo → Paketname |
| `install/ApkInstaller.kt` | Download mit Fortschritt, Installation per `PackageInstaller` |
| `install/InstallResultReceiver.kt` | Ergebnis der Installation / Bestätigungsdialog |
| `work/UpdateCheckWorker.kt` | Hintergrund-Prüfung + Benachrichtigung |
| `ui/AccountScreen.kt` | Anmelden / Registrieren / Code einlösen |
| `ui/AdminScreens.kt`, `ui/AdminViewModel.kt` | Admin-Bereich: Freigaben, Codes, Benutzer |
| `ui/*` | übrige Oberfläche (Jetpack Compose, Material 3) |

Der Server nutzt von Forgejo: `GET /api/v1/repos/search`, `GET /api/v1/repos/{owner}/{repo}/releases/latest`.
