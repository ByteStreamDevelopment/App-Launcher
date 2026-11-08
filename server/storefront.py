"""Web-Auftritt: Startseite, Katalog, App-Seiten (mit QR-Codes) und Kontaktformular.

Die Seiten werden auf dem Server gerendert (schnell, suchmaschinenfreundlich). /static/store.js ergänzt für
angemeldete Nutzer die Aktionen (Kaufen, Code, Beta, Bewerten, Download, Entwickler kontaktieren).
"""

import html
import time
import urllib.parse

import qrcode_svg

CSS = """
:root{--bg:#f6f7fb;--card:#fff;--text:#1f2937;--muted:#6b7280;--brand:#3D5AFE;--brand2:#1A237E;--border:#e5e7eb;
--chip:#eef2ff;--star:#f59e0b;--ok:#059669;--err:#dc2626;--warn:#d97706;--shadow:0 8px 28px rgba(17,24,39,.08)}
@media (prefers-color-scheme:dark){:root{--bg:#0f1117;--card:#171a23;--text:#e5e7eb;--muted:#9ca3af;--border:#2a2f3a;
--chip:#1e2440;--shadow:0 8px 28px rgba(0,0,0,.35)}}
*{box-sizing:border-box}html,body{overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
a{color:var(--brand)}img{max-width:100%}
header.site{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;padding:18px 16px}
header.site .in,main,footer .in,.band .in{max-width:1120px;margin:0 auto}
header.site .top{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
header.site .logo{color:#fff;text-decoration:none;font-weight:800;font-size:21px;letter-spacing:.3px}
header.site .sp{flex:1}
header.site nav{display:flex;align-items:center;gap:4px;flex-wrap:wrap}
header.site nav a{color:rgba(255,255,255,.92);text-decoration:none;padding:6px 10px;border-radius:999px;font-size:15px}
header.site nav a:hover,header.site nav a.on{background:rgba(255,255,255,.14)}
header.site nav a.account{background:#fff;color:var(--brand2);font-weight:700}
.hero{display:flex;gap:32px;align-items:center;flex-wrap:wrap;padding:26px 0 14px}
.hero h1{margin:0 0 10px;font-size:40px;line-height:1.15;letter-spacing:-.5px}
.hero p{margin:0 0 18px;opacity:.92;max-width:600px;font-size:18px}
.hero .qr{background:#fff;border-radius:20px;padding:10px;width:150px;height:150px;flex:none}
.hero .qr svg{width:100%;height:100%}.hero .qrlabel{font-size:13px;opacity:.85;text-align:center;margin-top:6px}
.page-title h1{margin:14px 0 4px;font-size:30px}.page-title p{margin:0 0 6px;opacity:.9}
.btn{display:inline-block;background:#fff;color:var(--brand2);border:0;border-radius:999px;padding:11px 22px;
font:inherit;font-weight:700;text-decoration:none;margin:4px 8px 4px 0;cursor:pointer}
.btn.ghost{background:rgba(255,255,255,.16);color:#fff}.btn.primary{background:var(--brand);color:#fff}
.btn.outline{background:transparent;color:var(--brand);border:1px solid var(--border)}
.btn.small{padding:7px 14px;font-size:14px}.btn.danger{background:var(--err);color:#fff}
.btn:disabled{opacity:.55;cursor:default}
main{padding:24px 16px 56px}
h2.title{font-size:24px;margin:34px 0 14px;display:flex;align-items:center;gap:12px}
h2.title a{font-size:15px;font-weight:600;margin-left:auto}
form.search{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 14px}
input,select,textarea{font:inherit;color:var(--text);background:var(--card);border:1px solid var(--border);
border-radius:12px;padding:10px 13px;width:100%}
textarea{min-height:130px;resize:vertical}label{display:block;font-size:14px;color:var(--muted);margin:12px 0 4px}
form.search input{flex:1;min-width:200px;border-radius:999px;width:auto}form.search select{width:auto;border-radius:999px}
form.search button{border:0;border-radius:999px;background:var(--brand);color:#fff;padding:0 24px;font:inherit;
font-weight:700;cursor:pointer}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}.chips a{padding:6px 14px;border-radius:999px;
background:var(--chip);text-decoration:none;font-size:14px;font-weight:600}.chips a.on{background:var(--brand);color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:16px;text-decoration:none;
color:inherit;display:block;transition:transform .12s,box-shadow .12s}
a.card:hover{transform:translateY(-2px);box-shadow:var(--shadow)}
.row{display:flex;gap:14px;align-items:center}
.icon{width:64px;height:64px;border-radius:16px;flex:none;object-fit:cover;background:var(--chip);display:flex;
align-items:center;justify-content:center;font-weight:800;font-size:26px;color:var(--brand)}
.icon.big{width:104px;height:104px;border-radius:26px;font-size:44px}
.name{font-weight:700;font-size:17px}.muted{color:var(--muted);font-size:14px}
.desc{margin-top:10px;font-size:14px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
overflow:hidden}
.badge{display:inline-block;font-size:12px;font-weight:700;padding:2px 9px;border-radius:999px;background:var(--chip);
color:var(--brand);margin:2px 4px 2px 0}
.stars{color:var(--star);letter-spacing:1px}
.section{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:20px 22px;margin:0 0 16px;min-width:0}
.section h2{font-size:19px;margin:0 0 12px}
.layout{display:grid;grid-template-columns:1fr 280px;gap:16px;align-items:start}.layout>div{min-width:0}
@media (max-width:860px){.layout{grid-template-columns:1fr}}
.shots{display:flex;gap:12px;overflow-x:auto;padding-bottom:6px;scroll-snap-type:x mandatory}
.shots img{height:380px;max-width:none;border-radius:14px;border:1px solid var(--border);scroll-snap-align:start;cursor:zoom-in}
@media (max-width:600px){.shots img{height:300px}.hero h1{font-size:30px}}
.qrbox{text-align:center}.qrbox svg{width:200px;height:200px;max-width:100%}
.review{border-top:1px solid var(--border);padding:12px 0}.review:first-of-type{border-top:0}
.reply{margin:8px 0 0 14px;padding:8px 12px;border-left:3px solid var(--brand);background:var(--chip);border-radius:8px;
font-size:14px}
.bars div{display:flex;align-items:center;gap:8px;font-size:13px}.bars span.bar{flex:1;height:8px;background:var(--chip);
border-radius:99px;overflow:hidden}.bars span.bar i{display:block;height:100%;background:var(--star)}
pre.notes{white-space:pre-wrap;font:inherit;margin:0;overflow-wrap:anywhere}
.features{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:14px}
.feature{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:20px}
.feature .em{font-size:30px}.feature h3{margin:8px 0 6px;font-size:17px}.feature p{margin:0;color:var(--muted);font-size:15px}
.stats{display:flex;gap:28px;flex-wrap:wrap;margin:10px 0 0}.stats div{font-size:14px;opacity:.9}
.stats b{display:block;font-size:26px}
.band{background:var(--card);border-top:1px solid var(--border);border-bottom:1px solid var(--border);padding:34px 16px;
margin:36px -16px}
.band .in{display:flex;gap:28px;align-items:center;flex-wrap:wrap;justify-content:space-between}
.band h2{margin:0 0 8px;font-size:26px}.band p{margin:0;color:var(--muted);max-width:620px}
details{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:14px 18px;margin:0 0 10px}
details summary{cursor:pointer;font-weight:700}details p{margin:10px 0 0;color:var(--muted)}
.cats{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:10px}
.cats a{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:14px 16px;text-decoration:none;
font-weight:700;color:inherit}.cats a span{display:block;font-weight:400;color:var(--muted);font-size:13px}
.alert{border-radius:12px;padding:12px 16px;margin:0 0 14px}.alert.ok{background:rgba(5,150,105,.12);color:var(--ok)}
.alert.err{background:rgba(220,38,38,.1);color:var(--err)}
.hp{position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden}
#actions:empty{display:none}
.empty{text-align:center;color:var(--muted);padding:40px 0}
footer{padding:28px 16px 40px;color:var(--muted);font-size:14px;border-top:1px solid var(--border)}
footer .in{display:flex;gap:24px;flex-wrap:wrap;justify-content:space-between}footer a{color:var(--muted);margin-right:14px}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#111827;color:#fff;padding:11px 20px;
border-radius:999px;z-index:20;max-width:92vw}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:15;
padding:16px}.modal .box{background:var(--card);border-radius:18px;padding:22px;max-width:520px;width:100%;
max-height:90vh;overflow:auto}
.lightbox{position:fixed;inset:0;background:rgba(0,0,0,.92);display:flex;align-items:center;justify-content:center;z-index:30}
.lightbox img{max-height:92vh;max-width:96vw;border-radius:10px}
"""

