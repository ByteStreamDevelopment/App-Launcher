"""Hilfe & Dokumentation (/hilfe) für Nutzer, Entwickler und Betreiber."""

import html

import storefront

DOC_CSS = """<style>
.docs{display:grid;grid-template-columns:250px 1fr;gap:20px;align-items:start}
@media (max-width:860px){.docs{grid-template-columns:1fr}}
.docs nav.side{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:14px;position:sticky;top:12px}
.docs nav.side h4{margin:12px 8px 4px;font-size:12px;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}
.docs nav.side a{display:block;padding:6px 10px;border-radius:10px;text-decoration:none;color:var(--text);font-size:15px}
.docs nav.side a.on{background:var(--chip);color:var(--brand);font-weight:700}
.docs article{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:24px 28px;min-width:0}
.docs article h1{margin:0 0 6px;font-size:30px}.docs article h2{margin:26px 0 8px;font-size:21px}
.docs article h3{margin:18px 0 6px;font-size:17px}.docs article p,.docs article li{color:var(--text)}
.docs article code{background:var(--chip);padding:1px 6px;border-radius:6px;font-size:14px}
.docs article pre{background:var(--chip);padding:14px;border-radius:12px;overflow-x:auto;font-size:13px}
.docs article pre code{background:none;padding:0}
.docs table{border-collapse:collapse;width:100%;font-size:14px;display:block;overflow-x:auto}
.docs td,.docs th{border-bottom:1px solid var(--border);padding:8px 10px;text-align:left;vertical-align:top}
.docs .tip{background:var(--chip);border-radius:12px;padding:12px 16px;margin:14px 0}
.docs .cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;margin-top:14px}
.docs .cards a{background:var(--bg);border:1px solid var(--border);border-radius:14px;padding:14px;text-decoration:none;color:inherit}
.docs .cards a b{display:block;color:var(--brand)}
.docs .next{display:flex;justify-content:space-between;gap:10px;margin-top:28px;flex-wrap:wrap}
</style>"""

