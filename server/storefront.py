"""Web-Auftritt: Startseite, Katalog, App-Seiten (mit QR-Codes) und Kontaktformular.

Die Seiten werden auf dem Server gerendert (schnell, suchmaschinenfreundlich). /static/store.js ergänzt für
angemeldete Nutzer die Aktionen (Kaufen, Code, Beta, Bewerten, Download, Entwickler kontaktieren).
"""

import html
import re
import time
import urllib.parse

import qrcode_svg

CSS = """
:root{--bg:#fff;--surface:#f6f8fc;--card:#fff;--text:#1f1f1f;--muted:#5f6368;--brand:#3D5AFE;--brand2:#1A237E;
--soft:#e8ecff;--border:#e1e3e6;--chip:#f1f3f4;--star:#1f1f1f;--bar:#3D5AFE;--ok:#137333;--err:#d93025;--warn:#b06000;
--shadow:0 1px 3px rgba(60,64,67,.15),0 4px 12px rgba(60,64,67,.12)}
@media (prefers-color-scheme:dark){:root{--bg:#131314;--surface:#1b1c1d;--card:#1e1f20;--text:#e3e3e3;--muted:#a8adb3;
--brand:#8c9eff;--soft:#262c4f;--border:#3c4043;--chip:#2a2b2c;--star:#e3e3e3;--bar:#8c9eff;--ok:#81c995;--err:#f28b82;
--warn:#fdd663;--shadow:0 1px 3px rgba(0,0,0,.5),0 4px 12px rgba(0,0,0,.4)}}
*{box-sizing:border-box}html,body{overflow-x:hidden}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 "Google Sans",Roboto,-apple-system,Segoe UI,Helvetica,Arial,sans-serif}
a{color:var(--brand);text-decoration:none}a:hover{text-decoration:underline}img{max-width:100%}
.in{max-width:1180px;margin:0 auto}
header.site{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--border);padding:0 16px}
header.site .in{display:flex;align-items:center;gap:8px;height:64px}
.logo{display:flex;align-items:center;gap:10px;color:var(--text);font-weight:600;font-size:20px;margin-right:18px;white-space:nowrap}
.logo:hover{text-decoration:none}
.logo .mark{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,var(--brand),var(--brand2));
display:flex;align-items:center;justify-content:center;font-size:19px}
nav.tabs{display:flex;align-self:stretch;gap:4px;overflow-x:auto;scrollbar-width:none}
nav.tabs a{display:flex;align-items:center;padding:0 14px;color:var(--muted);font-weight:500;white-space:nowrap;
border-bottom:3px solid transparent;border-top:3px solid transparent}
nav.tabs a:hover{color:var(--text);text-decoration:none;background:var(--surface)}
nav.tabs a.on{color:var(--brand);border-bottom-color:var(--brand)}
.sp{flex:1}
form.hsearch{display:flex;align-items:center;gap:8px;background:var(--chip);border-radius:999px;padding:0 14px;height:42px;
width:280px;max-width:40vw}
form.hsearch input{border:0;background:transparent;padding:0;height:100%;border-radius:0;min-width:0}
form.hsearch input:focus{outline:none}form.hsearch svg{flex:none;fill:var(--muted)}
a.searchbtn{display:none;width:40px;height:40px;border-radius:50%;align-items:center;justify-content:center}
a.searchbtn svg{fill:var(--muted)}
#account-link{flex:none;padding:8px 16px;border-radius:999px;border:1px solid var(--border);font-weight:500;white-space:nowrap}
#account-link:hover{background:var(--surface);text-decoration:none}
#account-link.avatar{width:36px;height:36px;padding:0;border:0;display:flex;align-items:center;justify-content:center;
background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff;font-weight:700}
@media (max-width:860px){header.site .in{flex-wrap:wrap;height:auto;padding-top:10px;gap:4px}
nav.tabs{order:5;flex-basis:100%;height:46px}form.hsearch{display:none}a.searchbtn{display:flex}.logo{margin-right:0}}
.hero-band{padding:28px 16px 4px}.page-title h1{margin:0 0 4px;font-size:32px;font-weight:500;letter-spacing:-.3px}
.page-title p{margin:0;color:var(--muted)}
main{padding:16px 16px 56px}
.btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;background:transparent;color:var(--brand);
border:1px solid var(--border);border-radius:10px;padding:10px 22px;font:inherit;font-weight:600;margin:4px 8px 4px 0;
cursor:pointer;text-decoration:none}
.btn:hover{text-decoration:none;background:var(--soft)}
.btn.primary{background:var(--brand);border-color:var(--brand);color:#fff}.btn.primary:hover{filter:brightness(1.08)}
@media (prefers-color-scheme:dark){.btn.primary{color:#0b1033}}
.btn.outline{background:transparent}.btn.small{padding:6px 14px;font-size:14px}
.btn.danger{background:var(--err);border-color:var(--err);color:#fff}.btn:disabled{opacity:.55;cursor:default}
.btn.big{min-width:200px;padding:12px 28px}
input,select,textarea{font:inherit;color:var(--text);background:var(--card);border:1px solid var(--border);
border-radius:10px;padding:10px 13px;width:100%}
textarea{min-height:130px;resize:vertical}label{display:block;font-size:14px;color:var(--muted);margin:12px 0 4px}
form.search{display:flex;gap:10px;flex-wrap:wrap;margin:0 0 14px}
form.search input{flex:1;min-width:200px;border-radius:999px;width:auto;background:var(--chip);border-color:transparent}
form.search select{width:auto;border-radius:999px}
form.search button{border:0;border-radius:999px;background:var(--brand);color:#fff;padding:0 24px;font:inherit;
font-weight:600;cursor:pointer}
.chips{display:flex;gap:8px;overflow-x:auto;margin:4px 0 18px;padding-bottom:4px;scrollbar-width:none}
.chips a{padding:7px 16px;border-radius:8px;border:1px solid var(--border);font-size:14px;font-weight:500;color:var(--text);
white-space:nowrap}.chips a:hover{background:var(--surface);text-decoration:none}
.chips a.on{background:var(--soft);border-color:var(--soft);color:var(--brand)}
.icon{width:64px;height:64px;border-radius:22%;flex:none;object-fit:cover;display:flex;align-items:center;
justify-content:center;font-weight:600;font-size:26px;color:#fff;box-shadow:0 0 0 1px rgba(0,0,0,.04)}
img.icon{background:var(--surface)}
.shelf{margin:8px 0 26px}.shelf h2{font-size:21px;font-weight:500;margin:0 0 12px}
.shelf h2 a{color:var(--text);display:inline-flex;align-items:center;gap:10px}
.shelf h2 a:hover{text-decoration:none}.shelf h2 a .arr{color:var(--muted);font-size:20px}
.scroller{display:flex;gap:14px;overflow-x:auto;padding:2px 2px 8px;scroll-snap-type:x proximity;scrollbar-width:thin}
.tile{flex:none;width:140px;color:var(--text);scroll-snap-align:start;border-radius:14px;padding:6px}
.tile:hover{text-decoration:none;background:var(--surface)}
.tile .icon{width:128px;height:128px;font-size:52px;box-shadow:var(--shadow)}
.tile .tname{margin-top:8px;font-size:14px;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;
overflow:hidden}
.tile .tmeta{font-size:13px;color:var(--muted)}
@media (max-width:600px){.tile{width:108px}.tile .icon{width:96px;height:96px;font-size:40px}}
.spots{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(300px,1fr);gap:16px;overflow-x:auto;padding-bottom:8px;
margin:4px 0 26px;scroll-snap-type:x mandatory}
@media (max-width:700px){.spots{grid-auto-columns:86%}}
.spot{display:block;color:var(--text);border-radius:18px;overflow:hidden;background:var(--card);border:1px solid var(--border);
scroll-snap-align:start}
.spot:hover{text-decoration:none;box-shadow:var(--shadow)}
.spot .art{aspect-ratio:16/9;position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center}
.spot .art img.shot{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:top}
.spot .art .icon{width:96px;height:96px;font-size:40px;box-shadow:var(--shadow)}
.spot .art .tag{position:absolute;left:14px;top:12px;background:rgba(0,0,0,.6);color:#fff;font-size:12px;font-weight:600;
padding:3px 10px;border-radius:999px}
.spot .info{display:flex;gap:12px;align-items:center;padding:12px 14px}
.spot .info .icon{width:48px;height:48px;font-size:20px}.spot .info .t{flex:1;min-width:0}
.spot .info .n{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.spot .info .btn{margin:0;padding:6px 16px;font-size:14px}
.charts{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(320px,100%),1fr));gap:4px 18px}
.list-item{display:flex;gap:14px;align-items:center;padding:8px;border-radius:12px;color:var(--text);min-width:0}
.list-item:hover{background:var(--surface);text-decoration:none}
.list-item .rank{width:20px;text-align:center;color:var(--muted);font-weight:500;flex:none}
.list-item .t{min-width:0;flex:1}.list-item .n{font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.muted{color:var(--muted);font-size:14px}.row{display:flex;gap:14px;align-items:center}.small{font-size:13px}
.results{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(320px,100%),1fr));gap:6px 18px}
.results .icon{width:72px;height:72px}
.badge{display:inline-block;font-size:12px;font-weight:600;padding:2px 9px;border-radius:6px;background:var(--chip);
color:var(--muted);margin:2px 4px 2px 0}
.stars{color:var(--star)}
.apphead{display:grid;grid-template-columns:minmax(0,1fr) 220px;grid-template-areas:"title icon" "body icon";gap:0 40px;
padding:20px 0 8px}
.apphead .ah-icon{grid-area:icon;width:220px;height:220px;font-size:90px;border-radius:22%;box-shadow:var(--shadow);
justify-self:end}
.apphead .ah-title{grid-area:title;min-width:0}.apphead .ah-body{grid-area:body;min-width:0}
.apphead h1{margin:0;font-size:46px;line-height:1.1;font-weight:500;letter-spacing:-.5px;overflow-wrap:anywhere}
.apphead .dev{display:inline-block;margin-top:10px;font-size:17px;font-weight:600}
.apphead .sub{color:var(--muted);font-size:13px;margin-top:2px}
.statsrow{display:flex;margin:22px 0 18px;overflow-x:auto}
.statsrow div{padding:0 22px;text-align:center;border-left:1px solid var(--border);white-space:nowrap;flex:none}
.statsrow div:first-child{padding-left:0;border-left:0}
.statsrow b{display:block;font-weight:600;font-size:15px}.statsrow span{font-size:12px;color:var(--muted)}
@media (max-width:760px){.apphead{grid-template-columns:72px minmax(0,1fr);grid-template-areas:"icon title" "body body";gap:0 16px}
.apphead .ah-icon{width:72px;height:72px;font-size:30px;justify-self:start}.apphead h1{font-size:26px}
.apphead .dev{margin-top:4px;font-size:15px}.statsrow div{padding:0 14px}.ah-actions .btn.big{flex:1;min-width:0}}
.ah-actions{display:flex;flex-wrap:wrap;align-items:center}
.layout{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:40px;align-items:start}
@media (max-width:960px){.layout{grid-template-columns:minmax(0,1fr);gap:8px}}
.section{padding:18px 0;border-top:1px solid var(--border);min-width:0}.layout>div>.section:first-child{border-top:0}
.section h2{font-size:20px;font-weight:500;margin:0 0 12px}
.box{background:var(--card);border:1px solid var(--border);border-radius:18px;padding:18px 20px;margin:0 0 16px;min-width:0}
.box h2{font-size:17px;font-weight:600;margin:0 0 10px}
.shots{display:flex;gap:12px;overflow-x:auto;padding-bottom:6px;scroll-snap-type:x mandatory}
.shots img{height:360px;max-width:none;border-radius:14px;border:1px solid var(--border);scroll-snap-align:start;cursor:zoom-in}
@media (max-width:600px){.shots img{height:280px}}
.qrbox{text-align:center}.qrbox svg{width:180px;height:180px;max-width:100%;background:#fff;border-radius:12px;padding:6px}
.review{border-top:1px solid var(--border);padding:14px 0}.review:first-of-type{border-top:0}
.reply{margin:8px 0 0 14px;padding:10px 14px;background:var(--surface);border-radius:10px;font-size:14px}
.bars div{display:flex;align-items:center;gap:10px;font-size:13px;color:var(--muted)}
.bars span.bar{flex:1;height:10px;background:var(--chip);border-radius:99px;overflow:hidden}
.bars span.bar i{display:block;height:100%;background:var(--bar);border-radius:99px}
pre.notes{white-space:pre-wrap;font:inherit;margin:0;overflow-wrap:anywhere}
.info-row{display:flex;gap:12px;padding:8px 0;border-top:1px solid var(--border);font-size:14px}
.info-row:first-of-type{border-top:0}.info-row .k{color:var(--muted);width:42%;flex:none}.info-row .v{min-width:0;overflow-wrap:anywhere}
.features{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.feature{background:var(--surface);border-radius:18px;padding:20px}
.feature .em{font-size:28px}.feature h3{margin:8px 0 6px;font-size:16px;font-weight:600}
.feature p{margin:0;color:var(--muted);font-size:14px}
.promo{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:30px 0}
@media (max-width:800px){.promo{grid-template-columns:1fr}}
.promo>div{border-radius:22px;padding:26px;display:flex;gap:20px;align-items:center;flex-wrap:wrap}
.promo .p1{background:linear-gradient(135deg,var(--brand),var(--brand2));color:#fff}
.promo .p1 .btn{background:#fff;color:var(--brand2);border-color:#fff}
.promo .p2{background:var(--soft)}
.promo h2{margin:0 0 6px;font-size:22px;font-weight:500}.promo p{margin:0 0 12px;opacity:.9}
.promo .qr{background:#fff;border-radius:16px;padding:8px;width:128px;height:128px;flex:none}.promo .qr svg{width:100%;height:100%}
.stat-line{display:flex;gap:26px;flex-wrap:wrap;margin:6px 0 0;color:var(--muted);font-size:14px}.stat-line b{color:var(--text)}
details{border-bottom:1px solid var(--border);padding:14px 4px}
details summary{cursor:pointer;font-weight:500}details p{margin:10px 0 0;color:var(--muted)}
h2.title{font-size:21px;font-weight:500;margin:30px 0 12px;display:flex;align-items:center;gap:12px}
h2.title a{font-size:14px;font-weight:600;margin-left:auto}
.alert{border-radius:12px;padding:12px 16px;margin:0 0 14px}.alert.ok{background:rgba(19,115,51,.12);color:var(--ok)}
.alert.err{background:rgba(217,48,37,.1);color:var(--err)}
.hp{position:absolute;left:-10000px;width:1px;height:1px;overflow:hidden}
#actions:empty{display:none}
.empty{text-align:center;color:var(--muted);padding:40px 0}
footer{padding:28px 16px 40px;color:var(--muted);font-size:14px;border-top:1px solid var(--border);background:var(--surface)}
footer .in{display:flex;gap:24px;flex-wrap:wrap;justify-content:space-between}footer a{color:var(--muted);margin-right:14px}
.toast{position:fixed;left:50%;bottom:24px;transform:translateX(-50%);background:#202124;color:#fff;padding:11px 20px;
border-radius:8px;z-index:20;max-width:92vw}
.modal{position:fixed;inset:0;background:rgba(0,0,0,.55);display:flex;align-items:center;justify-content:center;z-index:15;
padding:16px}.modal .box{background:var(--card);border-radius:22px;padding:22px;max-width:520px;width:100%;
max-height:90vh;overflow:auto}
.lightbox{position:fixed;inset:0;background:rgba(0,0,0,.92);display:flex;align-items:center;justify-content:center;z-index:30}
.lightbox img{max-height:92vh;max-width:96vw;border-radius:10px}
"""