e = html.escape


def stars(avg: float) -> str:
    full = int(round(avg))
    return "★" * full + "☆" * (5 - full)


def _icon(app, big=False) -> str:
    cls = "icon big" if big else "icon"
    if app.get("avatar_url"):
        return f'<img class="{cls}" src="{e(app["avatar_url"])}" alt="" loading="lazy">'
    return f'<div class="{cls}">{e(app["name"][:1].upper())}</div>'


def _version(tag: str) -> str:
    return tag[1:] if tag[:1] in ("v", "V") and tag[1:2].isdigit() else tag


NAV = (("/apps", "Apps"), ("/hilfe", "Hilfe"), ("/hilfe/entwickler", "Für Entwickler"), ("/kontakt", "Kontakt"))


def layout(config, title: str, body: str, hero: str = "", description: str = "", active: str = "",
           body_attrs: str = "") -> str:
    base = e(config.public_url)
    desc = e(description or "ByteDroide – der App-Store für unabhängige Android-Apps. Ohne Google, mit Betas, "
                            "Bewertungen und automatischen Updates.")
    nav = "".join(f'<a href="{base}{href}" class="{"on" if active == href else ""}">{label}</a>' for href, label in NAV)
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>
<meta name="description" content="{desc}"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{desc}"><meta property="og:site_name" content="ByteDroide">
<link rel="icon" href="/favicon.ico" type="image/svg+xml"><style>{CSS}</style></head><body {body_attrs}>
<header class="site"><div class="in"><div class="top"><a class="logo" href="{base}/">&#129302; ByteDroide</a>
<span class="sp"></span><nav>{nav}<a class="account" id="account-link" href="{base}/konto#/login">Anmelden</a></nav>
</div>{hero}</div></header>
<main>{body}</main>
<footer><div class="in"><div><b>&#129302; ByteDroide</b><br>Der App-Store für unabhängige Android-Apps.</div>
<div><a href="{base}/apps">Apps</a><a href="{base}/hilfe">Hilfe &amp; Doku</a><a href="{base}/kontakt">Kontakt</a>
<a href="{base}/konto">Mein Konto</a><br><a href="{base}/impressum">Impressum</a><a href="{base}/datenschutz">Datenschutz</a>
<a href="{base}/agb">Nutzungsbedingungen</a><a href="{base}/widerruf">Widerruf</a></div></div></footer>
<script src="/static/store.js" defer></script></body></html>"""


# ---------------------------------------------------------------------------
# Karten & Listen
# ---------------------------------------------------------------------------

def _app_card(base, a) -> str:
    rating = a.get("rating") or {}
    meta = []
    if rating.get("count"):
        meta.append(f'<span class="stars">{stars(rating["average"])}</span> {rating["average"]:.1f} ({rating["count"]})')
    meta.append(f'Version {e(_version(a["release"]["tag"]))}')
    badges = ""
    if a.get("price"):
        badges += f'<span class="badge">{e(a["price"])}</span>'
    elif a.get("access") == "code":
        badges += '<span class="badge">🔒 Code</span>'
    else:
        badges += '<span class="badge">Kostenlos</span>'
    if a.get("beta", {}).get("available"):
        badges += '<span class="badge">Beta</span>'
    return f"""<a class="card" href="{e(base)}/app/{e(a['id'])}"><div class="row">{_icon(a)}<div style="min-width:0">
