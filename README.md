# ByteDroide

ByteDroide ist ein eigener App-Store für Android: Entwicklerinnen und Entwickler veröffentlichen ihre Apps
(aus GitHub/Forgejo oder per APK-Upload), Nutzer installieren und aktualisieren sie mit einem Tipp – mit
Beta-Kanal, Freischalt-Codes, kostenpflichtigen Apps, E-Mail-Benachrichtigungen und vollständigen Rechtstexten.

```
Android-App  ──►  Store-Server (server/)  ──►  GitHub · Forgejo/Gitea · hochgeladene APKs
Entwickler-Portal (Browser) ─┘   Konten, Rollen, Freigaben, Codes, Käufe (Stripe), E-Mails (SMTP)
```

## Funktionen

**Für alle**
- Apps entdecken (Suche, Kategorien), installieren, aktualisieren, öffnen, deinstallieren, „Alle aktualisieren“
- Update-Prüfung im Hintergrund (alle 6 Stunden) mit Benachrichtigung
- Ohne Konto nutzbar für alle offenen, kostenlosen Apps

**Mit Konto**
- Registrierung mit E-Mail-Bestätigung, „Passwort vergessen“, Passwort/E-Mail ändern
- Freischalt-Codes einlösen, Apps kaufen, Beta-Tester werden
- E-Mail-Benachrichtigungen (ein-/ausschaltbar): Updates genutzter Apps, Neuigkeiten
- Meine Käufe inkl. **„Vertrag widerrufen“**, Daten exportieren, Konto selbst löschen (DSGVO)

**Rollen**
| Rolle | Wie | Darf |
|---|---|---|
| Benutzer | normale Registrierung | Apps nutzen, kaufen, testen |
| Entwickler | bei der Registrierung (oder später im Konto) beantragen, **Admin gibt frei** | eigene Apps veröffentlichen und verwalten |
| Admin | **das erste registrierte Konto** – danach ernennen Admins weitere Admins | alles: Rollen, Anfragen, App-Prüfung, Käufe, Rundmails |

Es gibt **keine fest eingebauten Admin-Konten oder Passwörter** mehr. Der letzte Admin kann weder
zurückgestuft noch gelöscht werden.

**Für Entwickler** (in der App unter Konto → Entwickler-Bereich oder im Browser unter `/portal`)
- App anlegen mit **Quelle** (GitHub, Forgejo, Gitea, Codeberg – auch private Repos per Token) **oder Upload**
- APK hochladen: Paketname, `versionName` und `versionCode` werden aus der APK gelesen und geprüft
  (falsche App, falsche Version oder nicht steigender `versionCode` werden abgelehnt)
- Kanäle **Stabil** und **Beta** (bei Quellen: Pre-Releases = Beta); Beta-Programm offen oder nur auf Einladung
- Freigabe: offen / nur mit Code / versteckt; **Preis** (0,50 €–1000 €); Icon, Kategorie, Webseite
- Freischalt-Codes (wirken bei Kauf-Apps als Gutschein), Beta-Tester einladen
- Statistik: Downloads, 30 Tage, Verkäufe, Umsatz
- **API-Schlüssel** für automatische Uploads aus CI

**App-Prüfung**: Neue Apps von Entwicklern sind erst sichtbar, wenn ein Admin sie freigibt
(Entwickler bekommt eine E-Mail, bei Ablehnung mit Begründung).

## Web-Store, Bewertungen & mehr

- **Web-Store im Browser** unter `https://apps.nebendahl.eu/`: Katalog mit Suche und Kategorien, App-Seiten mit
  Screenshots, Bewertungen, Versionshinweisen und **QR-Code** (`/app/{id}`, als Datei unter `/app/{id}/qr.svg`).
  Freie, offene Apps lassen sich dort auch direkt als APK laden.
  Mit `ANDROID_CERT_SHA256` liefert der Server `/.well-known/assetlinks.json` aus – dann öffnet ein gescannter
  QR-Code direkt ByteDroide (Android App Links).
- **Bewertungen**: 1–5 Sterne mit Text, nur wer die App über ByteDroide geladen hat; Entwickler können antworten,
  Admins moderieren. Durchschnitt erscheint in der App-Liste und im Web-Store.