e = html.escape

SEARCH_SVG = ('<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="M15.5 14h-.79l-.28-.27A6.47 '
              '6.47 0 0 0 16 9.5 6.5 6.5 0 1 0 9.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19zm-6 0C7.01 14 5 '
              '11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14"/></svg>')
ICON_COLORS = ("#3D5AFE", "#00897B", "#E53935", "#8E24AA", "#F4511E", "#43A047", "#1E88E5", "#6D4C41", "#D81B60")


def stars(avg: float) -> str:
    full = int(round(avg))
    return "★" * full + "☆" * (5 - full)


def _de(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


def _icon(app, cls="") -> str:
    cls = f"icon {cls}".strip()
    if app.get("avatar_url"):
        return f'<img class="{cls}" src="{e(app["avatar_url"])}" alt="" loading="lazy">'
    color = ICON_COLORS[sum(map(ord, app["id"])) % len(ICON_COLORS)]
    return f'<div class="{cls}" style="background:{color}">{e(app["name"][:1].upper())}</div>'


def _version(tag: str) -> str:
    m = re.search(r"(?<![0-9A-Za-z])[vV]?(\d+(?:\.\d+)+\S*)", tag or "")
    if m:
        return m.group(1)
    return tag[1:] if tag[:1] in ("v", "V") and tag[1:2].isdigit() else tag


NAV = (("/", "Entdecken"), ("/apps", "Alle Apps"), ("/apps?sortierung=beliebt", "Top-Charts"), ("/hilfe", "Hilfe"),
       ("/hilfe/entwickler", "Für Entwickler"), ("/kontakt", "Kontakt"))


def layout(config, title: str, body: str, hero: str = "", description: str = "", active: str = "",
           body_attrs: str = "") -> str:
    base = e(config.public_url)
    desc = e(description or "ByteDroide – der App-Store für unabhängige Android-Apps. Ohne Google, mit Betas, "
                            "Bewertungen und automatischen Updates.")
    nav = "".join(f'<a href="{base}{e(href)}" class="{"on" if active == href else ""}">{label}</a>' for href, label in NAV)
    hero_html = f'<div class="hero-band"><div class="in">{hero}</div></div>' if hero else ""
    return f"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{e(title)}</title>
<meta name="description" content="{desc}"><meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{desc}"><meta property="og:site_name" content="ByteDroide">
<meta name="theme-color" content="#ffffff">
<link rel="icon" href="/favicon.ico" type="image/svg+xml"><style>{CSS}</style></head><body {body_attrs}>
<header class="site"><div class="in"><a class="logo" href="{base}/"><span class="mark">&#129302;</span>ByteDroide</a>
<nav class="tabs">{nav}</nav><span class="sp"></span>
<form class="hsearch" action="{base}/apps" role="search">{SEARCH_SVG}<input name="q" placeholder="Apps suchen"
aria-label="Apps suchen"></form><a class="searchbtn" href="{base}/apps" aria-label="Suchen">{SEARCH_SVG}</a>
<a id="account-link" href="{base}/konto#/login">Anmelden</a></div></header>
{hero_html}<main><div class="in">{body}</div></main>
<footer><div class="in"><div><b>&#129302; ByteDroide</b><br>Der App-Store für unabhängige Android-Apps.</div>
<div><a href="{base}/apps">Apps</a><a href="{base}/hilfe">Hilfe &amp; Doku</a><a href="{base}/kontakt">Kontakt</a>
<a href="{base}/konto">Mein Konto</a><br><a href="{base}/impressum">Impressum</a><a href="{base}/datenschutz">Datenschutz</a>
<a href="{base}/agb">Nutzungsbedingungen</a><a href="{base}/widerruf">Widerruf</a></div></div></footer>
<script src="/static/store.js" defer></script></body></html>"""


# ---------------------------------------------------------------------------
# Kacheln & Listen
# ---------------------------------------------------------------------------

def _price_label(a) -> str:
    if a.get("price"):
        return a["price"]
    return "🔒 Code" if a.get("access") == "code" else "Kostenlos"


def _rating_short(a) -> str:
    r = a.get("rating") or {}
    return f'{_de(r["average"])} ★' if r.get("count") else ""


def _tile(base, a) -> str:
    meta = _rating_short(a) or e(a.get("category") or "")
    if a.get("price"):
        meta = (meta + " · " if meta else "") + e(a["price"])
    return (f'<a class="tile" href="{e(base)}/app/{e(a["id"])}">{_icon(a)}<div class="tname">{e(a["name"])}</div>'
            f'<div class="tmeta">{meta or "&nbsp;"}</div></a>')


def _shelf(base, title, apps, href="") -> str:
    if not apps:
        return ""
    head = (f'<a href="{e(base)}{e(href)}">{e(title)} <span class="arr">→</span></a>' if href else e(title))
    return f'<section class="shelf"><h2>{head}</h2><div class="scroller">{"".join(_tile(base, a) for a in apps)}</div></section>'


def _list_item(base, a, rank=None) -> str:
    bits = [e(a.get("category") or a["owner"])]
    if _rating_short(a):
        bits.append(_rating_short(a))
    if (a.get("downloads") or 0) > 0:
        bits.append(e(a.get("downloads_label") or "") + " Downloads")
    meta = " · ".join(b for b in bits if b)
    rank_html = f'<span class="rank">{rank}</span>' if rank else ""
    return (f'<a class="list-item" href="{e(base)}/app/{e(a["id"])}">{rank_html}{_icon(a)}<div class="t">'
            f'<div class="n">{e(a["name"])}</div><div class="muted small">{e(a["owner"])}</div>'
            f'<div class="muted small">{meta} · {e(_price_label(a))}</div></div></a>')


def _spot(base, a, label) -> str:
    shots = a.get("screenshots") or []
    if shots:
        art = f'<img class="shot" src="{e(shots[0])}" alt="" loading="lazy">'
        style = ""
    else:
        art = _icon(a)
        color = ICON_COLORS[sum(map(ord, a["id"])) % len(ICON_COLORS)]
        style = f' style="background:linear-gradient(135deg,{color}33,{color}88)"'
    rating = _rating_short(a)
    return (f'<a class="spot" href="{e(base)}/app/{e(a["id"])}"><div class="art"{style}>{art}'
            f'<span class="tag">{e(label)}</span></div><div class="info">{_icon(a)}<div class="t">'
            f'<div class="n">{e(a["name"])}</div><div class="muted small">{e(a["owner"])}'
            f'{" · " + rating if rating else ""}</div></div><span class="btn primary">Ansehen</span></div></a>')


def _published(a) -> str:
    return a["release"].get("published_at") or ""


def _popularity(a):
    r = a.get("rating") or {}
    return (r.get("average", 0) * min(r.get("count", 0), 20) + min(a.get("downloads") or 0, 1000) / 50,
            r.get("count", 0), a.get("downloads") or 0)


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


def _categories(apps) -> dict:
    cats = {}
    for a in apps:
        if a.get("category"):
            cats.setdefault(a["category"], []).append(a)
    return cats


def home(config, apps: list, stats: dict) -> str:
    base = config.public_url
    cats = _categories(apps)
    chips = "".join(f'<a href="{e(base)}/apps?{urllib.parse.urlencode({"kategorie": c})}">{e(c)}</a>'
                    for c in sorted(cats))
    chips = (f'<div class="chips"><a class="on" href="{e(base)}/">Für dich</a>'
             f'<a href="{e(base)}/apps?sortierung=beliebt">Top-Charts</a>'
             f'<a href="{e(base)}/apps?sortierung=neu">Neu</a>{chips}</div>')
    popular = sorted(apps, key=_popularity, reverse=True)
    newest = sorted(apps, key=_published, reverse=True)
    featured = sorted(apps, key=lambda a: (bool(a.get("screenshots")), _popularity(a)), reverse=True)[:3]
    spots = "".join(_spot(base, a, "Empfohlen" if i == 0 else ("Beliebt" if i == 1 else "Entdecken"))
                    for i, a in enumerate(featured))
    shelves = [_shelf(base, "Neu im Store", newest[:15], "/apps?sortierung=neu")]
    if any((a.get("rating") or {}).get("count") or a.get("downloads") for a in apps):
        shelves.append(_shelf(base, "Beliebt", popular[:15], "/apps?sortierung=beliebt"))
    for cat, items in sorted(((c, i) for c, i in cats.items() if len(i) >= 3), key=lambda kv: -len(kv[1]))[:4]:
        shelves.append(_shelf(base, cat, sorted(items, key=_popularity, reverse=True)[:15],
                              "/apps?" + urllib.parse.urlencode({"kategorie": cat})))
    charts = "".join(_list_item(base, a, i + 1) for i, a in enumerate(popular[:9]))
    qr = ""
    if config.store_app_id:
        qr = f'<div class="qr" title="Mit dem Handy scannen">{qrcode_svg.svg(base + "/download", module=4)}</div>'
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
    empty = '<div class="empty">Noch keine Apps im Store.</div>' if not apps else ""
    body = f"""{chips}{empty}{f'<div class="spots">{spots}</div>' if spots else ''}
{''.join(shelves)}
{f'<section class="shelf"><h2><a href="{e(base)}/apps?sortierung=beliebt">Top-Charts <span class="arr">→</span></a></h2><div class="charts">{charts}</div></section>' if charts else ''}
<div class="promo"><div class="p1">{qr}<div style="flex:1;min-width:220px"><h2>ByteDroide für Android</h2>
<p>Installieren, automatisch aktualisieren, Betas testen – alles in einer App.</p>
{f'<a class="btn" href="{e(base)}/download">App herunterladen</a>' if config.store_app_id else ''}
<div class="stat-line" style="color:rgba(255,255,255,.85)"><span><b style="color:#fff">{len(apps)}</b> Apps</span>
<span><b style="color:#fff">{stats.get("developers", 0)}</b> Entwickler</span>
<span><b style="color:#fff">{stats.get("downloads", 0)}</b> Downloads</span></div></div></div>
<div class="p2"><div style="flex:1;min-width:220px"><h2>Du entwickelst Android-Apps?</h2>
<p>Veröffentliche sie per Upload, direkt aus GitHub oder Forgejo oder automatisch aus deiner CI – mit Betas,
gestaffelten Rollouts, Freischalt-Codes, Verkauf und Statistiken.</p>
<a class="btn primary" href="{e(base)}/konto#/login?entwickler=1">Entwickler werden</a>
<a class="btn" href="{e(base)}/hilfe/entwickler">Dokumentation</a></div></div></div>
<h2 class="title">Warum ByteDroide?</h2><div class="features">{feat_html}</div>
<h2 class="title">Häufige Fragen <a href="{e(base)}/hilfe">Zur Hilfe →</a></h2>{faq_html}"""
    return layout(config, "ByteDroide – Apps unabhängiger Entwickler", body, active="/")


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
    chips = f'<div class="chips"><a class="{"" if category else "on"}" href="{e(link(kategorie=""))}">Alle</a>{chips}</div>'
    options = "".join(f'<option value="{k}"{" selected" if k == sort else ""}>{v}</option>' for k, v in SORTS.items())
    title = "Top-Charts" if sort == "beliebt" and not q and not category else (category or "Alle Apps")
    if q:
        title = f"Ergebnisse für „{query.strip()}“"
    hero = (f'<div class="page-title"><h1>{e(title)}</h1><p>{len(shown)} von {len(apps)} Apps</p></div>')
    if shown:
        items = "".join(_list_item(base, a, i + 1 if sort == "beliebt" else None) for i, a in enumerate(shown))
        results = f'<div class="results">{items}</div>'
    else:
        results = '<div class="empty">Keine Apps gefunden.</div>'
    body = f"""<form class="search" method="get"><input name="q" value="{e(query)}" placeholder="Apps durchsuchen"
aria-label="Apps durchsuchen">{f'<input type="hidden" name="kategorie" value="{e(category)}">' if category else ''}
<select name="sortierung" aria-label="Sortierung">{options}</select><button type="submit">Suchen</button></form>
{chips}{results}"""
    active = "/apps?sortierung=beliebt" if sort == "beliebt" else "/apps"
    return layout(config, f"{title} – ByteDroide", body, hero, active=active)


# ---------------------------------------------------------------------------
# App-Seite
# ---------------------------------------------------------------------------

def app_page(config, app: dict, reviews: dict, similar: list = ()) -> str:
    base = config.public_url
    page_url = f"{base}/app/{app['id']}"
    rel = app["release"]
    rating = reviews or {}
    free_open = not app.get("price") and app.get("access") == "open"
    install_label = "Installieren" if free_open else ("Kaufen" if app.get("price") else "Ansehen")
    buttons = [f'<a class="btn primary big" href="{e(page_url)}" rel="nofollow">{install_label} in ByteDroide</a>']
    if free_open:
        buttons.append(f'<a class="btn" href="{e(base)}/api/apps/{e(app["id"])}/download">APK direkt laden</a>')
    deep = f'bytedroide://app/{app["id"]}'
    sub = []
    if app.get("category"):
        sub.append(e(app["category"]))
    if app.get("beta", {}).get("available"):
        sub.append("Beta verfügbar")
    if app.get("price"):
        sub.append("Kostenpflichtig")
    elif app.get("access") == "code":
        sub.append("Nur mit Freischalt-Code")
    stats = []
    if rating.get("count"):
        stats.append((f'{_de(rating["average"])} ★',
                      f'{rating["count"]} Bewertung{"en" if rating["count"] != 1 else ""}'))
    else:
        stats.append(("–", "Noch keine Bewertungen"))
    stats.append((e(app.get("downloads_label") or "Neu"), "Downloads"))
    stats.append((_size(app), "Größe"))
    stats.append((e(_price_label(app)), "Preis"))
    stats.append((e(_version(rel["tag"])), "Version"))
    stats_html = "".join(f"<div><b>{v}</b><span>{k}</span></div>" for v, k in stats)
    header = f"""<div class="apphead">{_icon(app, "ah-icon")}
<div class="ah-title"><h1>{e(app['name'])}</h1><a class="dev" href="{e(base)}/apps?{urllib.parse.urlencode({"q": app["owner"]})}">{e(app['owner'])}</a>
<div class="sub">{" · ".join(sub)}</div></div>
<div class="ah-body"><div class="statsrow">{stats_html}</div><div class="ah-actions">{''.join(buttons)}</div>
<p class="muted small" style="margin:6px 0 0">Kein „Öffnen“? Dann <a href="{e(deep)}">hier tippen</a> oder zuerst
{f'<a href="{e(base)}/download">ByteDroide installieren</a>' if config.store_app_id else 'ByteDroide installieren'}.</p>
<div id="actions"></div></div></div>"""
    shots = ""
    if app.get("screenshots"):
        shots = ('<div class="section"><div class="shots">' + "".join(
            f'<img src="{e(u)}" alt="Screenshot {i + 1}" loading="lazy" data-lightbox>'
            for i, u in enumerate(app["screenshots"])) + "</div></div>")
    description = (f'<div class="section"><h2>Über diese App</h2><pre class="notes">{e(app["description"])}</pre>'
                   f'<p class="muted small" style="margin:12px 0 0">Aktualisiert am {e(_date(rel))}</p></div>'
                   if app.get("description") else "")
    notes = (f'<div class="section"><h2>Neuigkeiten in {e(_version(rel["tag"]))}</h2><pre class="notes">{e(rel["notes"])}</pre></div>'
             if (rel.get("notes") or "").strip() else "")
    body = f"""{header}<div class="layout"><div>{shots}{description}{notes}
<div class="section" id="reviews">{reviews_html(rating)}</div>
<div class="section" id="contact"><h2>Fehler gefunden oder Feedback?</h2>
<p class="muted">Schreib dem Entwickler direkt – er bekommt eine Benachrichtigung und kann dir antworten.</p>
<a class="btn small" href="{e(base)}/konto#/login">Anmelden, um zu schreiben</a></div></div>
<div>{_side(base, app, page_url, rel, similar)}</div></div>"""
    attrs = f'data-app-id="{e(app["id"])}"'
    return layout(config, f"{app['name']} – ByteDroide", body, description=(app.get("description") or "")[:160],
                  body_attrs=attrs)


def _date(rel) -> str:
    raw = rel.get("published_at") or ""
    try:
        return time.strftime("%d.%m.%Y", time.strptime(raw[:10], "%Y-%m-%d"))
    except ValueError:
        return raw[:10] or "–"


def reviews_html(rating: dict) -> str:
    if not rating.get("count"):
        return ('<h2>Bewertungen und Rezensionen</h2><p class="muted">Noch keine Bewertungen. Bewerten kann, wer die App über '
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
    return (f'<h2>Bewertungen und Rezensionen</h2><div class="row" style="align-items:flex-start;gap:24px;flex-wrap:wrap"><div>'
            f'<div style="font-size:56px;font-weight:400;line-height:1">{_de(rating["average"])}</div>'
            f'<div class="stars">{stars(rating["average"])}</div><div class="muted">{rating["count"]} Bewertungen</div>'
            f'</div><div class="bars" style="flex:1;min-width:200px">{bars}</div></div>{"".join(items)}')


def _size(app) -> str:
    size = (app.get("apks") or [{}])[0].get("size") or 0
    return f"{size / 1048576:.1f} MB".replace(".", ",") if size >= 1048576 else f"{max(size // 1024, 1)} KB"


def _side(base, app, page_url, rel, similar=()) -> str:
    rows = [("Entwickler", e(app["owner"])), ("Version", e(_version(rel["tag"]))), ("Aktualisiert", e(_date(rel))),
            ("Größe", _size(app)), ("Downloads", e(app.get("downloads_label") or "Neu"))]
    if app.get("category"):
        rows.append(("Kategorie", e(app["category"])))
    if app.get("homepage"):
        rows.append(("Webseite", f'<a href="{e(app["homepage"])}" rel="nofollow noopener">{e(app["homepage"])}</a>'))
    if app.get("html_url") and app.get("html_url") != app.get("homepage"):
        rows.append(("Quellcode", f'<a href="{e(app["html_url"])}" rel="nofollow noopener">ansehen</a>'))
    info = "".join(f'<div class="info-row"><span class="k">{k}</span><span class="v">{v}</span></div>' for k, v in rows)
    similar_html = ""
    if similar:
        similar_html = ('<div class="box"><h2>Ähnliche Apps</h2>' +
                        "".join(_list_item(base, a) for a in similar) + "</div>")
    return f"""<div class="box"><h2>App-Infos</h2>{info}
<p style="margin:12px 0 0" class="small"><a href="{e(base)}/kontakt?thema=meldung">App melden</a></p></div>
{similar_html}<div class="box qrbox"><h2>Auf dem Handy öffnen</h2>{qrcode_svg.svg(page_url, module=5)}
<p class="muted small">QR-Code mit der Kamera scannen – die Seite öffnet sich direkt in ByteDroide.</p>
<a class="small" href="{e(page_url)}/qr.svg" download>QR-Code herunterladen</a></div>"""


# ---------------------------------------------------------------------------
# Kontakt
# ---------------------------------------------------------------------------

def contact_page(config, topics: dict, form=None, error="", sent=False, topic="") -> str:
    base = config.public_url
    form = form or {}
    hero = '<div class="page-title"><h1>Kontakt</h1><p>Fragen, Feedback oder ein Problem? Schreib uns.</p></div>'
    if sent:
        body = ('<div class="box" style="max-width:720px"><div class="alert ok">Danke! Deine Nachricht ist '
                'angekommen. Du bekommst gleich eine Bestätigung per E-Mail.</div><a class="btn primary" '
                f'href="{e(base)}/">Zur Startseite</a></div>')
        return layout(config, "Kontakt – ByteDroide", body, hero, active="/kontakt")
    selected = form.get("topic") or topic
    options = "".join(f'<option value="{k}"{" selected" if k == selected else ""}>{e(v)}</option>'
                      for k, v in topics.items())
    v = lambda k: e(form.get(k, ""))  # noqa: E731
    operator = e(config.operator_email) if config.operator_email else ""
    body = f"""<div class="layout"><div><div class="box">
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
<div><div class="box"><h2>Schneller zum Ziel</h2>
<p><b>Problem mit einer bestimmten App?</b><br><span class="muted">Schreib direkt dem Entwickler – auf der App-Seite unter
„Fehler gefunden oder Feedback?“.</span></p>
<p><b>Hilfe zur Bedienung</b><br><a href="{e(base)}/hilfe">Zur Dokumentation</a></p>
<p><b>Rechtswidrige Inhalte melden</b><br><span class="muted">Bitte Thema „Rechtswidrigen Inhalt melden“ wählen und die
App genau bezeichnen.</span></p>
{f'<p><b>Per E-Mail</b><br><a href="mailto:{operator}">{operator}</a></p>' if operator else ''}
</div></div></div>"""
    return layout(config, "Kontakt – ByteDroide", body, hero, active="/kontakt")