<div class="name">{e(a['name'])}</div><div class="muted">{e(a['owner'])}{(' · ' + e(a['category'])) if a.get('category') else ''}</div>
<div class="muted">{' · '.join(meta)}</div></div></div>
{f'<div class="desc">{e(a["description"])}</div>' if a.get("description") else ''}
<div style="margin-top:8px">{badges}</div></a>"""


def _grid(base, apps) -> str:
    if not apps:
        return '<div class="empty">Keine Apps gefunden.</div>'
    return f'<div class="grid">{"".join(_app_card(base, a) for a in apps)}</div>'


def _published(a) -> str:
    return a["release"].get("published_at") or ""


def _popularity(a):
    r = a.get("rating") or {}
    return (r.get("average", 0) * min(r.get("count", 0), 20), r.get("count", 0))


# ---------------------------------------------------------------------------
# Startseite
# ---------------------------------------------------------------------------

FAQ = [
    ("Was ist ByteDroide?", "Ein App-Store für Android, in dem unabhängige Entwicklerinnen und Entwickler ihre Apps "
                            "veröffentlichen. ByteDroide installiert sie und hält sie automatisch aktuell."),
    ("Brauche ich ein Google-Konto?", "Nein. ByteDroide funktioniert ohne Google-Dienste. Benachrichtigungen gibt es "
                                      "per E-Mail oder als Push über ntfy."),
    ("Ist das sicher?", "Neue Apps werden von einem Admin geprüft, Uploads werden auf Schadsoftware gescannt und jede "
                        "Version muss zur App passen (gleicher Paketname, steigende Versionsnummer)."),
    ("Was kostet das?", "Der Store ist kostenlos. Einige Apps sind kostenpflichtig oder brauchen einen "
                        "Freischalt-Code vom Entwickler."),
    ("Wie veröffentliche ich eine eigene App?", "Konto erstellen, Entwickler-Zugang beantragen und nach der Freigabe "
                                                "die App per Upload oder aus GitHub/Forgejo anlegen."),
]


def home(config, apps: list, stats: dict) -> str:
    base = config.public_url
    qr = ""
    if config.store_app_id:
        qr = (f'<div><div class="qr" title="Mit dem Handy scannen">{qrcode_svg.svg(base + "/download", module=4)}'
              f'</div><div class="qrlabel">Scannen &amp; installieren</div></div>')
    hero = f"""<div class="hero"><div style="flex:1;min-width:280px"><h1>Apps unabhängiger Entwickler.<br>Ohne Google.</h1>
