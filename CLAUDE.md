# Projektnotizen für Claude

- **Sprache**: Mit dem Nutzer immer auf Deutsch kommunizieren. UI-Texte der App sind deutsch.
- **Zweck**: Android-App-Store für selbst gebaute Apps des Nutzers.
- **Quelle**: Forgejo-Server `https://git.nebendahl.eu` (Forgejo 16 / Gitea-1.22-kompatible API v1).
  Es zählt immer das **neueste Release** (`/releases/latest`) eines Repos; Repos ohne `.apk`-Anhang werden ignoriert.
  Bekannte Benutzer/Orgs dort: `Mrcoolgamer11`, `Manhunt`, `ProfImpossible`.
  Stand 2026-11: einzige App mit APK-Release ist `Manhunt/manhunt` (z. B. `v2.5.0`, Asset `manhunt-v2.5.0.apk`).
- **GitHub-Repo**: `bytestreamdevelopment/app-launcher`.
- **Technik**: Kotlin, Jetpack Compose (Material 3), minSdk 26, targetSdk/compileSdk 35, AGP 8.7.3,
  Kotlin 2.0.21, Gradle-Wrapper 8.11.1, JDK 17. Keine Netzwerk-Bibliothek (HttpURLConnection + org.json), Coil für Bilder,
  WorkManager für die Update-Prüfung.
- **Paketname**: `com.bytestreamdevelopment.applauncher`.
- **Installationslogik**: APK herunterladen → `getPackageArchiveInfo` liefert Paketnamen → Zuordnung Repo→Paket in
  SharedPreferences → Installation über `PackageInstaller`-Session (ab API 31 `USER_ACTION_NOT_REQUIRED`).
  Update-Erkennung: Tag (ohne `v`) vs. `versionName` der installierten App (`Versions.isNewer`).
- **Bauen/Testen**: `./gradlew assembleDebug testDebugUnitTest`. In der Cloud-Sandbox: Android SDK nach `/opt/android-sdk`
  installieren (cmdline-tools von dl.google.com; `platforms;android-35`, `build-tools;35.0.0`) und
  `local.properties` mit `sdk.dir=/opt/android-sdk` anlegen. Maven Central liefert gelegentlich 429 → einfach erneut bauen.
  Kein KVM → kein Emulator verfügbar.
