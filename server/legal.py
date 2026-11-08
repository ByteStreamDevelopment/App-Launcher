"""Rechtstexte (Impressum, Datenschutz, Nutzungsbedingungen, Widerruf) als HTML-Seiten.

Die Betreiberdaten kommen aus der Konfiguration (OPERATOR_* in der .env). Fehlende Pflichtangaben werden
auf der Seite deutlich rot markiert, damit sie nicht unbemerkt fehlen.

Hinweis: Vorlage nach bestem Wissen (Stand 11/2026), keine Rechtsberatung.
"""

import html

STAND = "November 2026"

PAGE_CSS = """
:root{--bg:#f6f7fb;--card:#fff;--text:#1f2937;--muted:#6b7280;--brand:#3D5AFE;--border:#e5e7eb}
@media (prefers-color-scheme:dark){:root{--bg:#0f1117;--card:#171a23;--text:#e5e7eb;--muted:#9ca3af;--border:#2a2f3a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:16px/1.65 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
header{background:linear-gradient(135deg,#3D5AFE,#1A237E);color:#fff;padding:28px 16px}
header .in,main{max-width:820px;margin:0 auto}header a{color:#fff;text-decoration:none;font-weight:700;letter-spacing:1px}
header h1{margin:8px 0 0;font-size:28px}main{padding:24px 16px 48px}
section{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:20px 24px;margin:0 0 16px}
h2{font-size:19px;margin:0 0 8px}h3{font-size:16px;margin:16px 0 4px}a{color:var(--brand)}
.missing{color:#fff;background:#dc2626;border-radius:6px;padding:0 6px;font-weight:600}
.muted{color:var(--muted);font-size:14px}nav.legal{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px}
nav.legal a{color:rgba(255,255,255,.85);font-size:14px}ul{padding-left:20px}
input,button,textarea{font:inherit}button{background:var(--brand);color:#fff;border:0;border-radius:999px;padding:10px 20px;
cursor:pointer}input,textarea{width:100%;padding:10px 12px;border:1px solid var(--border);border-radius:10px;
background:var(--card);color:var(--text);margin:4px 0 12px}
"""


def page(config, title: str, body: str) -> str:
    base = html.escape(config.public_url)
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} – ByteDroide</title>
<style>{PAGE_CSS}</style></head><body>
<header><div class="in"><a href="{base}/">&#129302; BYTEDROIDE</a><h1>{html.escape(title)}</h1>
<nav class="legal"><a href="{base}/impressum">Impressum</a><a href="{base}/datenschutz">Datenschutz</a>
<a href="{base}/agb">Nutzungsbedingungen</a><a href="{base}/widerruf">Widerruf</a></nav></div></header>
<main>{body}</main></body></html>"""


class _Op:
    """Betreiberangaben, fehlende Werte als rote Markierung."""

    def __init__(self, config):
        self.c = config

    def __getattr__(self, name):
        value = getattr(self.c, "operator_" + name, "")
        if value:
            return html.escape(value)
        return f'<span class="missing">[fehlt: OPERATOR_{name.upper()}]</span>'

    def has(self, name) -> bool:
        return bool(getattr(self.c, "operator_" + name, ""))


def missing_fields(config) -> list:
    required = ("name", "street", "city", "email")
    return [f"OPERATOR_{f.upper()}" for f in required if not getattr(config, "operator_" + f, "")]


def impressum(config) -> str:
    op = _Op(config)
    phone = f"Telefon: {op.phone}<br>" if op.has("phone") else ""
    vat = (f"<section><h2>Umsatzsteuer-ID</h2><p>Umsatzsteuer-Identifikationsnummer gemäß § 27a "
           f"Umsatzsteuergesetz: {op.vat_id}</p></section>") if op.has("vat_id") else ""
    responsible = op.responsible if op.has("responsible") else op.name
    body = f"""
