/* ByteDroide Web-Store: Anmeldestatus und Aktionen auf App-Seiten (Kaufen, Code, Beta, Bewerten, Kontakt). */
"use strict";
(function () {
  let token = null;
  try { token = localStorage.getItem("bd_token"); } catch (e) {}

  function h(tag, attrs, ...kids) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
      else if (k === "value") el.value = v;
      else el.setAttribute(k, v === true ? "" : v);
    }
    for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false)
      el.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
    return el;
  }
  function toast(msg) {
    const t = h("div", { class: "toast" }, msg); document.body.append(t); setTimeout(() => t.remove(), 4500);
  }
  async function api(method, path, body) {
    const opt = { method, headers: {} };
    if (token) opt.headers.Authorization = "Bearer " + token;
    if (body !== undefined) { opt.body = JSON.stringify(body); opt.headers["Content-Type"] = "application/json"; }
    const r = await fetch(path, opt);
    const data = await r.json().catch(() => ({}));
    if (r.status === 401 && token) { try { localStorage.removeItem("bd_token"); } catch (e) {} token = null; }
    if (!r.ok) throw new Error(data.error || ("Fehler " + r.status));
    return data;
  }
  async function run(fn) { try { await fn(); } catch (e) { toast(e.message); } }
  const enc = id => id.split("/").map(encodeURIComponent).join("/");
  const ver = t => (t || "").replace(/^[vV](?=\d)/, "");
  const stars = n => "★".repeat(Math.round(n)) + "☆".repeat(5 - Math.round(n));
  const day = ts => new Date(ts * 1000).toLocaleDateString("de-DE");
  function loginLink(text) {
    return h("a", { class: "btn outline small", href: "/konto#/login", onclick: () => sessionStorage.setItem("bd_return", location.href) }, text);
  }
  function modal(title, content, actions) {
    const box = h("div", { class: "box" }, h("h2", { style: "margin-top:0" }, title), content,
      h("div", { style: "margin-top:16px;display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap" }, actions));
    const m = h("div", { class: "modal", onclick: ev => { if (ev.target === m) m.remove(); } }, box);
    document.body.append(m);
    return m;
  }

  // --- Lightbox für Screenshots ------------------------------------------------
  document.addEventListener("click", ev => {
    const img = ev.target.closest && ev.target.closest("img[data-lightbox]");
    if (!img) return;
    const lb = h("div", { class: "lightbox", onclick: () => lb.remove() }, h("img", { src: img.src, alt: img.alt }));
    document.body.append(lb);
  });

  // --- Kopfzeile: Konto -------------------------------------------------------
  const link = document.getElementById("account-link");
  let me = null;
  async function init() {
    if (token) {
      try { me = (await api("GET", "/api/me")).user; } catch (e) { me = null; }
    }
    if (link && me) { link.textContent = me.username; link.href = "/konto#/konto"; }
    const appId = document.body.dataset.appId;
    if (appId) await appPage(appId);
  }

  // --- App-Seite ----------------------------------------------------------------
  async function appPage(id) {
    const actions = document.getElementById("actions");
    const contact = document.getElementById("contact");
    if (!me) {
      actions.replaceChildren(h("p", { class: "muted", style: "margin:12px 0 0" },
        "Melde dich an, um Apps zu kaufen, Codes einzulösen, Betas zu testen und zu bewerten. ", loginLink("Anmelden")));
      return;
    }
    let app;
    try { app = await api("GET", "/api/apps/" + enc(id)); } catch (e) { return; }
    const box = [];
    if (app.unlocked) {
      box.push(h("button", { class: "btn primary", onclick: () => download(app) }, "APK herunterladen" + (app.release.channel === "beta" ? " (Beta)" : "")));
    } else if (app.price) {
      box.push(h("button", { class: "btn primary", onclick: () => buy(app) }, "Kaufen für " + app.price));
      box.push(h("button", { class: "btn outline", onclick: () => redeem(app) }, "Gutschein einlösen"));
    } else {
      box.push(h("button", { class: "btn primary", onclick: () => redeem(app) }, "🔒 Freischalt-Code einlösen"));
    }
    if (app.beta.mode !== "off" && (app.beta.available || app.beta.joined)) {
      if (app.beta.joined) box.push(h("button", { class: "btn outline", onclick: () => beta(app, false) }, "Beta verlassen"));
      else if (app.beta.mode === "open") box.push(h("button", { class: "btn outline", onclick: () => beta(app, true) }, "Beta-Tester werden" + (app.beta.version ? " (" + ver(app.beta.version) + ")" : "")));
    }
    if (app.can_manage) box.push(h("a", { class: "btn outline", href: "/konto#/entwickler/app/" + app.id }, "App verwalten"));
    actions.replaceChildren(h("div", { style: "margin-top:14px;padding-top:14px;border-top:1px solid var(--border)" },
      h("div", { class: "muted", style: "margin-bottom:6px" }, "Angemeldet als " + me.username +
        (app.unlocked && !app.can_manage && (app.price || app.access === "code") ? " · für dein Konto freigeschaltet ✓" : "") +
        (app.beta.joined ? " · Beta-Tester" : "")), box,
      h("p", { class: "muted", style: "margin:8px 0 0" }, "Für automatische Updates die App über ByteDroide auf dem Handy installieren.")));

    // Kontakt zum Entwickler
    if (contact && !app.can_manage) {
      contact.replaceChildren(h("h2", {}, "Fehler gefunden oder Feedback?"),
        h("p", { class: "muted" }, "Schreib dem Entwickler direkt – er bekommt eine Benachrichtigung und kann dir antworten."),
        h("button", { class: "btn outline small", onclick: () => contactDev(app, "bug") }, "🐞 Fehler melden"),
        h("button", { class: "btn outline small", onclick: () => contactDev(app, "feedback") }, "💡 Feedback geben"),
        h("button", { class: "btn outline small", onclick: () => contactDev(app, "question") }, "❓ Frage stellen"));
    } else if (contact) contact.remove();
    await reviews(app);
  }

  async function download(app) {
    await run(async () => {
      toast("Download startet …");
      const r = await fetch(`/api/apps/${enc(app.id)}/download`, { headers: { Authorization: "Bearer " + token } });
      if (!r.ok) { const d = await r.json().catch(() => ({})); throw new Error(d.error || "Download fehlgeschlagen"); }
      const blob = await r.blob();
      const name = (r.headers.get("Content-Disposition") || "").match(/filename="([^"]+)"/);
      const a = h("a", { href: URL.createObjectURL(blob), download: name ? name[1] : "app.apk" });
      document.body.append(a); a.click(); a.remove();
    });
  }

  function buy(app) {
    if (!app.can_buy) { toast("Kauf ist noch nicht eingerichtet – frag den Entwickler nach einem Gutschein-Code."); return redeem(app); }
    const consent = h("input", { type: "checkbox", style: "width:auto;margin:4px 10px 0 0" });
    const btn = h("button", { class: "btn primary", disabled: true, onclick: () => run(async () => {
      const r = await api("POST", `/api/apps/${enc(app.id)}/purchase`, { accept_waiver: true }); location.href = r.checkout_url; }) }, "Zahlungspflichtig kaufen");
    consent.addEventListener("change", () => btn.disabled = !consent.checked);
    const m = modal(app.name + " kaufen", h("div", {},
      h("p", {}, `Preis: ${app.price} – einmalig, inklusive aller Updates. Bezahlt wird sicher über Stripe.`),
      h("label", { style: "display:flex;color:var(--text)" }, consent, h("span", {}, "Ich stimme ausdrücklich zu, dass vor Ablauf der Widerrufsfrist mit der Ausführung des Vertrags begonnen wird (sofortige Freischaltung). Mir ist bekannt, dass ich dadurch mein Widerrufsrecht verliere.")),
      h("p", { class: "muted" }, h("a", { href: "/widerruf", target: "_blank" }, "Widerrufsbelehrung"), " · ", h("a", { href: "/agb", target: "_blank" }, "AGB"))),
      [h("button", { class: "btn outline", onclick: () => m.remove() }, "Abbrechen"), btn]);
  }

  function redeem(app) {
    const code = h("input", { placeholder: "XXXX-XXXX", style: "font-family:monospace;text-transform:uppercase" });
    const m = modal(app.price ? "Gutschein einlösen" : "Freischalt-Code einlösen", h("div", {},
      h("p", {}, app.price ? `Du hast einen Gutschein-Code für „${app.name}“?` : `„${app.name}“ ist nur mit Code verfügbar. Den Code bekommst du vom Entwickler.`), code),
      [h("button", { class: "btn outline", onclick: () => m.remove() }, "Abbrechen"),
       h("button", { class: "btn primary", onclick: () => run(async () => {
         const r = await api("POST", "/api/redeem", { code: code.value }); m.remove(); toast(r.name + " ist jetzt freigeschaltet 🎉"); appPage(app.id); }) }, "Einlösen")]);
    code.focus();
  }

  function beta(app, join) {
    run(async () => { await api(join ? "POST" : "DELETE", `/api/apps/${enc(app.id)}/beta`, join ? {} : undefined);
      toast(join ? "Du bist jetzt Beta-Tester 🧪" : "Beta verlassen"); appPage(app.id); });
  }

  function contactDev(app, kind) {
    const labels = { bug: "Fehler melden", feedback: "Feedback geben", question: "Frage stellen" };
    const kindSel = h("select", {}, Object.entries(labels).map(([k, l]) => h("option", { value: k, selected: k === kind }, l)));
    const subject = h("input", { maxlength: "120", placeholder: "Kurz zusammengefasst" });
    const body = h("textarea", { placeholder: kind === "bug" ? "Was hast du gemacht? Was ist passiert? Was hättest du erwartet?" : "Deine Nachricht" });
    const device = h("input", { placeholder: "z. B. Pixel 7, Android 14 (optional)" });
    const m = modal("Nachricht an den Entwickler von " + app.name, h("div", {},
      h("label", {}, "Art"), kindSel, h("label", {}, "Betreff"), subject, h("label", {}, "Nachricht"), body,
      h("label", {}, "Gerät & Android-Version (hilft bei Fehlern)"), device),
      [h("button", { class: "btn outline", onclick: () => m.remove() }, "Abbrechen"),
       h("button", { class: "btn primary", onclick: () => run(async () => {
         const t = await api("POST", `/api/apps/${enc(app.id)}/threads`, { kind: kindSel.value, subject: subject.value, message: body.value,
           device: device.value ? device.value + " · über Web, installierte Version unbekannt" : "" });
         m.remove(); toast("Gesendet! Antworten findest du unter Mein Konto → Nachrichten.");
         setTimeout(() => location.href = "/konto#/nachrichten/" + t.id, 1200); }) }, "Senden")]);
    subject.focus();
  }

  // --- Bewertungen (interaktiv) -----------------------------------------------------
  async function reviews(app) {
    const sec = document.getElementById("reviews");
    let data;
    try { data = await api("GET", `/api/apps/${enc(app.id)}/reviews`); } catch (e) { return; }
    const nodes = [h("h2", {}, "Bewertungen")];
    if (data.count) {
      const bars = data.distribution.map((n, i) => h("div", {}, `${5 - i} ★ `, h("span", { class: "bar" }, h("i", { style: `width:${Math.round(n * 100 / data.count)}%` })), " " + n));
      nodes.push(h("div", { class: "row", style: "align-items:flex-start;gap:24px;flex-wrap:wrap" },
        h("div", {}, h("div", { style: "font-size:44px;font-weight:800;line-height:1" }, data.average.toFixed(1)),
          h("div", { class: "stars" }, stars(data.average)), h("div", { class: "muted" }, data.count + " Bewertungen")),
        h("div", { class: "bars", style: "flex:1;min-width:200px" }, bars)));
    } else nodes.push(h("p", { class: "muted" }, "Noch keine Bewertungen."));
    if (data.can_review) nodes.push(reviewForm(app, data.mine));
    else if (!app.can_manage) nodes.push(h("p", { class: "muted" }, "Bewerten kannst du, nachdem du die App über ByteDroide geladen hast."));
    for (const r of data.reviews.slice(0, 50)) {
      const replyBtn = data.can_reply ? h("a", { href: "#", class: "muted", onclick: ev => { ev.preventDefault();
        const text = prompt(`Öffentliche Antwort an ${r.username} (leer = Antwort entfernen):`, r.reply);
        if (text !== null) run(async () => { await api("PUT", `/api/dev/apps/${enc(app.id)}/reviews/${r.user_id}/reply`, { text }); toast("Antwort gespeichert"); reviews(app); }); } },
        r.reply ? "Antwort bearbeiten" : "Antworten") : null;
      const delBtn = me && me.is_admin ? h("a", { href: "#", class: "muted", style: "margin-left:12px", onclick: ev => { ev.preventDefault();
        if (confirm("Bewertung entfernen?")) run(async () => { await api("DELETE", `/api/admin/apps/${enc(app.id)}/reviews/${r.user_id}`); reviews(app); }); } }, "Entfernen") : null;
      nodes.push(h("div", { class: "review" }, h("span", { class: "stars" }, stars(r.rating)), " ", h("b", {}, r.username + (r.mine ? " (du)" : "")),
        h("span", { class: "muted" }, ` · ${day(r.updated_at)} · Version ${ver(r.version)}`),
        r.text ? h("div", {}, r.text) : null,
        r.reply ? h("div", { class: "reply" }, h("b", {}, "Antwort des Entwicklers: "), r.reply) : null,
        replyBtn || delBtn ? h("div", { style: "margin-top:4px" }, replyBtn, delBtn) : null));
    }
    sec.replaceChildren(...nodes);
  }

  function reviewForm(app, mine) {
    let rating = mine ? mine.rating : 0;
    const starsRow = h("div", { style: "font-size:30px;cursor:pointer;color:var(--star);user-select:none" });
    const draw = () => starsRow.replaceChildren(...[1, 2, 3, 4, 5].map(i => h("span", { title: i + " Sterne", onclick: () => { rating = i; draw(); } }, i <= rating ? "★" : "☆")));
    draw();
    const text = h("textarea", { placeholder: "Was gefällt dir, was nicht? (optional)", maxlength: "2000" });
    text.value = mine ? mine.text : "";
    return h("div", { style: "background:var(--chip);border-radius:14px;padding:14px;margin:14px 0" },
      h("b", {}, mine ? "Deine Bewertung bearbeiten" : "App bewerten"), starsRow, text,
      h("div", { style: "margin-top:8px" },
        h("button", { class: "btn primary small", onclick: () => run(async () => {
          if (!rating) throw new Error("Bitte Sterne vergeben");
          await api("PUT", `/api/apps/${enc(app.id)}/reviews`, { rating, text: text.value }); toast("Danke für deine Bewertung!"); reviews(app); }) }, "Veröffentlichen"),
        mine ? h("button", { class: "btn outline small", onclick: () => confirm("Bewertung löschen?") && run(async () => {
          await api("DELETE", `/api/apps/${enc(app.id)}/reviews`); reviews(app); }) }, "Löschen") : null),
      h("div", { class: "muted" }, "Deine Bewertung ist mit deinem Benutzernamen öffentlich sichtbar."));
  }

  init();
})();