<p>Entdecke Android-Apps abseits der großen Stores – mit automatischen Updates, Beta-Versionen, ehrlichen
Bewertungen und direktem Draht zu den Entwicklern.</p>
{f'<a class="btn" href="{e(base)}/download">ByteDroide für Android laden</a>' if config.store_app_id else ''}
<a class="btn ghost" href="{e(base)}/apps">Apps entdecken</a>
<div class="stats"><div><b>{len(apps)}</b>Apps</div><div><b>{stats.get("developers", 0)}</b>Entwickler</div>
<div><b>{stats.get("downloads", 0)}</b>Downloads</div><div><b>{stats.get("reviews", 0)}</b>Bewertungen</div></div>
</div>{qr}</div>"""
    newest = sorted(apps, key=_published, reverse=True)[:6]
    popular = sorted([a for a in apps if (a.get("rating") or {}).get("count")], key=_popularity, reverse=True)[:6]
    cats = {}
    for a in apps:
        if a.get("category"):
            cats[a["category"]] = cats.get(a["category"], 0) + 1
    cat_html = "".join(f'<a href="{e(base)}/apps?{urllib.parse.urlencode({"kategorie": c})}">{e(c)}'
                       f'<span>{n} App{"s" if n != 1 else ""}</span></a>' for c, n in sorted(cats.items()))
    features = [
        ("🔄", "Automatische Updates", "ByteDroide prüft im Hintergrund und aktualisiert deine Apps mit einem Tipp."),
        ("🧪", "Beta-Kanal", "Neue Funktionen vor allen anderen testen – und jederzeit zurück zur stabilen Version."),
        ("🔔", "Ohne Google", "Benachrichtigungen per E-Mail oder Push über ntfy. Keine Werbung, kein Tracking."),
        ("🛡️", "Geprüft & gescannt", "Admin-Prüfung, Virenscan und Signatur-Checks für jede neue Version."),
        ("💬", "Direkter Draht", "Fehler melden, Feedback geben und Fragen stellen – direkt an die Entwickler."),
        ("⭐", "Ehrliche Bewertungen", "Bewerten kann nur, wer die App wirklich über ByteDroide installiert hat."),
    ]
    feat_html = "".join(f'<div class="feature"><div class="em">{em}</div><h3>{t}</h3><p>{d}</p></div>'
                        for em, t, d in features)
    faq_html = "".join(f"<details><summary>{e(q)}</summary><p>{e(a)}</p></details>" for q, a in FAQ)
    body = f"""