<section><h2>Angaben gemäß § 5 DDG</h2>
<p>{op.name}<br>{op.street}<br>{op.city}<br>{op.country if op.has('country') else 'Deutschland'}</p></section>
<section><h2>Kontakt</h2><p>{phone}E-Mail: {op.email}</p></section>
{vat}
<section><h2>Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV</h2>
<p>{responsible}<br>{op.street}<br>{op.city}</p></section>
<section><h2>Verbraucherstreitbeilegung</h2>
<p>Wir sind nicht bereit und nicht verpflichtet, an Streitbeilegungsverfahren vor einer
Verbraucherschlichtungsstelle teilzunehmen.</p></section>
<section><h2>Haftung für Inhalte</h2>
<p>Als Diensteanbieter sind wir für eigene Inhalte auf diesen Seiten und in der App ByteDroide nach den allgemeinen
Gesetzen verantwortlich. Apps, die von registrierten Entwicklerinnen und Entwicklern veröffentlicht werden, sind
fremde Inhalte. Für diese sind wir nach §§ 7 ff. DDG bzw. Art. 6 der Verordnung (EU) 2022/2065 (Digital Services Act)
erst ab Kenntnis einer konkreten Rechtsverletzung verantwortlich. Bei Bekanntwerden entfernen wir solche Inhalte
umgehend.</p>
<h3>Rechtswidrige Inhalte melden</h3>
<p>Hinweise auf rechtswidrige Inhalte oder Apps (z. B. Schadsoftware, Urheberrechtsverletzungen) bitte per E-Mail an
{op.email} mit genauer Bezeichnung der App, einer Begründung und Ihren Kontaktdaten. Diese Adresse ist zugleich die
zentrale Kontaktstelle nach Art. 11 und 12 DSA. Kommunikation ist auf Deutsch oder Englisch möglich.</p></section>
<section><h2>Haftung für Links</h2>
<p>Unser Angebot enthält Links zu externen Websites Dritter (z. B. Quell-Repositories auf GitHub oder Forgejo), auf
deren Inhalte wir keinen Einfluss haben. Für diese Inhalte ist stets der jeweilige Anbieter verantwortlich. Bei
Bekanntwerden von Rechtsverletzungen werden wir derartige Links umgehend entfernen.</p></section>
<section><h2>Urheberrecht</h2>
<p>Die durch den Betreiber erstellten Inhalte und Werke unterliegen dem deutschen Urheberrecht. Die Rechte an den
veröffentlichten Apps liegen bei den jeweiligen Entwicklerinnen und Entwicklern.</p></section>
<p class="muted">Stand: {STAND}</p>"""
    return page(config, "Impressum", body)


def datenschutz(config) -> str:
    op = _Op(config)
    payments = ""
    if config.stripe_secret_key:
        payments = """
<section><h2>7. Bezahlung kostenpflichtiger Apps (Stripe)</h2>
<p>Für Käufe nutzen wir den Zahlungsdienst Stripe Payments Europe, Ltd., 1 Grand Canal Street Lower, Grand Canal Dock,
Dublin, D02 H210, Irland („Stripe“). Beim Kauf werden Sie auf eine Bezahlseite von Stripe weitergeleitet; Zahlungsdaten
(z. B. Karten- oder Kontodaten) gibt Ihr Gerät direkt an Stripe weiter, wir erhalten sie nicht. Wir erhalten von Stripe
lediglich die Bestätigung der Zahlung, Betrag, Währung und eine Transaktionskennung. Rechtsgrundlage ist Art. 6 Abs. 1
lit. b DSGVO (Vertragserfüllung) sowie Art. 6 Abs. 1 lit. c DSGVO (steuer- und handelsrechtliche Aufbewahrungspflichten).
Stripe kann Daten auch in die USA übermitteln; Stripe, Inc. ist unter dem EU-US Data Privacy Framework zertifiziert.
Datenschutzhinweise von Stripe: <a href="https://stripe.com/de/privacy">stripe.com/de/privacy</a>.</p>
<p>Kaufbelege speichern wir für die gesetzliche Aufbewahrungsfrist (bis zu 10 Jahre, § 147 AO, § 257 HGB).</p></section>"""
    hosting = (f"<p>Der Server wird betrieben bei: {op.hosting}.</p>" if op.has("hosting") else
               "<p>Der Server wird vom Betreiber selbst bzw. bei einem Hosting-Dienstleister in der EU betrieben, "
               "mit dem ein Vertrag zur Auftragsverarbeitung (Art. 28 DSGVO) besteht.</p>")
    body = f"""
