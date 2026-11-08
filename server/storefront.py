"""Web-Store: Katalog und App-Seiten im Browser, mit QR-Codes zum Öffnen in ByteDroide."""

import html
import time
import urllib.parse

import qrcode_svg

CSS = """
:root{--bg:#f6f7fb;--card:#fff;--text:#1f2937;--muted:#6b7280;--brand:#3D5AFE;--brand2:#1A237E;--border:#e5e7eb;
--chip:#eef2ff;--star:#f59e0b}
@media (prefers-color-scheme:dark){:root{--bg:#0f1117;--card:#171a23;--text:#e5e7eb;--muted:#9ca3af;--border:#2a2f3a;
--chip:#1e2440}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);
font:16px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
a{color:var(--brand)}
header{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;padding:22px 16px}
header .in,main,footer .in{max-width:1080px;margin:0 auto}
header .top{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
header .logo{color:#fff;text-decoration:none;font-weight:800;font-size:20px;letter-spacing:.5px}
header .sp{flex:1}header nav a{color:rgba(255,255,255,.9);text-decoration:none;margin-left:14px;font-size:15px}
.hero{display:flex;gap:28px;align-items:center;flex-wrap:wrap;margin-top:18px}
.hero h1{margin:0 0 6px;font-size:30px;line-height:1.2}.hero p{margin:0 0 14px;opacity:.9;max-width:560px}
.hero .qr{background:#fff;border-radius:16px;padding:8px;width:132px;height:132px}.hero .qr svg{width:100%;height:100%}
.btn{display:inline-block;background:#fff;color:var(--brand2);border-radius:999px;padding:10px 20px;font-weight:700;
text-decoration:none;margin:4px 8px 4px 0}.btn.ghost{background:rgba(255,255,255,.15);color:#fff}
.btn.primary{background:var(--brand);color:#fff}
main{padding:22px 16px 48px}
form.search{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 14px}
form.search input{flex:1;min-width:200px;padding:11px 14px;border:1px solid var(--border);border-radius:999px;
background:var(--card);color:var(--text);font:inherit}
form.search button{border:0;border-radius:999px;background:var(--brand);color:#fff;padding:0 22px;font:inherit;
font-weight:700;cursor:pointer}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 18px}.chips a{padding:5px 14px;border-radius:999px;
background:var(--chip);text-decoration:none;font-size:14px;font-weight:600}.chips a.on{background:var(--brand);color:#fff}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:16px;text-decoration:none;
color:inherit;display:block;transition:transform .12s,box-shadow .12s}
a.card:hover{transform:translateY(-2px);box-shadow:0 8px 24px rgba(17,24,39,.08)}
.row{display:flex;gap:14px;align-items:center}
.icon{width:64px;height:64px;border-radius:16px;flex:none;object-fit:cover;background:var(--chip);display:flex;
align-items:center;justify-content:center;font-weight:800;font-size:26px;color:var(--brand)}
.icon.big{width:96px;height:96px;border-radius:24px;font-size:40px}
.name{font-weight:700;font-size:17px}.muted{color:var(--muted);font-size:14px}
.desc{margin-top:10px;font-size:14px;color:var(--muted);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
overflow:hidden}
.badge{display:inline-block;font-size:12px;font-weight:700;padding:2px 9px;border-radius:999px;background:var(--chip);
color:var(--brand);margin-right:4px}
.stars{color:var(--star);letter-spacing:1px}
.section{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:20px 22px;margin:0 0 16px}
.section h2{font-size:19px;margin:0 0 10px}
.layout{display:grid;grid-template-columns:1fr 260px;gap:16px;align-items:start}
.layout>div,.section{min-width:0}html,body{overflow-x:hidden}
@media (max-width:820px){.layout{grid-template-columns:1fr}}
.shots{display:flex;gap:12px;overflow-x:auto;padding-bottom:6px;scroll-snap-type:x mandatory}
.shots img{height:360px;border-radius:14px;border:1px solid var(--border);scroll-snap-align:start}
@media (max-width:600px){.shots img{height:280px}}
.qrbox{text-align:center}.qrbox svg{width:200px;height:200px;max-width:100%}
.review{border-top:1px solid var(--border);padding:12px 0}.review:first-of-type{border-top:0}
.reply{margin:8px 0 0 14px;padding:8px 12px;border-left:3px solid var(--brand);background:var(--chip);border-radius:8px;
font-size:14px}
.bars div{display:flex;align-items:center;gap:8px;font-size:13px}.bars span.bar{flex:1;height:8px;background:var(--chip);
border-radius:99px;overflow:hidden}.bars span.bar i{display:block;height:100%;background:var(--star)}
pre.notes{white-space:pre-wrap;font:inherit;margin:0}
footer{padding:20px 16px 36px;color:var(--muted);font-size:14px}footer a{color:var(--muted);margin-right:14px}
.empty{text-align:center;color:var(--muted);padding:40px 0}
"""