<h2 class="title">Neu im Store <a href="{e(base)}/apps?sortierung=neu">Alle ansehen →</a></h2>{_grid(base, newest)}
{f'<h2 class="title">Beliebt <a href="{e(base)}/apps?sortierung=beliebt">Alle ansehen →</a></h2>' + _grid(base, popular) if popular else ''}
{f'<h2 class="title">Kategorien</h2><div class="cats">{cat_html}</div>' if cat_html else ''}
<h2 class="title">Warum ByteDroide?</h2><div class="features">{feat_html}</div>
<div class="band"><div class="in"><div><h2>Du entwickelst Android-Apps?</h2>
<p>Veröffentliche sie in ByteDroide – per Upload, direkt aus GitHub oder Forgejo oder automatisch aus deiner
CI-Pipeline. Mit Betas, gestaffelten Rollouts, Freischalt-Codes, Verkauf und Statistiken.</p></div>
<div><a class="btn primary" href="{e(base)}/konto#/login?entwickler=1">Entwickler werden</a>
<a class="btn outline" href="{e(base)}/hilfe/entwickler">Dokumentation</a></div></div></div>
<h2 class="title">Häufige Fragen <a href="{e(base)}/hilfe">Zur Hilfe →</a></h2>{faq_html}"""
    return layout(config, "ByteDroide – Apps unabhängiger Entwickler", body, hero, active="/")


# ---------------------------------------------------------------------------
# Katalog
# ---------------------------------------------------------------------------

SORTS = {"name": "Name", "neu": "Neueste", "beliebt": "Beliebteste"}


def catalog(config, apps: list, query: str = "", category: str = "", sort: str = "") -> str:
    base = config.public_url
    q = query.strip().lower()
    sort = sort if sort in SORTS else "name"
    categories = sorted({a["category"] for a in apps if a.get("category")})
    shown = [a for a in apps if (not category or a.get("category") == category) and (
        not q or q in a["name"].lower() or q in (a.get("description") or "").lower()
        or q in (a.get("owner") or "").lower())]
    if sort == "neu":
        shown.sort(key=_published, reverse=True)
    elif sort == "beliebt":
        shown.sort(key=_popularity, reverse=True)

    def link(**kw):
        params = {"q": query, "kategorie": category, "sortierung": sort if sort != "name" else ""}
        params.update(kw)
        return "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v})

    chips = "".join(f'<a class="{"on" if c == category else ""}" href="{e(link(kategorie=c))}">{e(c)}</a>'
                    for c in categories)
    if chips:
        chips = f'<div class="chips"><a class="{"" if category else "on"}" href="{e(link(kategorie=""))}">Alle</a>{chips}</div>'
    options = "".join(f'<option value="{k}"{" selected" if k == sort else ""}>{v}</option>' for k, v in SORTS.items())
    hero = (f'<div class="page-title"><h1>Alle Apps</h1><p>{len(apps)} Apps von unabhängigen Entwicklern</p></div>')
    body = f"""<form class="search" method="get"><input name="q" value="{e(query)}" placeholder="Apps durchsuchen"
aria-label="Apps durchsuchen">{f'<input type="hidden" name="kategorie" value="{e(category)}">' if category else ''}
<select name="sortierung" aria-label="Sortierung">{options}</select><button type="submit">Suchen</button></form>
{chips}{_grid(base, shown)}"""
    return layout(config, "Alle Apps – ByteDroide", body, hero, active="/apps")


# ---------------------------------------------------------------------------
# App-Seite
# ---------------------------------------------------------------------------

def app_page(config, app: dict, reviews: dict) -> str:
    base = config.public_url
    page_url = f"{base}/app/{app['id']}"
    rel = app["release"]
    rating = reviews or {}
    free_open = not app.get("price") and app.get("access") == "open"
    buttons = [f'<a class="btn primary" href="{e(page_url)}" rel="nofollow">In ByteDroide öffnen</a>']
    if free_open:
        buttons.append(f'<a class="btn outline" href="{e(base)}/api/apps/{e(app["id"])}/download">APK direkt laden</a>')
    if config.store_app_id:
        buttons.append(f'<a class="btn outline" href="{e(base)}/download">ByteDroide laden</a>')
    deep = f'bytedroide://app/{app["id"]}'
    badges = ""
    if app.get("price"):
        badges += f'<span class="badge">{e(app["price"])}</span>'
    elif app.get("access") == "code":
        badges += '<span class="badge">🔒 Nur mit Freischalt-Code</span>'
    else:
        badges += '<span class="badge">Kostenlos</span>'
    if app.get("category"):
        badges += f'<span class="badge">{e(app["category"])}</span>'
    if app.get("beta", {}).get("available"):
        badges += '<span class="badge">Beta verfügbar</span>'
    summary = ""
    if rating.get("count"):
        summary = (f'<span class="stars">{stars(rating["average"])}</span> <b>{rating["average"]:.1f}</b> '
                   f'<span class="muted">({rating["count"]} Bewertung{"en" if rating["count"] != 1 else ""})</span>')
    header = f"""<div class="section"><div class="row" style="align-items:flex-start">{_icon(app, big=True)}<div style="min-width:0">
