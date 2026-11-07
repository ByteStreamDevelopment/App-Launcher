# App Store (App-Launcher)

Ein eigener kleiner App Store für Android, der deine selbst gebauten Apps direkt
von deinem Forgejo-Server (**https://git.nebendahl.eu**) installiert und aktuell hält.

## Was er kann

- **Entdecken**: Zeigt automatisch jedes Repo, dessen **neuestes Release** eine `.apk` enthält.
- **Installieren / Aktualisieren / Öffnen / Deinstallieren** mit einem Tipp.
- **Updates**: Vergleicht das Release-Tag (`v2.5.0`) mit der installierten Version (`versionName` = `2.5.0`).
  „Alle aktualisieren“ in einem Rutsch.
- **Hintergrund-Prüfung** alle 6 Stunden mit Benachrichtigung bei neuen Versionen.
- Ab Android 12 laufen Updates von Apps, die der Store installiert hat, **ohne Bestätigungsdialog**.
- Suche, Release-Notizen, Größe, Datum, Links zum Repo.
- Optional: Filter auf bestimmte Benutzer/Organisationen und Token für private Repos.

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
| `data/ForgejoApi.kt` | Forgejo-API: Repos suchen, neuestes Release holen |
| `data/Catalog.kt` | Katalog aufbauen, APK auswählen, Installationsstatus bestimmen |
| `data/Versions.kt` | Versionsvergleich Tag ↔ installierte Version |
| `data/StoreSettings.kt` | Einstellungen, Zuordnung Repo → Paketname |
| `install/ApkInstaller.kt` | Download mit Fortschritt, Installation per `PackageInstaller` |
| `install/InstallResultReceiver.kt` | Ergebnis der Installation / Bestätigungsdialog |
| `work/UpdateCheckWorker.kt` | Hintergrund-Prüfung + Benachrichtigung |
| `ui/*` | Oberfläche (Jetpack Compose, Material 3) |

Benutzte API-Endpunkte: `GET /api/v1/repos/search`, `GET /api/v1/repos/{owner}/{repo}/releases/latest`.
