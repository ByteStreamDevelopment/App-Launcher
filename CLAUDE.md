# Projektnotizen für Claude

- **Sprache**: Mit dem Nutzer immer auf Deutsch kommunizieren. UI-Texte der App, Mails und Rechtstexte sind deutsch.
- **Name**: **ByteDroide** (überall). Code-Namespace `com.bytestreamdevelopment.bytedroide`; die `applicationId` bleibt
  `com.bytestreamdevelopment.applauncher` (sonst bekämen bestehende Installationen keine Updates). Repo heißt App-Launcher.
- **Zweck**: Android-App-Store mit Entwickler-Konten (eigene Apps veröffentlichen), Betas, Kauf-Apps.
- **Architektur (seit v2)**: App / Entwickler-Portal (`server/web/portal.html`) → eigener **Store-Server**
  (`server/store_server.py`, Python-Stdlib + SQLite, Docker; dazu `mailer.py`, `legal.py`, `apk_info.py`)
  → Quellen GitHub / Forgejo/Gitea oder hochgeladene APKs. Server-Adresse in der App FEST `https://apps.nebendahl.eu`
  (`StoreSettings.SERVER_URL`).
- **Forgejo** `https://git.nebendahl.eu` (Gitea-1.22-kompatible API v1): optionaler Auto-Import aller Repos mit
  APK-Release (`FORGEJO_AUTO_IMPORT=1`) als Admin-Apps. Stabil = neuestes Nicht-Pre-Release mit `.apk`, Beta = neueres
  Pre-Release. Bekannt: `Manhunt/manhunt` (z. B. `v2.5.0`).
- **Rollen**: `user` / `developer` / `admin`. KEINE fest eingebauten Admins/Passwörter: das **erste registrierte Konto wird
  Admin**, Admins ernennen weitere. Letzter Admin nicht entfernbar. Entwickler-Konten werden normal registriert
  (`developer: true`) und vom Admin freigegeben. Neue Entwickler-Apps brauchen Admin-Prüfung (`review`).
- **App-IDs**: `besitzer/kurzname` (Entwickler-Apps: `benutzername/slug`, Forgejo-Import: `owner/repo`).
  Freigabe `open`/`code`/`hidden`, `price_cents` (>0 = Kauf nötig, Codes wirken als Gutschein), `beta` `off`/`open`/`closed`.
- **Upload-Prüfung**: Paketname fest pro App, `versionName` muss zur Version passen, `versionCode` muss steigen.
- **Käufe**: Stripe Checkout + Webhook (`/api/stripe/webhook`, HMAC-Signatur), Widerrufsfunktion in der App
  (14 Tage, Eingangsbestätigung per Mail), Erstattung durch Admin.
- **Mails**: SMTP über `SMTP_*`; ohne `SMTP_HOST` nur Log. **Rechtstexte**: `/impressum`, `/datenschutz`, `/agb`,
  `/widerruf`, Betreiberdaten aus `OPERATOR_*` (fehlende werden rot markiert). Nutzer muss echte Daten in `.env` eintragen.
- **Server testen**: `python3 -m unittest discover -s server/tests` (64 Tests, Fake-Forgejo/GitHub/Mailer/Stripe/ntfy/ClamAV, ~35 s).
  CLI im Container: `python store_server.py users | set-role NAME ROLLE | reset-password NAME`.
- **App testen**: `./gradlew assembleDebug testDebugUnitTest` (Versionsvergleich + `ApiContractTest` mit echten
  Server-Antworten aus `app/src/test/resources/api-samples.json`; bei API-Änderungen neu erzeugen).
- **Weitere Funktionen (Issue #2)**: Web-Store (`storefront.py`, QR per `qrcode_svg.py`, App Links über
  `/.well-known/assetlinks.json`), Bewertungen (`reviews`), Screenshots, Push über ntfy (`notify.py`, `users.ntfy_topic`),
  gestaffelte Rollouts (`releases.rollout`, Zuordnung per Konto/`X-Install-Id`), ClamAV (`scanner.py`),
  Versions-Prüfung (`REVIEW_RELEASES`, `releases.status`, bei Quellen `apps.pending_*`/`held_*`).
- **Web**: Startseite/Katalog/App-Seiten/Kontakt in `storefront.py` (serverseitig), Aktionen auf App-Seiten per
  `web/store.js`, komplette Web-App (Konto, Käufe, Nachrichten, Entwickler, Admin) in `web/app.html` unter `/konto`
  (Hash-Routing, Token in `localStorage` `bd_token`), Doku in `docs.py` unter `/hilfe`. `/portal` leitet auf `/konto` um.
- **Icons & Versionen**: App-Icon wird automatisch aus der APK gelesen (`apk_icon.py`: resources.arsc → größte Bitmap,
  sonst adaptive/Vektor-Icon → SVG; `apps.icon_auto`, hochgeladenes Icon hat Vorrang). App lädt SVG über `coil-svg`.
  Tags mit Präfix (`android-v1.0.24`) → Version `1.0.24` (Server `normalize_version`, App `Versions.normalize`, JS `ver()`).
  Web und App im Play-Store-Stil (Reihen, Top-Charts, Kennzahlen-Zeile).
- **Nachrichten**: `threads`/`messages` (gelesen über `user_read_id`/`dev_read_id`), Kontaktformular `contact_messages`.
- **Releases**: `.github/workflows/release.yml` bzw. `.forgejo/workflows/release.yml` bauen bei veröffentlichtem
  Release eine signierte APK (Keystore aus Secrets), Version per `scripts/version-from-tag.sh`, Upload in den Store.
- **GitHub-Repo**: `bytestreamdevelopment/app-launcher`.
- **App-Technik**: Kotlin, Jetpack Compose (Material 3), minSdk 26, targetSdk/compileSdk 35, AGP 8.7.3,
  Kotlin 2.0.21, Gradle-Wrapper 8.11.1, JDK 17. Keine Netzwerk-Bibliothek (HttpURLConnection + org.json), Coil für Bilder,
  WorkManager für die Update-Prüfung. Navigation über Stapel in `UiState.stack`. Deep-Link `bytedroide://app/{owner}/{name}`.
- **Installationslogik**: APK herunterladen → `getPackageArchiveInfo` liefert Paketnamen → Zuordnung App→Paket in
  SharedPreferences → Installation über `PackageInstaller`-Session (ab API 31 `USER_ACTION_NOT_REQUIRED`).
  Update-Erkennung: Tag (ohne `v`) vs. `versionName` (`Versions.isNewer`, Vorabversion < fertige Version).
- **Bauen in der Cloud-Sandbox**: Android SDK nach `/opt/android-sdk` installieren (cmdline-tools von dl.google.com;
  `platforms;android-35`, `build-tools;35.0.0`) und `local.properties` mit `sdk.dir=/opt/android-sdk` anlegen.
  Maven Central liefert gelegentlich 429 → einfach erneut bauen. Kein KVM → kein Emulator verfügbar.