<section><h2>1. Verantwortlicher</h2>
<p>Verantwortlich für die Datenverarbeitung im Zusammenhang mit der App „ByteDroide“ und dem Server
{html.escape(config.public_url)} ist:</p>
<p>{op.name}<br>{op.street}<br>{op.city}<br>E-Mail: {op.email}</p>
<p>Ein Datenschutzbeauftragter ist nicht bestellt, da hierzu keine gesetzliche Pflicht besteht.</p></section>

<section><h2>2. Überblick</h2>
<p>ByteDroide ist ein App-Store für Android. Wir verarbeiten nur die Daten, die für den Betrieb nötig sind. Es gibt
<strong>keine Werbung, kein Tracking, keine Analyse-Dienste und keine Weitergabe zu Werbezwecken</strong>.</p></section>

<section><h2>3. Server-Protokolle und Hosting</h2>
<p>Bei jedem Aufruf des Servers (durch die App oder den Browser) werden technisch bedingt IP-Adresse, Zeitpunkt,
aufgerufene Adresse, HTTP-Statuscode und die Kennung der App bzw. des Browsers verarbeitet und in Protokollen
gespeichert. Das dient der Sicherheit (z. B. Schutz vor Passwort-Raten) und der Fehlersuche. Rechtsgrundlage ist
Art. 6 Abs. 1 lit. f DSGVO; unser berechtigtes Interesse liegt im sicheren und stabilen Betrieb. Protokolle werden nach
spätestens 14 Tagen gelöscht. Fehlversuche bei der Anmeldung werden nur im Arbeitsspeicher für 15 Minuten
gehalten.</p>{hosting}</section>

<section><h2>4. Benutzerkonto</h2>
<p>Für ein Konto speichern wir Benutzername, E-Mail-Adresse, das Passwort ausschließlich als sicheren Hash (scrypt),
Ihre Rolle (Benutzer, Entwickler, Admin), den Zeitpunkt der Registrierung und der Zustimmung zu den
Nutzungsbedingungen, Ihre Benachrichtigungs-Einstellungen sowie die für Ihr Konto freigeschalteten, gekauften oder
als Beta getesteten Apps. Anmelde-Sitzungen werden als Hash gespeichert und nach 90 Tagen ohne Nutzung ungültig.
Rechtsgrundlage ist Art. 6 Abs. 1 lit. b DSGVO (Nutzungsvertrag). Ohne Konto können offene Apps ohne Angabe
personenbezogener Daten (abgesehen von Nr. 3) genutzt werden.</p>
<p>Die Daten werden gespeichert, bis Sie Ihr Konto löschen. Das können Sie jederzeit selbst in der App unter
„Konto → Konto löschen“ tun. Kaufbelege bleiben wegen gesetzlicher Pflichten aufbewahrt (siehe Nr. 7).</p></section>

<section><h2>5. Downloads</h2>
<p>Laden Sie eine App herunter, speichern wir App, Version, Zeitpunkt und – falls Sie angemeldet sind – Ihr Konto.
Damit können wir Sie über Updates der von Ihnen genutzten Apps informieren (nur wenn Sie das eingeschaltet haben) und
Entwicklerinnen und Entwicklern <strong>zusammengefasste</strong> Download-Zahlen ohne Personenbezug anzeigen.
Rechtsgrundlage ist Art. 6 Abs. 1 lit. b und f DSGVO. Download-Einträge werden nach 12 Monaten gelöscht bzw. beim
Löschen des Kontos entfernt.</p></section>