- **Screenshots**: bis zu 8 pro App (App, Portal oder `POST /api/dev/apps/{id}/screenshots`).
- **Push über ntfy** (ohne Google): Konto → „Push über ntfy“ erzeugt ein geheimes Thema, das man in der ntfy-App
  abonniert. Alle Benachrichtigungen (Updates, Freigaben, Antworten …) kommen dann zusätzlich als Push.
- **Gestaffelte Rollouts**: Beim Upload (stabiler Kanal) z. B. erst 10 % der Nutzer; später auf 100 % erhöhen.
  Die Zuordnung ist stabil je Konto bzw. Gerät. Update-Benachrichtigungen gehen erst bei 100 % raus.
- **Virenscan** mit ClamAV: Uploads werden vor dem Speichern geprüft, neue Versionen aus Quellen vor der
  Auslieferung. Funde werden gesperrt und den Admins gemeldet. Starten:
  `docker compose --profile clamav up -d` und `CLAMAV_HOST=clamav` in der `.env`.
- **Prüfung neuer Versionen** (`REVIEW_RELEASES=1`): Neue Versionen von Entwicklern werden erst nach Freigabe im
  Admin-Bereich (Anfragen) ausgeliefert – bis dahin bekommen Nutzer die bisherige.

## E-Mails

Alle Mails sind als schönes HTML (mit Text-Alternative) gestaltet und enthalten Impressum-/Datenschutz-Links:
E-Mail bestätigen · Passwort zurücksetzen · Passwort/E-Mail geändert · Entwickler-Anfrage (an Admins) ·
Entwickler freigeschaltet/abgelehnt · Rolle geändert · neue App zur Prüfung (an Admins) · App freigegeben/abgelehnt ·
neue Version (an Nutzer der App, wenn eingeschaltet) · neue Beta (an Tester) · Beta-Einladung ·
Kaufbeleg · Verkauf (an Entwickler) · Widerruf-Eingangsbestätigung (an Käufer und Betreiber) · Erstattung ·
Konto gelöscht · Rundmails der Admins (nur an Abonnenten von „Neuigkeiten“).

Ohne `SMTP_HOST` läuft alles weiter, Mails werden dann nur ins Log geschrieben.

## Kostenpflichtige Apps

- Bezahlung über **Stripe Checkout** (Karte, PayPal, Apple/Google Pay … je nach Stripe-Einstellung).
  Die App öffnet die Bezahlseite im Browser, Stripe meldet die Zahlung per Webhook, die App wird sofort freigeschaltet.
- Vor dem Kauf stimmt der Käufer der sofortigen Bereitstellung zu (Erlöschen des Widerrufsrechts, § 356 Abs. 5 BGB);
  der Kaufbeleg per E-Mail ist die Vertragsbestätigung auf dauerhaftem Datenträger.
- **Widerrufsfunktion**: In der App unter Konto → Meine Käufe → „Vertrag widerrufen“ (14 Tage), mit sofortiger
  Eingangsbestätigung per E-Mail. Admins erstatten im Admin-Bereich → Käufe (Rückzahlung über die Stripe-API).
- Ohne Stripe-Schlüssel funktionieren Kauf-Apps nur über Codes (Gutscheine).

> Wer Apps verkauft, handelt in der Regel gewerblich (Gewerbeanmeldung, Steuern, ggf. Kleinunternehmerregelung).
> Die mitgelieferten Rechtstexte sind eine sorgfältige Vorlage, ersetzen aber keine Rechtsberatung.

## Rechtstexte

Der Server liefert `/impressum`, `/datenschutz`, `/agb` (Nutzungsbedingungen inkl. Entwickler- und Kaufbedingungen)
und `/widerruf` (Widerrufsbelehrung + Muster-Formular). Die App verlinkt sie unter Einstellungen → Rechtliches,
bei der Registrierung und beim Kauf; die Mails im Fußbereich.

Die Betreiberangaben kommen aus der `.env` (`OPERATOR_*`). **Fehlende Pflichtangaben werden auf der Seite rot
markiert** und im Admin-Bereich angezeigt.