e = html.escape


def _stars(avg: float) -> str:
    full = int(round(avg))
    return "★" * full + "☆" * (5 - full)


def _icon(app, big=False) -> str:
    cls = "icon big" if big else "icon"
    if app.get("avatar_url"):
        return f'<img class="{cls}" src="{e(app["avatar_url"])}" alt="" loading="lazy">'
    return f'<div class="{cls}">{e(app["name"][:1].upper())}</div>'


def _version(tag: str) -> str:
    return tag[1:] if tag[:1] in ("v", "V") and tag[1:2].isdigit() else tag


def _layout(config, title: str, body: str, hero: str = "", description: str = "") -> str:
    base = e(config.public_url)
    download = (f'<a href="{base}/download">ByteDroide laden</a>' if config.store_app_id else "")
    desc = e(description or "ByteDroide – der App-Store für unabhängige Android-Apps.")
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>
<meta name="description" content="{desc}"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{desc}"><link rel="icon" href="/favicon.ico" type="image/svg+xml">
<style>{CSS}</style></head><body>
<header><div class="in"><div class="top"><a class="logo" href="{base}/">&#129302; ByteDroide</a><span class="sp"></span>
<nav><a href="{base}/">Apps</a>{download}<a href="{base}/portal">Für Entwickler</a></nav></div>{hero}</div></header>
<main>{body}</main>
<footer><div class="in"><a href="{base}/impressum">Impressum</a><a href="{base}/datenschutz">Datenschutz</a>
<a href="{base}/agb">Nutzungsbedingungen</a><a href="{base}/widerruf">Widerruf</a></div></footer>
</body></html>"""


def catalog(config, apps: list, query: str = "", category: str = "") -> str:
    base = config.public_url
    q = query.strip().lower()
    categories = sorted({a["category"] for a in apps if a.get("category")})
    shown = [a for a in apps if (not category or a.get("category") == category) and (
        not q or q in a["name"].lower() or q in (a.get("description") or "").lower()
        or q in (a.get("owner") or "").lower())]
    hero_qr = ""
    if config.store_app_id:
        hero_qr = f'<div class="qr" title="Mit dem Handy scannen">{qrcode_svg.svg(base + "/download", module=4)}</div>'
    hero = f"""<div class="hero"><div><h1>Apps unabhängiger Entwickler</h1>