<h1 style="margin:0;font-size:30px;line-height:1.2">{e(app['name'])}</h1><div class="muted">{e(app['owner'])} · Version
{e(_version(rel['tag']))}</div><div style="margin-top:4px">{summary}</div><div style="margin-top:6px">{badges}</div>
</div></div><div style="margin-top:14px">{''.join(buttons)}</div>
<p class="muted" style="margin:6px 0 0">Kein „Öffnen“? Dann <a href="{e(deep)}">hier tippen</a> oder zuerst ByteDroide
installieren.</p><div id="actions"></div></div>"""
    shots = ""
    if app.get("screenshots"):
        shots = ('<div class="section"><h2>Screenshots</h2><div class="shots">' + "".join(
            f'<img src="{e(u)}" alt="Screenshot {i + 1}" loading="lazy" data-lightbox>'
            for i, u in enumerate(app["screenshots"])) + "</div></div>")
    description = (f'<div class="section"><h2>Beschreibung</h2><pre class="notes">{e(app["description"])}</pre></div>'
                   if app.get("description") else "")
    notes = (f'<div class="section"><h2>Neu in {e(_version(rel["tag"]))}</h2><pre class="notes">{e(rel["notes"])}</pre></div>'
             if (rel.get("notes") or "").strip() else "")
    body = f"""<div class="layout"><div>{header}{shots}{description}{notes}
<div class="section" id="reviews">{reviews_html(rating)}</div>
<div class="section" id="contact"><h2>Fehler gefunden oder Feedback?</h2>
<p class="muted">Schreib dem Entwickler direkt – er bekommt eine Benachrichtigung und kann dir antworten.</p>
<a class="btn outline small" href="{e(base)}/konto#/login">Anmelden, um zu schreiben</a></div></div>
<div>{_side(base, app, page_url, rel)}</div></div>"""
    attrs = f'data-app-id="{e(app["id"])}"'
    return layout(config, f"{app['name']} – ByteDroide", body, description=(app.get("description") or "")[:160],
                  body_attrs=attrs)


def reviews_html(rating: dict) -> str:
    if not rating.get("count"):
        return ('<h2>Bewertungen</h2><p class="muted">Noch keine Bewertungen. Bewerten kann, wer die App über '
                'ByteDroide geladen hat.</p>')
    total = max(rating["count"], 1)
    bars = "".join(f'<div>{5 - i} ★ <span class="bar"><i style="width:{n * 100 // total}%"></i></span> {n}</div>'
                   for i, n in enumerate(rating["distribution"]))
    items = []
    for r in rating["reviews"][:50]:
        when = time.strftime("%d.%m.%Y", time.localtime(r["updated_at"]))
        reply = f'<div class="reply"><b>Antwort des Entwicklers:</b> {e(r["reply"])}</div>' if r.get("reply") else ""
        text = f'<div>{e(r["text"])}</div>' if r["text"] else ""
        items.append(f'<div class="review"><span class="stars">{stars(r["rating"])}</span> <b>{e(r["username"])}</b>'
                     f' <span class="muted">· {when} · Version {e(_version(r["version"]))}</span>{text}{reply}</div>')
    return (f'<h2>Bewertungen</h2><div class="row" style="align-items:flex-start;gap:24px;flex-wrap:wrap"><div>'
            f'<div style="font-size:44px;font-weight:800;line-height:1">{rating["average"]:.1f}</div>'
            f'<div class="stars">{stars(rating["average"])}</div><div class="muted">{rating["count"]} Bewertungen</div>'
            f'</div><div class="bars" style="flex:1;min-width:200px">{bars}</div></div>{"".join(items)}')


def _size(app) -> str:
    size = (app.get("apks") or [{}])[0].get("size") or 0
    return f"{size / 1048576:.1f} MB".replace(".", ",") if size >= 1048576 else f"{max(size // 1024, 1)} KB"


def _side(base, app, page_url, rel) -> str:
    rows = [("Entwickler", e(app["owner"])), ("Version", e(_version(rel["tag"]))), ("Größe", _size(app))]
    if app.get("category"):
        rows.append(("Kategorie", e(app["category"])))
    if app.get("homepage"):
        rows.append(("Webseite", f'<a href="{e(app["homepage"])}" rel="nofollow noopener">{e(app["homepage"])}</a>'))
    if app.get("html_url") and app.get("html_url") != app.get("homepage"):
        rows.append(("Quellcode", f'<a href="{e(app["html_url"])}" rel="nofollow noopener">ansehen</a>'))
    info = "".join(f'<div class="muted" style="margin-top:8px">{k}</div><div style="overflow-wrap:anywhere">{v}</div>'
                   for k, v in rows)
    return f"""<div class="section qrbox"><h2>Auf dem Handy öffnen</h2>{qrcode_svg.svg(page_url, module=5)}
