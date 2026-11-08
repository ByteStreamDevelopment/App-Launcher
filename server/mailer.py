"""E-Mail-Versand für ByteDroide: schöne HTML-Mails mit Text-Alternative, Versand im Hintergrund.

Konfiguration über SMTP_* (siehe README). Ohne SMTP_HOST werden Mails nur ins Log geschrieben.
"""

import html
import logging
import queue
import smtplib
import ssl
import threading
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

log = logging.getLogger("store.mail")

BRAND = "#3D5AFE"
BRAND_DARK = "#1A237E"


class Mailer:
    def __init__(self, config):
        self.config = config
        self._queue: "queue.Queue" = queue.Queue()
        self._thread = None

    @property
    def enabled(self) -> bool:
        return bool(self.config.smtp_host)

    def send(self, to: str, subject: str, html_body: str, text_body: str):
        if not to:
            return
        if not self.enabled:
            log.info("Mail (nicht versendet, SMTP fehlt) an %s: %s", to, subject)
            return
        if self._thread is None:
            self._thread = threading.Thread(target=self._worker, daemon=True, name="mailer")
            self._thread.start()
        self._queue.put((to, subject, html_body, text_body))

    def _worker(self):
        while True:
            to, subject, html_body, text_body = self._queue.get()
            try:
                self._deliver(to, subject, html_body, text_body)
                log.info("Mail an %s gesendet: %s", to, subject)
            except Exception as e:  # nie den Server stören
                log.warning("Mail an %s fehlgeschlagen: %s", to, e)

    def _deliver(self, to, subject, html_body, text_body):
        c = self.config
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr(("ByteDroide", c.smtp_from))
        msg["To"] = to
        msg["Message-ID"] = make_msgid(domain=c.smtp_from.split("@")[-1] or None)
        if c.operator_email:
            msg["Reply-To"] = c.operator_email
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")
        context = ssl.create_default_context()
        if c.smtp_security == "ssl":
            server = smtplib.SMTP_SSL(c.smtp_host, c.smtp_port, context=context, timeout=30)
        else:
            server = smtplib.SMTP(c.smtp_host, c.smtp_port, timeout=30)
        with server:
            if c.smtp_security == "starttls":
                server.starttls(context=context)
            if c.smtp_user:
                server.login(c.smtp_user, c.smtp_password)
            server.send_message(msg)


# ---------------------------------------------------------------------------
# Vorlagen
# ---------------------------------------------------------------------------

def render(config, *, title: str, intro: str, paragraphs=(), button=None, facts=(), code=None,
           note: str = "", reason: str = "") -> tuple:
    """Baut (html, text) einer Mail im ByteDroide-Design.

    button = (Beschriftung, URL); facts = [(Label, Wert)]; code = hervorgehobener Text (z. B. Freischalt-Code).
    Alle Texte sind Klartext und werden escaped.
    """
    e = html.escape
    base = config.public_url
    parts_html = [f'<p style="margin:0 0 16px;font-size:16px;line-height:1.6;color:#1f2937">{e(intro)}</p>']
    parts_text = [intro, ""]
    for p in paragraphs:
        parts_html.append(f'<p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#374151">{e(p)}</p>')
        parts_text += [p, ""]
    if code:
        parts_html.append(
            '<div style="margin:8px 0 20px;padding:16px;border-radius:12px;background:#EEF2FF;text-align:center;'
            f'font-family:Menlo,Consolas,monospace;font-size:24px;font-weight:700;letter-spacing:3px;color:{BRAND_DARK}">'
            f'{e(code)}</div>')
        parts_text += [code, ""]
    if facts:
        rows = "".join(
            f'<tr><td style="padding:8px 12px;color:#6b7280;font-size:14px;border-bottom:1px solid #f1f5f9">{e(k)}</td>'
            f'<td style="padding:8px 12px;color:#111827;font-size:14px;font-weight:600;text-align:right;'
            f'border-bottom:1px solid #f1f5f9">{e(str(v))}</td></tr>' for k, v in facts)
        parts_html.append('<table role="presentation" width="100%" cellspacing="0" cellpadding="0" '
                          'style="margin:0 0 20px;border:1px solid #e5e7eb;border-radius:12px;border-collapse:separate;'
                          f'overflow:hidden">{rows}</table>')
        parts_text += [f"{k}: {v}" for k, v in facts] + [""]
    if button:
        label, url = button
        parts_html.append(
            '<table role="presentation" cellspacing="0" cellpadding="0" style="margin:8px 0 24px"><tr>'
            f'<td style="border-radius:999px;background:{BRAND}">'
            f'<a href="{e(url)}" style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:600;'
            f'color:#ffffff;text-decoration:none;border-radius:999px">{e(label)}</a></td></tr></table>'
            f'<p style="margin:0 0 16px;font-size:12px;color:#9ca3af;word-break:break-all">Falls der Knopf nicht '
            f'funktioniert: <a href="{e(url)}" style="color:{BRAND}">{e(url)}</a></p>')
        parts_text += [f"{label}: {url}", ""]
    if note:
        parts_html.append(f'<p style="margin:0 0 8px;font-size:13px;line-height:1.5;color:#6b7280">{e(note)}</p>')
        parts_text += [note, ""]

    reason = reason or "Du erhältst diese E-Mail, weil du ein Konto bei ByteDroide hast."
    footer_links = (f'<a href="{e(base)}/impressum" style="color:#6b7280">Impressum</a> · '
                    f'<a href="{e(base)}/datenschutz" style="color:#6b7280">Datenschutz</a> · '
                    f'<a href="{e(base)}/agb" style="color:#6b7280">Nutzungsbedingungen</a>')
    operator = ", ".join(x for x in (config.operator_name, config.operator_city) if x)
    html_doc = f"""<!doctype html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light"><title>{e(title)}</title></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif">
<span style="display:none;max-height:0;overflow:hidden">{e(intro)}</span>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#f3f4f6;padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;background:#ffffff;
border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(17,24,39,.08)">
<tr><td style="background:linear-gradient(135deg,{BRAND} 0%,{BRAND_DARK} 100%);background-color:{BRAND};padding:28px 32px">
<div style="font-size:13px;font-weight:700;letter-spacing:2px;color:rgba(255,255,255,.75);text-transform:uppercase">
&#129302; ByteDroide</div>
<div style="margin-top:8px;font-size:24px;font-weight:700;line-height:1.3;color:#ffffff">{e(title)}</div>
</td></tr>
<tr><td style="padding:28px 32px 12px">{''.join(parts_html)}</td></tr>
<tr><td style="padding:16px 32px 28px;border-top:1px solid #f1f5f9;font-size:12px;line-height:1.6;color:#9ca3af">
{e(reason)}<br>{e(operator) + '<br>' if operator else ''}{footer_links}
</td></tr>
</table></td></tr></table></body></html>"""
    text = "\n".join([title, "=" * len(title), ""] + parts_text +
                     ["--", reason, f"Impressum: {base}/impressum · Datenschutz: {base}/datenschutz"])
    return html_doc, text