<p>Entdecken, installieren und automatisch aktuell halten – mit Beta-Versionen, Bewertungen und ohne Google.</p>
{f'<a class="btn" href="{e(base)}/download">ByteDroide für Android laden</a>' if config.store_app_id else ''}
<a class="btn ghost" href="{e(base)}/portal">Eigene App veröffentlichen</a></div>{hero_qr}</div>"""
    chips = "".join(
        f'<a class="{"on" if c == category else ""}" href="?{urllib.parse.urlencode({"kategorie": c, "q": query} if query else {"kategorie": c})}">{e(c)}</a>'
        for c in categories)
    if chips:
        chips = f'<div class="chips"><a class="{"" if category else "on"}" href="?{urllib.parse.urlencode({"q": query}) if query else ""}">Alle</a>{chips}</div>'
    cards = []
    for a in shown:
        rating = a.get("rating") or {}
        meta = []
        if rating.get("count"):
            meta.append(f'<span class="stars">{_stars(rating["average"])}</span> {rating["average"]:.1f} ({rating["count"]})')
        meta.append(f'Version {e(_version(a["release"]["tag"]))}')
        badges = ""
        if a.get("price"):
            badges += f'<span class="badge">{e(a["price"])}</span>'
        elif a.get("access") == "code":
            badges += '<span class="badge">🔒 Code</span>'
        if a.get("beta", {}).get("available"):
            badges += '<span class="badge">Beta</span>'
        cards.append(f"""<a class="card" href="{e(base)}/app/{e(a['id'])}"><div class="row">{_icon(a)}<div>
<div class="name">{e(a['name'])}</div><div class="muted">{e(a['owner'])}{(' · ' + e(a['category'])) if a.get('category') else ''}</div>
<div class="muted">{' · '.join(meta)}</div></div></div>
{f'<div class="desc">{e(a["description"])}</div>' if a.get("description") else ''}
{f'<div style="margin-top:8px">{badges}</div>' if badges else ''}</a>""")
    grid = f'<div class="grid">{"".join(cards)}</div>' if cards else '<div class="empty">Keine Apps gefunden.</div>'
    body = f"""<form class="search" method="get"><input name="q" value="{e(query)}" placeholder="Apps durchsuchen"
aria-label="Apps durchsuchen">{f'<input type="hidden" name="kategorie" value="{e(category)}">' if category else ''}
<button type="submit">Suchen</button></form>{chips}{grid}"""
    return _layout(config, "ByteDroide – App-Store", body, hero)


def app_page(config, app: dict, reviews: dict) -> str:
    base = config.public_url
    page_url = f"{base}/app/{app['id']}"
    rel = app["release"]
    rating = reviews or {}
    free_open = not app.get("price") and app.get("access") == "open"
    buttons = [f'<a class="btn primary" href="{e(page_url)}" rel="nofollow">In ByteDroide öffnen</a>']
    if free_open:
        buttons.append(f'<a class="btn" style="border:1px solid var(--border)" href="{e(base)}/api/apps/{e(app["id"])}/download">'
                       'APK direkt laden</a>')
    if config.store_app_id:
        buttons.append(f'<a class="btn" style="border:1px solid var(--border)" href="{e(base)}/download">'
                       'ByteDroide laden</a>')
    deep = f'bytedroide://app/{app["id"]}'
    badges = ""
    if app.get("price"):
        badges += f'<span class="badge">{e(app["price"])}</span>'
    elif app.get("access") == "code":
        badges += '<span class="badge">🔒 Nur mit Freischalt-Code</span>'
    if app.get("category"):
        badges += f'<span class="badge">{e(app["category"])}</span>'
    if app.get("beta", {}).get("available"):
        badges += '<span class="badge">Beta verfügbar</span>'
    summary = ""
    if rating.get("count"):
        summary = (f'<span class="stars">{_stars(rating["average"])}</span> <b>{rating["average"]:.1f}</b> '
                   f'<span class="muted">({rating["count"]} Bewertung{"en" if rating["count"] != 1 else ""})</span>')
    header = f"""<div class="section"><div class="row">{_icon(app, big=True)}<div>