## Store-Server einrichten

Liegt in [`server/`](server/), nur Python-Standardbibliothek + SQLite, am einfachsten per Docker:

```bash
cd server
cp .env.example .env      # Betreiberdaten, SMTP, Forgejo-Token, optional Stripe eintragen
docker compose up -d --build
```

Der Container hängt im externen Docker-Netzwerk **`reverse-proxy`** (ohne veröffentlichten Port) und ist dort für
Caddy unter `http://bytedroide:8080` erreichbar. Falls das Netzwerk noch nicht existiert:
`docker network create reverse-proxy` (Caddy muss ebenfalls darin hängen).

Caddy-Konfiguration für **`https://apps.nebendahl.eu`** (fest in der App eingebaut): siehe
[`server/Caddyfile.example`](server/Caddyfile.example) – Block ins eigene Caddyfile übernehmen und Caddy neu laden.
Sie erlaubt APK-Uploads bis 210 MB, lange Up-/Downloads und behält Zugriffsprotokolle 14 Tage (wie in der
Datenschutzerklärung angegeben).

**Erste Schritte:** App installieren → Konto → Registrieren. Das **erste Konto wird automatisch Admin.**

Daten liegen in `server/data/` (`store.db` + `files/` mit hochgeladenen APKs und Icons) – Backup = Ordner kopieren.
Eine bestehende Datenbank aus Version 1.x wird beim Start automatisch übernommen (Admins bleiben Admins).

| Variable | Bedeutung |
|---|---|
| `PUBLIC_URL` | öffentliche Adresse (Links in Mails, Rechtstexte), Standard `https://apps.nebendahl.eu` |
| `OPERATOR_NAME`, `_STREET`, `_CITY`, `_EMAIL` | **Pflicht** für Impressum/Datenschutz |
| `OPERATOR_PHONE`, `_VAT_ID`, `_RESPONSIBLE`, `_HOSTING`, `_MAIL_PROVIDER`, `_AUTHORITY`, `KLEINUNTERNEHMER` | optional |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | E-Mail-Versand |
| `FORGEJO_URL`, `FORGEJO_TOKEN` | Forgejo-Server und Token (`read:repository`) |
| `FORGEJO_AUTO_IMPORT` | `1` = alle Forgejo-Repos mit APK-Release automatisch als Admin-Apps übernehmen |
| `OWNERS` | optional: nur Repos dieser Benutzer/Orgs importieren |
| `DEFAULT_ACCESS` | Freigabe neu importierter Apps: `open`, `code`, `hidden` |
| `GITHUB_TOKEN` | optional, höheres Abruf-Limit bei GitHub-Quellen |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `CURRENCY` | Bezahlung (Webhook: `https://…/api/stripe/webhook`) |
| `MAX_UPLOAD_MB` | maximale APK-Größe (Standard 200) |
| `STORE_APP_ID` | App, die unter `/download` angeboten wird (z. B. ByteDroide selbst) |
| `NTFY_URL`, `NTFY_TOKEN` | Push über ntfy (Standard `https://ntfy.sh`, leer = aus) |
| `CLAMAV_HOST`, `CLAMAV_PORT`, `CLAMAV_REQUIRED` | Virenscan mit ClamAV |
| `REVIEW_RELEASES` | `1` = neue Versionen von Entwicklern erst nach Admin-Freigabe |
| `ANDROID_CERT_SHA256` | Zertifikats-Fingerabdruck für App Links (QR-Codes öffnen die App) |
| `TRUST_PROXY` | `1` hinter Reverse-Proxy (in `docker-compose.yml` bereits gesetzt) |

Ohne Docker: `cd server && python3 store_server.py`

**Verwaltung per Kommandozeile** (z. B. wenn man sich ausgesperrt hat):

```bash
docker exec bytedroide python store_server.py users
docker exec bytedroide python store_server.py set-role Mrcoolgamer11 admin
docker exec bytedroide python store_server.py reset-password BENUTZER
```

Tests: `python3 -m unittest discover -s server/tests`

### Stripe einrichten (optional)