<section><h2>6. E-Mails</h2>
<p>Wir senden E-Mails, die für Ihr Konto nötig sind (Bestätigung der E-Mail-Adresse, Passwort zurücksetzen,
Sicherheits-Hinweise, Kaufbelege, Entscheidungen über Entwickler-Freischaltungen und App-Prüfungen) auf Grundlage von
Art. 6 Abs. 1 lit. b DSGVO. Update- und Neuigkeiten-Mails erhalten Sie nur, wenn Sie diese in den
Konto-Einstellungen eingeschaltet haben (Art. 6 Abs. 1 lit. a DSGVO); das können Sie jederzeit dort wieder
ausschalten. Für den Versand nutzen wir einen E-Mail-Server{(' von ' + op.mail_provider) if op.has('mail_provider') else ''}.
</p></section>
{payments}
<section><h2>{'8' if payments else '7'}. Entwickler-Funktionen und Dritte</h2>
<p>Entwicklerinnen und Entwickler sehen für ihre eigenen Apps: Download- und Verkaufszahlen (zusammengefasst), die
Benutzernamen ihrer Beta-Tester sowie den Benutzernamen, wer einen ihrer Freischalt-Codes eingelöst hat.
Gibt eine Entwicklerin oder ein Entwickler als Quelle ein Repository (z. B. GitHub oder Forgejo) an, ruft
<strong>unser Server</strong> dort die Release-Informationen und APK-Dateien ab und leitet sie an Sie weiter. Ihr Gerät
verbindet sich dabei nicht mit diesen Diensten, es werden keine Daten über Sie dorthin übermittelt.</p>
<p>App-Icons können von dem jeweiligen Quell-Server geladen werden; dabei wird Ihre IP-Adresse an diesen Server
übermittelt.</p></section>

<section><h2>{'9' if payments else '8'}. Daten in der App und im Browser</h2>
<p>Die App speichert auf Ihrem Gerät nur Ihr Anmelde-Token, Ihre Einstellungen und die Zuordnung, welche installierte App
zu welchem Store-Eintrag gehört. Für die Erkennung von Updates liest die App die Versionen der über ByteDroide
installierten Apps auf Ihrem Gerät aus; diese Information verlässt Ihr Gerät nicht. Das Entwickler-Portal im Browser
speichert Ihr Anmelde-Token im lokalen Speicher des Browsers (technisch erforderlich, § 25 Abs. 2 Nr. 2 TDDDG).
Cookies werden nicht gesetzt.</p></section>

<section><h2>{'10' if payments else '9'}. Ihre Rechte</h2>
<p>Sie haben das Recht auf Auskunft (Art. 15 DSGVO), Berichtigung (Art. 16), Löschung (Art. 17), Einschränkung der
Verarbeitung (Art. 18), Datenübertragbarkeit (Art. 20) und Widerspruch gegen Verarbeitungen auf Grundlage von
Art. 6 Abs. 1 lit. f DSGVO (Art. 21). Eine erteilte Einwilligung können Sie jederzeit mit Wirkung für die Zukunft
widerrufen. Eine Kopie Ihrer Daten erhalten Sie in der App unter „Konto → Meine Daten exportieren“, löschen können Sie
Ihr Konto unter „Konto → Konto löschen“. Für alles Weitere genügt eine E-Mail an {op.email}.</p>
<p>Sie haben außerdem das Recht, sich bei einer Datenschutz-Aufsichtsbehörde zu beschweren, insbesondere in dem
Bundesland Ihres Wohnorts oder des Sitzes des Verantwortlichen{(': ' + op.authority) if op.has('authority') else ''}.</p>
<p>Eine automatisierte Entscheidungsfindung einschließlich Profiling findet nicht statt.</p></section>
<p class="muted">Stand: {STAND}</p>"""
    return page(config, "Datenschutzerklärung", body)


def agb(config) -> str:
    op = _Op(config)
    vat = ("Gemäß § 19 UStG wird keine Umsatzsteuer berechnet." if config.kleinunternehmer
           else "Alle Preise sind Endpreise inklusive der gesetzlichen Umsatzsteuer.")
    body = f"""
<section><h2>§ 1 Geltungsbereich und Anbieter</h2>
<p>Diese Nutzungsbedingungen gelten für die Nutzung der App „ByteDroide“, des Servers {html.escape(config.public_url)}
und des Entwickler-Portals (zusammen „ByteDroide“). Anbieter ist {op.name}, {op.street}, {op.city}
(„Betreiber“).</p></section>