<h1 style="margin:0;font-size:28px">{e(app['name'])}</h1><div class="muted">{e(app['owner'])} · Version
{e(_version(rel['tag']))}</div><div style="margin-top:4px">{summary}</div><div style="margin-top:6px">{badges}</div>
</div></div><div style="margin-top:14px">{''.join(buttons)}</div>
<p class="muted" style="margin:6px 0 0">Kein „Öffnen“? Dann <a href="{e(deep)}">hier tippen</a> oder zuerst ByteDroide
installieren.</p></div>"""
    shots = ""
    if app.get("screenshots"):
        shots = ('<div class="section"><h2>Screenshots</h2><div class="shots">' + "".join(
            f'<a href="{e(u)}"><img src="{e(u)}" alt="Screenshot {i + 1}" loading="lazy"></a>'
            for i, u in enumerate(app["screenshots"])) + "</div></div>")
    description = (f'<div class="section"><h2>Beschreibung</h2><pre class="notes">{e(app["description"])}</pre></div>'
                   if app.get("description") else "")
    notes = (f'<div class="section"><h2>Neu in {e(_version(rel["tag"]))}</h2><pre class="notes">{e(rel["notes"])}</pre></div>'
             if (rel.get("notes") or "").strip() else "")
    review_html = ""
    if rating.get("count"):
        total = max(rating["count"], 1)
        bars = "".join(f'<div>{5 - i} ★ <span class="bar"><i style="width:{n * 100 // total}%"></i></span> {n}</div>'
                       for i, n in enumerate(rating["distribution"]))
        items = []
        for r in rating["reviews"][:50]:
            when = time.strftime("%d.%m.%Y", time.localtime(r["updated_at"]))
            reply = (f'<div class="reply"><b>Antwort des Entwicklers:</b> {e(r["reply"])}</div>' if r.get("reply") else "")
            text = f'<div>{e(r["text"])}</div>' if r["text"] else ""
            items.append(f'<div class="review"><span class="stars">{_stars(r["rating"])}</span> <b>{e(r["username"])}</b>'
                         f' <span class="muted">· {when} · Version {e(_version(r["version"]))}</span>{text}{reply}</div>')
        review_html = (f'<div class="section"><h2>Bewertungen</h2><div class="row" style="align-items:flex-start;gap:24px;'
                       f'flex-wrap:wrap"><div><div style="font-size:42px;font-weight:800">{rating["average"]:.1f}</div>'
                       f'<div class="stars">{_stars(rating["average"])}</div><div class="muted">{rating["count"]} '
                       f'Bewertungen</div></div><div class="bars" style="flex:1;min-width:200px">{bars}</div></div>'
                       f'{"".join(items)}<p class="muted">Bewerten kannst du in der ByteDroide-App, nachdem du die App '
                       f'installiert hast.</p></div>')
    side = f"""<div class="section qrbox"><h2>Auf dem Handy öffnen</h2>{qrcode_svg.svg(page_url, module=5)}
<p class="muted">QR-Code mit der Kamera scannen – die Seite öffnet sich direkt in ByteDroide.</p>
<a href="{e(page_url)}/qr.svg" download>QR-Code herunterladen</a></div>
<div class="section"><h2>Infos</h2><div class="muted">Entwickler</div><div>{e(app['owner'])}</div>
<div class="muted" style="margin-top:8px">Version</div><div>{e(_version(rel['tag']))}</div>
<div class="muted" style="margin-top:8px">Größe</div><div>{_size(app)}</div>
{f'<div class="muted" style="margin-top:8px">Webseite</div><div><a href="{e(app["homepage"])}" rel="nofollow noopener">{e(app["homepage"])}</a></div>' if app.get("homepage") else ''}
{f'<div class="muted" style="margin-top:8px">Quellcode</div><div><a href="{e(app["html_url"])}" rel="nofollow noopener">ansehen</a></div>' if app.get("html_url") and app.get("html_url") != app.get("homepage") else ''}
</div>"""
    body = f'<div class="layout"><div>{header}{shots}{description}{notes}{review_html}</div><div>{side}</div></div>'
    return _layout(config, f"{app['name']} – ByteDroide", body, description=(app.get("description") or "")[:160])


def _size(app) -> str:
    size = (app.get("apks") or [{}])[0].get("size") or 0
    return f"{size / 1048576:.1f} MB".replace(".", ",") if size >= 1048576 else f"{max(size // 1024, 1)} KB"