# (Bereich, Slug, Titel, Inhalt) – Inhalt ist HTML, {base} wird ersetzt
PAGES = [
    ("Für Nutzer", "erste-schritte", "Erste Schritte", """
<p>ByteDroide ist ein App-Store für Android. Du installierst darüber Apps unabhängiger Entwicklerinnen und Entwickler
und bekommst Updates automatisch.</p>
<h2>1. ByteDroide installieren</h2>
<ol><li>Auf dem Handy <a href="{base}/download">{base}/download</a> öffnen (oder den QR-Code auf der
<a href="{base}/">Startseite</a> scannen).</li>
<li>Die heruntergeladene Datei öffnen. Android fragt, ob der Browser „unbekannte Apps installieren“ darf –
erlauben.</li>
<li>Auf <b>Installieren</b> tippen.</li></ol>
<h2>2. Apps installieren</h2>
<p>In ByteDroide eine App antippen und <b>Installieren</b> wählen. Beim ersten Mal fragt Android, ob ByteDroide
Apps installieren darf – erlauben und zurückkehren. Danach geht es mit einem Tipp.</p>
<h2>3. Konto (optional)</h2>
<p>Offene, kostenlose Apps funktionieren ohne Konto. Für Freischalt-Codes, Käufe, Betas, Bewertungen, Nachrichten an
Entwickler und Benachrichtigungen brauchst du ein <a href="{base}/konto#/login">kostenloses Konto</a>.</p>
<div class="tip">Du kannst ByteDroide auch im Browser nutzen: Apps ansehen, kaufen, Codes einlösen, bewerten und
Entwicklern schreiben. Nur das automatische Installieren und Aktualisieren geht ausschließlich in der App.</div>"""),
    ("Für Nutzer", "updates", "Installieren & Updates", """
<h2>Updates</h2>
<p>ByteDroide vergleicht die installierte Version jeder App mit der neuesten im Store. Verfügbare Updates findest du
im Tab <b>Updates</b>; „Alle aktualisieren“ erledigt alles auf einmal. Im Hintergrund prüft ByteDroide alle sechs
Stunden und meldet sich mit einer Benachrichtigung (abschaltbar in den Einstellungen).</p>
<p>Ab Android 12 laufen Updates von Apps, die ByteDroide installiert hat, ohne weitere Rückfrage.</p>
<h2>Probleme beim Installieren</h2>
<ul><li><b>„App nicht installiert“ / Paketkonflikt:</b> Die installierte App wurde mit einem anderen Schlüssel signiert
(z. B. aus einer anderen Quelle). Einmal deinstallieren und über ByteDroide neu installieren.</li>
<li><b>Installation wird blockiert:</b> In den Android-Einstellungen für ByteDroide „Unbekannte Apps installieren“
erlauben (ByteDroide → Einstellungen → Installationsberechtigung).</li>
<li><b>Update wird nicht angezeigt:</b> Liste nach unten ziehen zum Aktualisieren. Bei gestaffelten Rollouts bekommen
nicht alle Nutzer eine neue Version gleichzeitig.</li></ul>"""),
    ("Für Nutzer", "konto", "Konto & Datenschutz", """
<h2>Konto erstellen</h2>
<p>Benutzername, E-Mail-Adresse und Passwort (mindestens 8 Zeichen) genügen. Danach bekommst du eine E-Mail zum
Bestätigen der Adresse – erst dann gibt es E-Mail-Benachrichtigungen und „Passwort vergessen“.</p>
<h2>Passwort vergessen</h2>
<p>Beim Anmelden auf „Passwort vergessen?“ tippen und Benutzername oder E-Mail eingeben. Der Link in der E-Mail ist eine
Stunde gültig.</p>
<h2>Deine Daten</h2>
<ul><li><b>Exportieren:</b> Konto → „Meine Daten exportieren“ (App) bzw. <a href="{base}/konto">Mein Konto</a> (Web).</li>
<li><b>Löschen:</b> Konto → „Konto löschen“. Freischaltungen, Beta-Teilnahmen, Bewertungen und Nachrichten werden
entfernt; Kaufbelege bleiben nur so lange, wie es das Gesetz verlangt.</li></ul>
<p>Mehr in der <a href="{base}/datenschutz">Datenschutzerklärung</a>.</p>"""),
    ("Für Nutzer", "benachrichtigungen", "Benachrichtigungen & ntfy", """
<p>ByteDroide benachrichtigt dich über Updates deiner Apps, Antworten von Entwicklern, Kaufbelege und mehr – per
E-Mail und auf Wunsch als <b>Push-Nachricht über ntfy</b>, ganz ohne Google-Dienste.</p>
<h2>Push über ntfy einrichten</h2>
<ol><li>Die kostenlose App <b>ntfy</b> installieren (F-Droid oder Play Store).</li>
<li>In ByteDroide: Konto → „Push über ntfy“ einschalten. ByteDroide erzeugt ein geheimes, persönliches Thema.</li>
<li>„In ntfy abonnieren“ tippen – fertig. Mit „Test senden“ kannst du es ausprobieren.</li></ol>
<div class="tip">Das Thema ist wie ein Passwort: Wer es kennt, kann deine Benachrichtigungen mitlesen. Bei Bedarf
„Neues Thema erzeugen“.</div>
<h2>E-Mails abbestellen</h2>
<p>Konto → Benachrichtigungen: „Updates meiner Apps“ und „Neuigkeiten“ lassen sich einzeln abschalten.</p>"""),
    ("Für Nutzer", "beta", "Beta-Versionen", """
<p>Viele Apps bieten Vorabversionen an. Auf der App-Seite „Beta-Tester werden“ wählen – ab dann bekommst du die
neueste Beta, sobald sie erscheint. Beta-Versionen können Fehler enthalten; Feedback hilft den Entwicklern sehr
(siehe <a href="{base}/hilfe/feedback">Feedback & Nachrichten</a>).</p>
<p>„Beta verlassen“ bringt dich zurück zum stabilen Kanal. Erscheint die fertige Version, bekommst du sie automatisch
(eine Vorabversion wie <code>1.3.0-beta2</code> gilt als älter als <code>1.3.0</code>).</p>
<p>Manche Beta-Programme sind geschlossen – dann lädt dich der Entwickler persönlich ein.</p>"""),
    ("Für Nutzer", "codes-und-kaeufe", "Codes & Käufe", """
<h2>Freischalt-Codes</h2>
<p>Manche Apps gibt es nur mit Code (z. B. für Tester oder Kunden). Den Code bekommst du vom Entwickler und löst ihn
unter Konto → „Freischalt-Code einlösen“ ein. Danach ist die App dauerhaft für dein Konto freigeschaltet. Bei
kostenpflichtigen Apps funktionieren Codes als Gutschein.</p>
<h2>Apps kaufen</h2>
<p>Bei kostenpflichtigen Apps auf den Preis tippen. Bezahlt wird sicher über Stripe; danach ist die App sofort
freigeschaltet und du bekommst einen Kaufbeleg per E-Mail. Käufe gelten für dein Konto – auch auf neuen Geräten.</p>
<h2>Widerruf</h2>
<p>Unter Konto → „Meine Käufe“ kannst du einen Kauf innerhalb von 14 Tagen über „Vertrag widerrufen“ widerrufen. Du
bekommst sofort eine Eingangsbestätigung. Einzelheiten in der <a href="{base}/widerruf">Widerrufsbelehrung</a>.</p>"""),
    ("Für Nutzer", "feedback", "Bewertungen & Nachrichten", """
<h2>Bewerten</h2>
<p>Hast du eine App über ByteDroide geladen, kannst du sie mit 1–5 Sternen und einem Text bewerten. Deine Bewertung
ist mit deinem Benutzernamen öffentlich; du kannst sie jederzeit ändern oder löschen. Entwickler können öffentlich
antworten.</p>
<h2>Fehler melden, Feedback, Fragen</h2>
<p>Auf jeder App-Seite (App oder Web) gibt es „Entwickler kontaktieren“. Wähle die Art (Fehlermeldung, Feedback,
Frage), beschreibe dein Anliegen – bei Fehlermeldungen aus der App werden Gerät, Android-Version und App-Version
automatisch mitgeschickt. Der Entwickler bekommt eine Benachrichtigung und kann dir antworten. Alle Gespräche
findest du unter Konto → Nachrichten.</p>
<div class="tip">Gute Fehlermeldungen enthalten: Was hast du gemacht? Was ist passiert? Was hättest du erwartet?</div>
<h2>Etwas melden</h2>
<p>Verstößt eine App gegen Gesetze (z. B. Schadsoftware, Urheberrechtsverletzung)? Bitte über das
<a href="{base}/kontakt?thema=meldung">Kontaktformular</a> melden.</p>"""),

    ("Für Entwickler", "entwickler", "Überblick für Entwickler", """
<p>Mit einem Entwickler-Konto veröffentlichst du eigene Android-Apps in ByteDroide – kostenlos, mit Code oder gegen
Bezahlung, mit Betas, gestaffelten Rollouts, Statistiken und direktem Kontakt zu deinen Nutzern.</p>
<h2>Zugang bekommen</h2>
<ol><li><a href="{base}/konto#/login?entwickler=1">Konto erstellen</a> und „Ich möchte Entwickler werden“
ankreuzen (oder später unter Konto → „Entwickler werden“).</li>
<li>Ein Admin prüft die Anfrage. Du bekommst eine E-Mail, sobald du freigeschaltet bist.</li></ol>
<h2>Wo verwalte ich meine Apps?</h2>
<p>In der App unter Konto → Entwickler-Bereich oder im Browser unter <a href="{base}/konto#/entwickler">Mein Konto →
Entwickler</a> – dort lassen sich APKs am PC bequem hochladen.</p>
<div class="cards"><a href="{base}/hilfe/app-veroeffentlichen"><b>App veröffentlichen</b>Upload oder GitHub/Forgejo</a>
<a href="{base}/hilfe/versionen"><b>Versionen & Rollouts</b>Kanäle, Betas, Prüfung</a>
<a href="{base}/hilfe/vermarktung"><b>Store-Eintrag</b>Screenshots, Preis, Codes</a>
<a href="{base}/hilfe/ci"><b>Automatisch veröffentlichen</b>GitHub & Forgejo Actions</a>
<a href="{base}/hilfe/api"><b>API-Referenz</b>Alle Endpunkte</a></div>"""),
    ("Für Entwickler", "app-veroeffentlichen", "App veröffentlichen", """
<h2>App anlegen</h2>
<p>Im Entwickler-Bereich „Neue App“: Name, Kurzname (ergibt die Adresse <code>deinname/kurzname</code>),
Beschreibung, Kategorie, Preis. Dann die Quelle wählen:</p>
<h3>Variante A: APK hochladen</h3>
<p>Du lädst jede Version selbst hoch (App, Browser oder per <a href="{base}/hilfe/ci">API/CI</a>). ByteDroide liest
Paketname, <code>versionName</code> und <code>versionCode</code> aus der APK und prüft sie.</p>
<h3>Variante B: Aus einem Repository</h3>
<p>Gib die Adresse eines GitHub-, Forgejo-, Gitea- oder Codeberg-Repos an, z. B.
<code>https://github.com/name/app</code>. ByteDroide übernimmt automatisch das neueste Release mit
<code>.apk</code>-Anhang; Pre-Releases werden zur Beta. Für private Repos einen Lese-Token angeben.</p>
<h2>Prüfung</h2>
<p>Neue Apps werden von einem Admin geprüft, bevor sie öffentlich erscheinen. Je nach Store-Einstellung werden auch
neue Versionen vor der Auslieferung geprüft – bis dahin bekommen Nutzer die bisherige Version. Alle Uploads werden
zusätzlich auf Schadsoftware gescannt (falls eingerichtet).</p>"""),
    ("Für Entwickler", "versionen", "Versionen, Betas & Rollouts", """
<h2>Regeln für Versionen</h2>
<ul><li><b>versionName = Version im Store.</b> Tag <code>v1.2.3</code> ↔ <code>versionName "1.2.3"</code>. Sonst erkennt
ByteDroide Updates nicht richtig – beim Upload wird das geprüft.</li>
<li><b>versionCode muss steigen</b>, sonst installiert Android das Update nicht.</li>
<li><b>Immer mit demselben Schlüssel signieren.</b></li>
<li>Der Paketname ist nach dem ersten Upload fest.</li></ul>
<h2>Kanäle: Stabil & Beta</h2>
<p>Beim Upload wählst du den Kanal. Beta-Tester bekommen die neueste Beta, alle anderen die neueste stabile
Version. Das Beta-Programm stellst du in den App-Einstellungen auf „Offen“ (jeder kann beitreten) oder „Nur
Eingeladene“ (du lädst Tester per Benutzername ein). Bei Repository-Quellen sind Pre-Releases automatisch Betas.</p>
<h2>Gestaffelte Rollouts</h2>
<p>Stabile Uploads können erst an einen Teil der Nutzer gehen (10/25/50 %). Die Zuordnung ist pro Konto bzw. Gerät
fest, die übrigen behalten die vorherige Version. Läuft alles gut, erhöhst du auf 100 % – erst dann gehen die
Update-Benachrichtigungen raus.</p>"""),
    ("Für Entwickler", "vermarktung", "Store-Eintrag, Preis & Codes", """
<h2>Ein guter Store-Eintrag</h2>
<ul><li><b>Icon:</b> quadratisches PNG/JPEG/WebP bis 1 MB.</li>
<li><b>Screenshots:</b> bis zu 8, PNG/JPEG/WebP bis 3 MB. Die Reihenfolge lässt sich per Pfeil ändern – der erste
Screenshot ist der wichtigste.</li>
<li><b>Beschreibung:</b> Die erste Zeile erscheint in Listen – kurz sagen, was die App kann.</li>
<li><b>Kategorie</b> und <b>Webseite</b> helfen beim Finden.</li></ul>
<h2>Freigabe & Preis</h2>
<table><tr><th>Freigabe</th><th>Bedeutung</th></tr>
<tr><td>Offen</td><td>Jeder sieht die App und kann sie installieren (bei Preis: nach dem Kauf).</td></tr>
<tr><td>Mit Code</td><td>Jeder sieht die App, installieren nur mit eingelöstem Freischalt-Code.</td></tr>
<tr><td>Versteckt</td><td>Nur du und die Admins sehen die App.</td></tr></table>
<p>Preise von 0,50 € bis 1000 € (einmalig, inklusive aller Updates). Bezahlt wird über Stripe, sofern der Betreiber
es eingerichtet hat.</p>
<h2>Freischalt-Codes</h2>
<p>Codes schalten die App für genau ein Konto dauerhaft frei – ideal für Tester, Kunden oder als Gutschein für
kostenpflichtige Apps. Erzeugen, teilen und sehen, wer welchen Code eingelöst hat: App → Freischalt-Codes.</p>"""),
    ("Für Entwickler", "nutzer-feedback", "Auf Feedback reagieren", """
<h2>Bewertungen beantworten</h2>
<p>Unter jeder Bewertung deiner App findest du „Antworten“. Die Antwort ist öffentlich; der Bewertende bekommt eine
Benachrichtigung.</p>
<h2>Nachrichten von Nutzern</h2>
<p>Nutzer können dir Fehlermeldungen, Feedback und Fragen schicken. Du bekommst eine E-Mail bzw. Push-Nachricht und
antwortest unter Konto → Nachrichten (App) oder <a href="{base}/konto#/nachrichten">Mein Konto → Nachrichten</a>
(Web). Fehlermeldungen aus der App enthalten Gerät, Android-Version und installierte App-Version. Erledigte
Gespräche kannst du schließen – schreibt der Nutzer erneut, öffnet es sich wieder.</p>"""),
    ("Für Entwickler", "ci", "Automatisch veröffentlichen (CI)", """
<p>Mit einem <b>API-Schlüssel</b> lädt deine Build-Pipeline neue Versionen selbst hoch. Schlüssel erstellen:
<a href="{base}/konto#/entwickler">Mein Konto → Entwickler → API-Schlüssel</a>.</p>
<h2>Mit curl</h2>
<pre><code>curl --fail -X POST -H "Authorization: Bearer $BYTEDROIDE_KEY" \\
  -H "X-Release-Notes: Neue%20Funktionen" \\
  --data-binary @app/build/outputs/apk/release/app-release.apk \\
  "{base}/api/dev/apps/NAME/APP/releases?channel=stable&amp;rollout=100"</code></pre>
<p>Parameter: <code>channel</code> (<code>stable</code>/<code>beta</code>), <code>version</code> (optional, sonst aus
der APK), <code>rollout</code> (1–100), <code>notes</code> oder Header <code>X-Release-Notes</code> (URL-kodiert).</p>
<h2>GitHub Actions</h2>
<pre><code>- name: In ByteDroide veröffentlichen
  run: |
    curl --fail -X POST -H "Authorization: Bearer ${{{{ secrets.BYTEDROIDE_KEY }}}}" \\
      --data-binary @app/build/outputs/apk/release/app-release.apk \\
      "{base}/api/dev/apps/NAME/APP/releases?channel=stable"</code></pre>
<h2>Forgejo Actions</h2>
<p>Identisch – das Secret unter Repo → Einstellungen → Actions → Geheimnisse anlegen. Alternativ das Repository als
Quelle eintragen: Dann genügt ein Release mit <code>.apk</code>-Anhang, ganz ohne API-Schlüssel.</p>"""),
    ("Für Entwickler", "api", "API-Referenz", """
<p>Alle Endpunkte sprechen JSON. Authentifizierung per <code>Authorization: Bearer TOKEN</code> (Anmelde-Token oder
API-Schlüssel). <code>{id}</code> ist immer <code>besitzer/kurzname</code>.</p>
<table><tr><th>Methode &amp; Pfad</th><th>Zweck</th></tr>
<tr><td><code>GET /api/apps</code>, <code>GET /api/apps/{id}</code></td><td>Katalog / eine App (für den Nutzer gefiltert)</td></tr>
<tr><td><code>GET /api/apps/{id}/download</code></td><td>APK laden</td></tr>
<tr><td><code>GET/PUT/DELETE /api/apps/{id}/reviews</code></td><td>Bewertungen lesen, eigene schreiben/löschen</td></tr>
<tr><td><code>POST /api/apps/{id}/threads</code></td><td>Entwickler kontaktieren</td></tr>
<tr><td><code>GET /api/threads</code>, <code>GET/PUT /api/threads/{t}</code>, <code>POST /api/threads/{t}/messages</code></td><td>Nachrichten</td></tr>
<tr><td><code>POST/DELETE /api/apps/{id}/beta</code></td><td>Beta beitreten/verlassen</td></tr>
<tr><td><code>POST /api/apps/{id}/purchase</code>, <code>POST /api/redeem</code></td><td>Kaufen, Code einlösen</td></tr>
<tr><td><code>GET/POST /api/dev/apps</code>, <code>GET/PUT/DELETE /api/dev/apps/{id}</code></td><td>Eigene Apps</td></tr>
<tr><td><code>GET/POST /api/dev/apps/{id}/releases</code>, <code>PUT/DELETE …/releases/{r}</code></td><td>Versionen, Rollout</td></tr>
<tr><td><code>POST/PUT /api/dev/apps/{id}/screenshots</code>, <code>DELETE …/screenshots/{s}</code></td><td>Screenshots (PUT = Reihenfolge)</td></tr>
<tr><td><code>POST /api/dev/apps/{id}/icon</code></td><td>Icon</td></tr>
<tr><td><code>…/codes</code>, <code>…/testers</code>, <code>PUT …/reviews/{u}/reply</code></td><td>Codes, Tester, Antworten</td></tr>
<tr><td><code>GET/POST/DELETE /api/dev/keys</code></td><td>API-Schlüssel</td></tr></table>"""),

    ("Für Betreiber", "betrieb", "Server betreiben", """
<p>Der Store-Server ist ein einzelnes Python-Programm (nur Standardbibliothek, SQLite) im Docker-Container.</p>
<h2>Einrichten</h2>
<pre><code>cd server
cp .env.example .env      # Betreiberdaten, SMTP, Forgejo-Token, optional Stripe
docker compose up -d --build</code></pre>
<p>Das <b>erste registrierte Konto wird Admin</b>. Der Container hängt im Docker-Netzwerk <code>reverse-proxy</code>;
Caddy leitet <code>apps.nebendahl.eu</code> an <code>bytedroide:8080</code> weiter (siehe
<code>server/Caddyfile.example</code>).</p>
<h2>Wichtige Einstellungen (.env)</h2>
<table><tr><th>Variable</th><th>Bedeutung</th></tr>
<tr><td><code>OPERATOR_*</code></td><td>Pflichtangaben für Impressum und Datenschutz</td></tr>
<tr><td><code>SMTP_*</code></td><td>E-Mail-Versand</td></tr>
<tr><td><code>FORGEJO_URL</code>, <code>FORGEJO_TOKEN</code>, <code>FORGEJO_AUTO_IMPORT</code></td><td>Forgejo-Anbindung</td></tr>
<tr><td><code>STRIPE_*</code></td><td>Bezahlung</td></tr>
<tr><td><code>NTFY_URL</code></td><td>Push-Server (Standard ntfy.sh)</td></tr>
<tr><td><code>CLAMAV_HOST</code></td><td>Virenscan (<code>docker compose --profile clamav up -d</code>)</td></tr>
<tr><td><code>REVIEW_RELEASES</code></td><td>Neue Versionen erst nach Admin-Freigabe</td></tr>
<tr><td><code>STORE_APP_ID</code></td><td>App unter <code>/download</code></td></tr>
<tr><td><code>ANDROID_CERT_SHA256</code></td><td>App Links (QR-Codes öffnen die App)</td></tr></table>
<h2>Kommandozeile</h2>
<pre><code>docker exec bytedroide python store_server.py users
docker exec bytedroide python store_server.py set-role NAME admin
docker exec bytedroide python store_server.py reset-password NAME</code></pre>
<h2>Backup</h2>
<p>Alles liegt in <code>server/data/</code> (Datenbank, APKs, Bilder) – diesen Ordner sichern.</p>"""),
]