<section><h2>§ 2 Leistungen</h2>
<p>ByteDroide ermöglicht das Entdecken, Installieren und Aktualisieren von Android-Apps. Apps werden vom Betreiber
oder von freigeschalteten Entwicklerinnen und Entwicklern („Entwickler“) bereitgestellt. Einige Apps sind nur mit
Freischalt-Code oder gegen Bezahlung verfügbar, andere als Beta-Version für Tester. Ein Anspruch auf eine bestimmte
Verfügbarkeit des Dienstes oder einzelner Apps besteht nicht; wir bemühen uns um einen möglichst störungsfreien
Betrieb.</p></section>

<section><h2>§ 3 Konto</h2>
<ul><li>Für die Registrierung sind ein Benutzername, eine gültige E-Mail-Adresse und ein Passwort nötig. Die Angaben
müssen zutreffen. Pro Person ist ein Konto vorgesehen.</li>
<li>Zugangsdaten sind geheim zu halten. Bei Verdacht auf Missbrauch bitte das Passwort ändern und uns informieren.</li>
<li>Sie können Ihr Konto jederzeit in der App löschen. Wir können Konten bei Verstößen gegen diese Bedingungen
sperren oder löschen; berechtigte Interessen der Nutzer werden dabei berücksichtigt.</li></ul></section>

<section><h2>§ 4 Entwickler</h2>
<ul><li>Ein Entwickler-Konto wird wie ein normales Konto erstellt und muss durch einen Admin freigegeben werden. Ein
Anspruch auf Freigabe besteht nicht.</li>
<li>Entwickler können Apps veröffentlichen, indem sie eine Quelle (z. B. ein GitHub- oder Forgejo-Repository) angeben oder
APK-Dateien hochladen. Neue Apps werden vor der Veröffentlichung von einem Admin geprüft.</li>
<li>Entwickler versichern, dass sie alle Rechte an den veröffentlichten Apps, Texten und Bildern besitzen, dass die Apps
keine Schadsoftware enthalten, keine Daten ohne Rechtsgrundlage erheben, nicht gegen geltendes Recht verstoßen und
dass Beschreibung und tatsächliche Funktion übereinstimmen. Für eigene Apps sind Entwickler selbst verantwortlich,
insbesondere für Datenschutzhinweise innerhalb ihrer Apps.</li>
<li>Entwickler räumen dem Betreiber das einfache, auf die Dauer der Veröffentlichung beschränkte Recht ein, die Apps und
zugehörige Inhalte zu speichern, zu vervielfältigen und über ByteDroide öffentlich zugänglich zu machen.</li>
<li>Entwickler stellen den Betreiber von Ansprüchen Dritter frei, die auf einer schuldhaften Verletzung dieser Pflichten
beruhen.</li>
<li>Der Betreiber darf Apps bei Hinweisen auf Rechtsverstöße oder Sicherheitsrisiken sperren oder entfernen und
informiert den Entwickler darüber mit Begründung (Art. 17 DSA).</li>
<li>Für kostenpflichtige Apps erhalten Entwickler die Erlöse abzüglich etwaiger Zahlungsgebühren nach gesonderter
Vereinbarung mit dem Betreiber.</li></ul></section>

<section><h2>§ 5 Kauf kostenpflichtiger Apps</h2>
<ul><li>Vertragspartner beim Kauf ist der Betreiber. Mit dem Tippen auf „Zahlungspflichtig kaufen“ und dem Abschluss der
Zahlung kommt der Vertrag über die dauerhafte Nutzung der App (einschließlich künftiger Updates, solange die App
angeboten wird) für Ihr Konto zustande.</li>
<li>{vat} Die Bezahlung erfolgt über den Zahlungsdienstleister Stripe.</li>
<li>Die gekaufte App wird unmittelbar nach Zahlungseingang für Ihr Konto freigeschaltet. Den Kaufbeleg erhalten Sie
per E-Mail.</li>
<li>Für Verbraucher gilt das gesetzliche Widerrufsrecht, siehe <a href="{html.escape(config.public_url)}/widerruf">
Widerrufsbelehrung</a>. Den Vertrag können Sie in der App unter „Konto → Meine Käufe → Vertrag widerrufen“
widerrufen.</li>
<li>Es gelten die gesetzlichen Gewährleistungsrechte für digitale Produkte (§§ 327 ff. BGB).</li>
<li>Freischalt-Codes sind nicht übertragbar, sobald sie eingelöst wurden, und können nicht gegen Geld eingetauscht
werden.</li></ul></section>