1. Im Stripe-Dashboard den geheimen Schlüssel als `STRIPE_SECRET_KEY` eintragen.
2. Webhook anlegen: URL `https://apps.nebendahl.eu/api/stripe/webhook`, Ereignisse
   `checkout.session.completed` und `checkout.session.async_payment_succeeded`; das Signing-Secret als
   `STRIPE_WEBHOOK_SECRET` eintragen.

### Automatisch aus CI veröffentlichen

Im Portal (`/portal`) einen API-Schlüssel erstellen und als Secret hinterlegen, dann z. B. in GitHub Actions:

```yaml
- name: In ByteDroide veröffentlichen
  run: |
    curl --fail -X POST -H "Authorization: Bearer ${{ secrets.BYTEDROIDE_KEY }}" \
      --data-binary @app/build/outputs/apk/release/app-release.apk \
      "https://apps.nebendahl.eu/api/dev/apps/NAME/APP/releases?channel=stable"
```

## Server-API (Kurzfassung)

| Methode & Pfad | Wer | Zweck |
|---|---|---|
| `POST /api/register`, `/api/login`, `/api/logout`, `/api/password/forgot` | alle | Konto |
| `GET/PUT/DELETE /api/me`, `POST /api/me/password`, `/api/me/verify`, `/api/me/developer`, `GET /api/me/export` | angemeldet | eigenes Konto |
| `GET /api/me/purchases`, `POST /api/me/purchases/{id}/withdraw` | angemeldet | Käufe, Widerruf |
| `GET /api/apps`, `GET /api/apps/{id}/download`, `GET /api/apps/{id}/icon` | alle | Katalog, APK, Icon |
| `POST/DELETE /api/apps/{id}/beta`, `POST /api/apps/{id}/purchase`, `POST /api/redeem` | angemeldet | Beta, Kauf, Code |
| `GET/POST /api/dev/apps`, `GET/PUT/DELETE /api/dev/apps/{id}` | Entwickler | eigene Apps |
| `GET/POST /api/dev/apps/{id}/releases`, `DELETE …/releases/{rid}`, `POST …/icon` | Entwickler | Versionen, Icon |
| `…/codes`, `…/testers`, `GET/POST/DELETE /api/dev/keys` | Entwickler | Codes, Tester, API-Schlüssel |
| `GET /api/admin/overview`, `/api/admin/apps`, `PUT /api/admin/apps/{id}` | Admin | Übersicht, Prüfung |
| `GET /api/admin/users`, `PUT/DELETE /api/admin/users/{id}`, `POST …/developer` | Admin | Rollen, Anfragen |
| `GET /api/admin/purchases`, `POST …/{id}/refund`, `POST /api/admin/announce` | Admin | Käufe, Rundmail |
| `POST /api/stripe/webhook` | Stripe | Zahlungsbestätigung |

`{id}` ist immer `besitzer/kurzname`, z. B. `anna/super-spiel` oder `Manhunt/manhunt`.

## Tipps zum Veröffentlichen

- **Tag/Version = `versionName`** der App (`v1.2.3` ↔ `1.2.3`), sonst erkennt der Store Updates nicht.
  Beim Upload wird das automatisch geprüft.
- **`versionCode` erhöhen** – Android installiert Updates nur mit größerem `versionCode`.
- **Immer mit demselben Schlüssel signieren**, sonst schlägt das Update fehl.
- Beta-Versionen z. B. `1.3.0-beta1`: Sie gelten als älter als `1.3.0`, Tester bekommen die fertige Version also
  automatisch, sobald sie erscheint.
- Mehrere APKs pro Release? Bevorzugt wird `universal`, dann die passende ABI (`arm64-v8a` …), sonst die erste.

## App bauen

Voraussetzungen: JDK 17+ und Android SDK (oder Android Studio).

```bash
./gradlew assembleRelease
```

Die APK liegt unter `app/build/outputs/apk/release/`. Version setzen:
`./gradlew assembleRelease -PappVersionName=2.0.0 -PappVersionCode=5`

Eigener Signaturschlüssel (empfohlen): `keytool -genkey -v -keystore release.jks -keyalg RSA -keysize 2048
-validity 10000 -alias store` und `keystore.properties` anlegen (wird nicht eingecheckt):