<p class="muted">QR-Code mit der Kamera scannen – die Seite öffnet sich direkt in ByteDroide.</p>
<a href="{e(page_url)}/qr.svg" download>QR-Code herunterladen</a></div>
<div class="section"><h2>Infos</h2>{info}
<p style="margin:14px 0 0"><a href="{e(base)}/kontakt?thema=meldung">App melden</a></p></div>"""


# ---------------------------------------------------------------------------
# Kontakt
# ---------------------------------------------------------------------------

def contact_page(config, topics: dict, form=None, error="", sent=False, topic="") -> str:
    base = config.public_url
    form = form or {}
    hero = '<div class="page-title"><h1>Kontakt</h1><p>Fragen, Feedback oder ein Problem? Schreib uns.</p></div>'
    if sent:
        body = ('<div class="section" style="max-width:720px"><div class="alert ok">Danke! Deine Nachricht ist '
                'angekommen. Du bekommst gleich eine Bestätigung per E-Mail.</div><a class="btn primary" '
                f'href="{e(base)}/">Zur Startseite</a></div>')
        return layout(config, "Kontakt – ByteDroide", body, hero, active="/kontakt")
    selected = form.get("topic") or topic
    options = "".join(f'<option value="{k}"{" selected" if k == selected else ""}>{e(v)}</option>'
                      for k, v in topics.items())
    v = lambda k: e(form.get(k, ""))  # noqa: E731
    operator = e(config.operator_email) if config.operator_email else ""
    body = f"""<div class="layout"><div><div class="section">
{f'<div class="alert err">{e(error)}</div>' if error else ''}
<form method="post" action="/kontakt">
<label for="name">Name</label><input id="name" name="name" required maxlength="100" value="{v('name')}" autocomplete="name">
<label for="email">E-Mail-Adresse</label><input id="email" name="email" type="email" required value="{v('email')}"
autocomplete="email">
<label for="topic">Worum geht es?</label><select id="topic" name="topic">{options}</select>
<label for="subject">Betreff</label><input id="subject" name="subject" required maxlength="150" value="{v('subject')}">
<label for="message">Nachricht</label><textarea id="message" name="message" required minlength="10"
maxlength="8000">{v('message')}</textarea>
<div class="hp" aria-hidden="true"><label>Webseite<input name="website" tabindex="-1" autocomplete="off"></label></div>
<label style="display:flex;gap:10px;align-items:flex-start;color:var(--text)"><input type="checkbox" name="privacy"
value="1" required style="width:auto;margin-top:5px"><span>Ich bin einverstanden, dass meine Angaben zur Bearbeitung der
Anfrage gespeichert werden (<a href="{e(base)}/datenschutz">Datenschutzerklärung</a>).</span></label>
<button class="btn primary" type="submit" style="margin-top:14px">Nachricht senden</button></form></div></div>
<div><div class="section"><h2>Schneller zum Ziel</h2>
<p><b>Problem mit einer bestimmten App?</b><br><span class="muted">Schreib direkt dem Entwickler – auf der App-Seite unter
„Fehler gefunden oder Feedback?“.</span></p>
<p><b>Hilfe zur Bedienung</b><br><a href="{e(base)}/hilfe">Zur Dokumentation</a></p>
<p><b>Rechtswidrige Inhalte melden</b><br><span class="muted">Bitte Thema „Rechtswidrigen Inhalt melden“ wählen und die
App genau bezeichnen.</span></p>
{f'<p><b>Per E-Mail</b><br><a href="mailto:{operator}">{operator}</a></p>' if operator else ''}
</div></div></div>"""
    return layout(config, "Kontakt – ByteDroide", body, hero, active="/kontakt")