<section><h2>§ 6 Beta-Versionen</h2>
<p>Beta-Versionen sind Vorabversionen, die Fehler enthalten können. Die Teilnahme ist freiwillig und kann jederzeit
in der App beendet werden.</p></section>

<section><h2>§ 7 Pflichten der Nutzer</h2>
<p>Untersagt sind insbesondere: das Umgehen von Freischalt- oder Bezahlmechanismen, das Weitergeben von APKs
kostenpflichtiger Apps an Dritte, automatisierte Massenabrufe, Angriffe auf die Infrastruktur sowie das Hochladen
rechtswidriger Inhalte.</p></section>

<section><h2>§ 8 Haftung</h2>
<p>Wir haften unbeschränkt bei Vorsatz und grober Fahrlässigkeit, bei Verletzung von Leben, Körper oder Gesundheit,
nach dem Produkthaftungsgesetz sowie im Umfang einer übernommenen Garantie. Bei leicht fahrlässiger Verletzung einer
wesentlichen Vertragspflicht (deren Erfüllung die ordnungsgemäße Durchführung des Vertrags erst ermöglicht und auf
deren Einhaltung Sie regelmäßig vertrauen dürfen) ist die Haftung auf den vertragstypischen, vorhersehbaren Schaden
begrenzt. Im Übrigen ist die Haftung für leichte Fahrlässigkeit ausgeschlossen. Für Apps von Entwicklern haftet der
jeweilige Entwickler; die gesetzlichen Rechte aus einem Kauf gegenüber dem Betreiber bleiben unberührt.</p></section>

<section><h2>§ 9 Änderungen</h2>
<p>Wir können diese Bedingungen mit Wirkung für die Zukunft ändern, wenn dafür ein triftiger Grund besteht (z. B.
neue Funktionen oder Rechtsänderungen). Über Änderungen informieren wir mindestens vier Wochen vorher per E-Mail.
Widersprechen Sie nicht innerhalb dieser Frist, gelten die neuen Bedingungen; auf diese Folge weisen wir in der
Mitteilung hin. Im Fall des Widerspruchs können beide Seiten den Nutzungsvertrag kündigen.</p></section>

<section><h2>§ 10 Schlussbestimmungen</h2>
<p>Es gilt deutsches Recht unter Ausschluss des UN-Kaufrechts. Bei Verbrauchern gilt diese Rechtswahl nur, soweit
nicht der Schutz durch zwingende Bestimmungen des Staates ihres gewöhnlichen Aufenthalts entzogen wird. Sollte eine
Bestimmung unwirksam sein, bleibt der Vertrag im Übrigen wirksam.</p></section>
<p class="muted">Stand: {STAND}</p>"""
    return page(config, "Nutzungsbedingungen", body)


def widerruf(config) -> str:
    op = _Op(config)
    body = f"""