INDEX = """
<p>Hier findest du Antworten rund um ByteDroide – von der ersten Installation bis zur eigenen App im Store.</p>
<div class="cards">
<a href="{base}/hilfe/erste-schritte"><b>Erste Schritte</b>ByteDroide installieren und loslegen</a>
<a href="{base}/hilfe/updates"><b>Installieren & Updates</b>Und was tun, wenn es hakt</a>
<a href="{base}/hilfe/benachrichtigungen"><b>Benachrichtigungen</b>E-Mail und Push über ntfy</a>
<a href="{base}/hilfe/codes-und-kaeufe"><b>Codes & Käufe</b>Freischalten, kaufen, widerrufen</a>
<a href="{base}/hilfe/feedback"><b>Bewertungen & Nachrichten</b>Feedback und Fehler melden</a>
<a href="{base}/hilfe/entwickler"><b>Für Entwickler</b>Eigene Apps veröffentlichen</a>
</div>
<h2>Nicht fündig geworden?</h2>
<p>Schreib uns über das <a href="{base}/kontakt">Kontaktformular</a>. Bei Problemen mit einer bestimmten App hilft
der Entwickler am schnellsten – über „Entwickler kontaktieren“ auf der App-Seite.</p>"""


def page(config, slug: str) -> str:
    base = config.public_url
    current = next((p for p in PAGES if p[1] == slug), None)
    if slug and not current:
        current = ("", slug, "Seite nicht gefunden", '<p>Diese Hilfeseite gibt es nicht. <a href="{base}/hilfe">Zur '
                                                      'Übersicht</a></p>')
    side, section = [], None
    side.append(f'<a href="{html.escape(base)}/hilfe" class="{"on" if not slug else ""}">Übersicht</a>')
    for sec, s, title, _ in PAGES:
        if sec != section:
            side.append(f"<h4>{html.escape(sec)}</h4>")
            section = sec
        side.append(f'<a href="{html.escape(base)}/hilfe/{s}" class="{"on" if s == slug else ""}">{html.escape(title)}</a>')
    if current:
        title, content = current[2], current[3]
        idx = PAGES.index(current) if current in PAGES else -1
        nav = ""
        if idx >= 0:
            prev_link = (f'<a href="{base}/hilfe/{PAGES[idx - 1][1]}">← {html.escape(PAGES[idx - 1][2])}</a>'
                         if idx > 0 else "<span></span>")
            next_link = (f'<a href="{base}/hilfe/{PAGES[idx + 1][1]}">{html.escape(PAGES[idx + 1][2])} →</a>'
                         if idx + 1 < len(PAGES) else "")
            nav = f'<div class="next">{prev_link}{next_link}</div>'
        article = f"<h1>{html.escape(title)}</h1>{content.replace('{base}', html.escape(base))}{nav}"
    else:
        title = "Hilfe & Dokumentation"
        article = f"<h1>{title}</h1>{INDEX.replace('{base}', html.escape(base))}"
    body = f'{DOC_CSS}<div class="docs"><nav class="side">{"".join(side)}</nav><article>{article}</article></div>'
    hero = '<div class="page-title"><h1>Hilfe & Dokumentation</h1><p>Für Nutzer, Entwickler und Betreiber</p></div>'
    return storefront.layout(config, f"{title} – ByteDroide Hilfe", body, hero, active="/hilfe")