```properties
storeFile=release.jks
storePassword=...
keyAlias=store
keyPassword=...
```

Der Paketname (`applicationId`) bleibt `com.bytestreamdevelopment.applauncher`, damit bestehende Installationen
Updates bekommen; der Code liegt im Namespace `com.bytestreamdevelopment.bytedroide`.

### Automatisch bei jedem GitHub-Release bauen

`.github/workflows/release.yml` baut bei jedem **Tag `v*`** (z. B. `git push origin v2.1.0` oder ein Release auf
GitHub) eine signierte APK, legt bei Bedarf das Release an, hängt die APK daran und lädt sie in den Store hoch (Pre-Releases wie `v2.2.0-beta1` → Beta-Kanal).
`versionName` kommt aus dem Tag, `versionCode` wird daraus berechnet (`2.1.3` → `2010300`, Vorabversionen etwas
kleiner), steigt also automatisch.

Einmalig einrichten:
1. Signaturschlüssel erzeugen (siehe oben) und als Secrets anlegen (Repo → Settings → Secrets and variables → Actions):
   `KEYSTORE_BASE64` (Ausgabe von `base64 -w0 release.jks`), `KEYSTORE_PASSWORD`, `KEY_ALIAS`, `KEY_PASSWORD`.
2. Im Entwickler-Portal eine App mit Kurzname z. B. `bytedroide` und Quelle „APK hochladen“ anlegen und einen
   API-Schlüssel erstellen → Secret `BYTEDROIDE_API_KEY`, Variable `BYTEDROIDE_APP` = `DEINNAME/bytedroide`.
3. In `server/.env` `STORE_APP_ID=DEINNAME/bytedroide` setzen → die APK gibt es dann auch unter `/download`.

Danach genügt `git tag v2.1.0 && git push origin v2.1.0` – oder GitHub → Releases → „Draft a new release“ → Tag `v2.1.0` → Publish.

**Mit Forgejo statt GitHub:** `.forgejo/workflows/release.yml` macht dasselbe auf einem Forgejo-Runner (für einen
Spiegel des Repos auf Forgejo; `runs-on` ggf. an das Label deines Runners anpassen). Die APK wird an das
Forgejo-Release gehängt; mit `FORGEJO_AUTO_IMPORT=1` übernimmt der Store sie dann automatisch – `BYTEDROIDE_API_KEY`
in dem Fall nicht setzen, sonst gibt es die App doppelt. Secrets wie bei GitHub, optional `RELEASE_TOKEN`.

**Der Store aktualisiert sich selbst**, wenn er als App im eigenen Katalog liegt (z. B. per Upload oder Forgejo-Release);
mit `STORE_APP_ID` ist er außerdem unter `https://apps.nebendahl.eu/download` erhältlich.

## Aufbau

| Datei | Aufgabe |
|---|---|
| `server/store_server.py` | Store-Server: Konten, Rollen, Apps, Quellen, Uploads, Betas, Käufe, API |
| `server/mailer.py` | HTML-E-Mails und SMTP-Versand im Hintergrund |
| `server/legal.py` | Impressum, Datenschutz, Nutzungsbedingungen, Widerruf |
| `server/apk_info.py` | liest Paketname/Version aus APKs (binäres AndroidManifest) |
| `server/web/portal.html` | Entwickler-Portal im Browser |
| `data/StoreApi.kt` | Client für den Store-Server |
| `data/Catalog.kt`, `data/Versions.kt` | Katalog, APK-Auswahl, Versionsvergleich (inkl. Beta) |
| `install/*` | Download mit Fortschritt, Installation per `PackageInstaller` |
| `work/UpdateCheckWorker.kt` | Hintergrund-Prüfung + Benachrichtigung |
| `ui/AccountScreen.kt` | Anmelden, Registrieren, Konto, Käufe, Kauf-Dialog |
| `ui/DevScreens.kt`, `ui/DevViewModel.kt` | Entwickler-Bereich |
| `ui/AdminScreens.kt`, `ui/AdminViewModel.kt` | Admin-Bereich |
| `ui/*` | übrige Oberfläche (Jetpack Compose, Material 3) |