<section><h2>Widerrufsbelehrung</h2>
<p>Verbraucher haben ein Widerrufsrecht nach Maßgabe der folgenden Bestimmungen. Verbraucher ist jede natürliche Person,
die ein Rechtsgeschäft zu Zwecken abschließt, die überwiegend weder ihrer gewerblichen noch ihrer selbständigen
beruflichen Tätigkeit zugerechnet werden können.</p>
<h3>Widerrufsrecht</h3>
<p>Sie haben das Recht, binnen vierzehn Tagen ohne Angabe von Gründen diesen Vertrag zu widerrufen. Die Widerrufsfrist
beträgt vierzehn Tage ab dem Tag des Vertragsabschlusses.</p>
<p>Um Ihr Widerrufsrecht auszuüben, müssen Sie uns ({op.name}, {op.street}, {op.city}, E-Mail: {op.email}) mittels
einer eindeutigen Erklärung (z. B. eine E-Mail) über Ihren Entschluss, diesen Vertrag zu widerrufen, informieren. Sie
können dafür das unten stehende Muster-Widerrufsformular verwenden, das jedoch nicht vorgeschrieben ist. Sie können den
Vertrag außerdem direkt in der App unter „Konto → Meine Käufe → Vertrag widerrufen“ widerrufen; den Eingang
bestätigen wir Ihnen unverzüglich per E-Mail.</p>
<p>Zur Wahrung der Widerrufsfrist reicht es aus, dass Sie die Mitteilung über die Ausübung des Widerrufsrechts vor Ablauf
der Widerrufsfrist absenden.</p>
<h3>Folgen des Widerrufs</h3>
<p>Wenn Sie diesen Vertrag widerrufen, haben wir Ihnen alle Zahlungen, die wir von Ihnen erhalten haben, unverzüglich und
spätestens binnen vierzehn Tagen ab dem Tag zurückzuzahlen, an dem die Mitteilung über Ihren Widerruf dieses Vertrags
bei uns eingegangen ist. Für diese Rückzahlung verwenden wir dasselbe Zahlungsmittel, das Sie bei der ursprünglichen
Transaktion eingesetzt haben, es sei denn, mit Ihnen wurde ausdrücklich etwas anderes vereinbart; in keinem Fall
werden Ihnen wegen dieser Rückzahlung Entgelte berechnet.</p>
<h3>Vorzeitiges Erlöschen des Widerrufsrechts</h3>
<p>Das Widerrufsrecht erlischt bei einem Vertrag über die Bereitstellung von nicht auf einem körperlichen Datenträger
befindlichen digitalen Inhalten, wenn wir mit der Vertragserfüllung begonnen haben, nachdem Sie ausdrücklich
zugestimmt haben, dass wir mit der Vertragserfüllung vor Ablauf der Widerrufsfrist beginnen, Sie Ihre Kenntnis davon
bestätigt haben, dass durch Ihre Zustimmung mit Beginn der Vertragserfüllung Ihr Widerrufsrecht erlischt, und wir
Ihnen eine Bestätigung des Vertrags auf einem dauerhaften Datenträger (Kaufbeleg per E-Mail) zur Verfügung gestellt
haben (§ 356 Abs. 5 BGB).</p></section>

<section><h2>Muster-Widerrufsformular</h2>
<p>(Wenn Sie den Vertrag widerrufen wollen, dann füllen Sie bitte dieses Formular aus und senden Sie es zurück.)</p>
<p>An {op.name}, {op.street}, {op.city}, E-Mail: {op.email}:</p>
<p>Hiermit widerrufe(n) ich/wir (*) den von mir/uns (*) abgeschlossenen Vertrag über den Kauf der folgenden Waren (*)/
die Erbringung der folgenden Dienstleistung (*)</p>
<p>– Bestellt am (*)/erhalten am (*)<br>– Name des/der Verbraucher(s)<br>– Anschrift des/der Verbraucher(s)<br>
– Unterschrift des/der Verbraucher(s) (nur bei Mitteilung auf Papier)<br>– Datum</p>
<p class="muted">(*) Unzutreffendes streichen.</p></section>
<p class="muted">Stand: {STAND}</p>"""
    return page(config, "Widerrufsbelehrung", body)


def simple_page(config, title: str, message: str, form: str = "") -> str:
    return page(config, title, f"<section><p>{html.escape(message)}</p>{form}</section>")


def landing(config) -> str:
    base = html.escape(config.public_url)
    body = f"""
<section><h2>Dein eigener App-Store für Android</h2>
<p>ByteDroide installiert und aktualisiert Apps von unabhängigen Entwicklerinnen und Entwicklern – mit Beta-Kanal,
Freischalt-Codes und kostenpflichtigen Apps.</p>
<p><a href="{base}/download">ByteDroide herunterladen</a> · <a href="{base}/portal">Entwickler-Portal</a></p></section>"""
    return page(config, "ByteDroide", body)
