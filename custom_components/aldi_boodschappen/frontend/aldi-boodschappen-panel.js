/* Aldi Boodschappen - zijbalkpaneel voor Home Assistant (vanilla web component) */

const T = {
  title: "Boodschappen",
  searchPlaceholder: "Zoek in het Aldi-assortiment, bijv. kwark…",
  searching: "Zoeken…",
  noResults: "Geen Aldi-producten gevonden.",
  addPlain: "Voeg toe als losse tekst",
  add: "Toevoegen",
  everyWeek: "Elke week",
  list: "Mijn lijst",
  empty: "Je lijst is leeg. Zoek hierboven een product.",
  newWeek: "Nieuwe week starten",
  newWeekConfirm:
    "Afgevinkte eenmalige producten worden verwijderd en terugkerende producten worden weer op 'te halen' gezet. Doorgaan?",
  remove: "Verwijderen",
  error: "Zoeken mislukt",
  toBuy: "Te halen",
  done: "Gehaald",
  recurring: "Terugkerend",
};

const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const money = (v, cur = "€") =>
  v === null || v === undefined ? "" : `${cur} ${Number(v).toFixed(2).replace(".", ",")}`;

class AldiBoodschappenPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._items = [];
    this._results = [];
    this._query = "";
    this._status = ""; // "", "loading", "error:..."
    this._unsub = null;
    this._timer = null;
    this._searchSeq = 0;
    this._rendered = false;
    this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._connect();
  }

  set narrow(v) { this._narrow = v; }
  set panel(v) { this._panel = v; }
  set route(v) { this._route = v; }

  connectedCallback() {
    this._render();
    if (this._hass && !this._unsub) this._connect();
  }

  disconnectedCallback() {
    if (this._unsub) {
      this._unsub.then?.((u) => u());
      this._unsub = null;
    }
  }

  async _connect() {
    if (this._unsub) return;
    this._unsub = this._hass.connection.subscribeMessage(
      (msg) => {
        this._items = msg.items || [];
        this._renderList();
      },
      { type: "aldi_boodschappen/subscribe" }
    );
  }

  _ws(msg) {
    return this._hass.callWS(msg);
  }

  /* ---------- rendering ---------- */

  _render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display:block; height:100%; overflow:auto; background:var(--primary-background-color); color:var(--primary-text-color); font-family:var(--paper-font-body1_-_font-family, Roboto, sans-serif); }
        header { display:flex; align-items:center; gap:12px; padding:12px 16px; background:var(--app-header-background-color, var(--primary-color)); color:var(--app-header-text-color, #fff); position:sticky; top:0; z-index:2; }
        header h1 { font-size:20px; font-weight:400; margin:0; flex:1; }
        header button { background:transparent; border:1px solid currentColor; color:inherit; border-radius:18px; padding:6px 14px; cursor:pointer; font-size:13px; }
        main { max-width:1100px; margin:0 auto; padding:16px; }
        .search { display:flex; gap:8px; }
        .search input { flex:1; font-size:16px; padding:12px 14px; border-radius:10px; border:1px solid var(--divider-color); background:var(--card-background-color); color:var(--primary-text-color); outline:none; }
        .search input:focus { border-color:var(--primary-color); }
        .hint { margin:12px 2px; color:var(--secondary-text-color); font-size:14px; }
        .hint button { background:none; border:none; color:var(--primary-color); cursor:pointer; padding:0; font-size:14px; text-decoration:underline; }
        .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:12px; margin:12px 0 24px; }
        .card { background:var(--card-background-color); border-radius:12px; box-shadow:var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.2)); display:flex; flex-direction:column; overflow:hidden; }
        .card .img { height:90px; background:var(--secondary-background-color) center/contain no-repeat; display:flex; align-items:center; justify-content:center; font-size:34px; }
        .card .body { padding:10px; display:flex; flex-direction:column; gap:4px; flex:1; }
        .card .name { font-size:14px; font-weight:500; line-height:1.25; }
        .card .meta { font-size:12px; color:var(--secondary-text-color); }
        .card .price { font-weight:600; }
        .card .old { text-decoration:line-through; color:var(--secondary-text-color); font-size:12px; margin-left:6px; }
        .card .actions { margin-top:auto; display:flex; flex-direction:column; gap:6px; padding-top:6px; }
        label.chk { display:flex; align-items:center; gap:6px; font-size:13px; cursor:pointer; }
        .btn { background:var(--primary-color); color:var(--text-primary-color,#fff); border:none; border-radius:8px; padding:8px; cursor:pointer; font-size:14px; }
        h2 { font-size:16px; font-weight:500; margin:24px 0 8px; }
        .list { background:var(--card-background-color); border-radius:12px; overflow:hidden; box-shadow:var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.2)); }
        .row { display:flex; align-items:center; gap:10px; padding:10px 12px; border-bottom:1px solid var(--divider-color); }
        .row:last-child { border-bottom:none; }
        .row img { width:44px; height:44px; object-fit:contain; background:#fff; border-radius:6px; }
        .row .ph { width:44px; height:44px; display:flex; align-items:center; justify-content:center; border-radius:6px; background:var(--secondary-background-color); font-size:20px; }
        .row .info { flex:1; min-width:0; }
        .row .nm { font-size:15px; overflow:hidden; text-overflow:ellipsis; }
        .row.done .nm { text-decoration:line-through; color:var(--secondary-text-color); }
        .row .sub { font-size:12px; color:var(--secondary-text-color); }
        .row input[type=checkbox] { width:20px; height:20px; cursor:pointer; }
        .qty { display:flex; align-items:center; gap:4px; }
        .qty button, .icon { background:var(--secondary-background-color); color:var(--primary-text-color); border:none; border-radius:50%; width:28px; height:28px; cursor:pointer; font-size:16px; line-height:1; }
        .tag { cursor:pointer; user-select:none; font-size:12px; padding:4px 8px; border-radius:12px; border:1px solid var(--divider-color); color:var(--secondary-text-color); white-space:nowrap; }
        .tag.on { background:var(--primary-color); border-color:var(--primary-color); color:var(--text-primary-color,#fff); }
        .empty { padding:24px; text-align:center; color:var(--secondary-text-color); }
        a { color:inherit; }
      </style>
      <header>
        <h1>${T.title}</h1>
        <button id="newweek">${T.newWeek}</button>
      </header>
      <main>
        <div class="search"><input id="q" type="search" autocomplete="off" placeholder="${escapeHtml(T.searchPlaceholder)}" /></div>
        <div id="status" class="hint"></div>
        <div id="results" class="grid"></div>
        <h2>${T.list}</h2>
        <div id="list" class="list"></div>
      </main>`;

    const input = this.shadowRoot.getElementById("q");
    input.value = this._query;
    input.addEventListener("input", (e) => {
      this._query = e.target.value;
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this._search(), 350);
    });
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        clearTimeout(this._timer);
        this._search();
      }
    });
    this.shadowRoot.getElementById("newweek").addEventListener("click", async () => {
      if (confirm(T.newWeekConfirm)) await this._ws({ type: "aldi_boodschappen/new_week" });
    });

    // Event delegation
    this.shadowRoot.getElementById("results").addEventListener("click", (e) => this._onResultClick(e));
    this.shadowRoot.getElementById("status").addEventListener("click", (e) => {
      if (e.target.id === "plain") this._addPlain();
    });
    this.shadowRoot.getElementById("list").addEventListener("click", (e) => this._onListClick(e));
    this.shadowRoot.getElementById("list").addEventListener("change", (e) => this._onListChange(e));

    this._rendered = true;
    this._renderStatus();
    this._renderResults();
    this._renderList();
  }

  _renderStatus() {
    const el = this.shadowRoot.getElementById("status");
    if (!el) return;
    if (this._status === "loading") el.textContent = T.searching;
    else if (this._status.startsWith("error:"))
      el.innerHTML = `${escapeHtml(T.error)}: ${escapeHtml(this._status.slice(6))}. <button id="plain">${T.addPlain} "${escapeHtml(this._query.trim())}"</button>`;
    else if (this._query.trim().length >= 2 && !this._results.length)
      el.innerHTML = `${T.noResults} <button id="plain">${T.addPlain} "${escapeHtml(this._query.trim())}"</button>`;
    else if (this._query.trim().length >= 2)
      el.innerHTML = `<button id="plain">${T.addPlain} "${escapeHtml(this._query.trim())}"</button>`;
    else el.textContent = "";
  }

  _renderResults() {
    const el = this.shadowRoot.getElementById("results");
    if (!el) return;
    el.innerHTML = this._results
      .map(
        (p, i) => `
      <div class="card">
        <div class="img"${p.image ? ` style="background:#fff url('${escapeHtml(p.image)}') center/contain no-repeat"` : ""}>${p.image ? "" : "🛒"}</div>
        <div class="body">
          <div class="name">${escapeHtml(p.name)}</div>
          ${p.available === false ? `<div class="meta">Nu niet beschikbaar</div>` : ""}
          ${p.brand ? `<div class="meta">${escapeHtml(p.brand)}</div>` : ""}
          ${p.description ? `<div class="meta">${escapeHtml(p.description)}</div>` : ""}
          <div><span class="price">${money(p.price, p.currency)}</span>${p.old_price ? `<span class="old">${money(p.old_price, p.currency)}</span>` : ""}</div>
          ${p.base_price ? `<div class="meta">${escapeHtml(p.base_price)}</div>` : ""}
          <div class="actions">
            <label class="chk"><input type="checkbox" data-rec="${i}"> 🔁 ${T.everyWeek}</label>
            <button class="btn" data-add="${i}">${T.add}</button>
          </div>
        </div>
      </div>`
      )
      .join("");
  }

  _renderList() {
    const el = this.shadowRoot?.getElementById("list");
    if (!el) return;
    if (!this._items.length) {
      el.innerHTML = `<div class="empty">${T.empty}</div>`;
      return;
    }
    const sorted = [...this._items].sort((a, b) => Number(a.checked) - Number(b.checked));
    el.innerHTML = sorted
      .map((it) => {
        const thumb = it.image
          ? `<img src="${escapeHtml(it.image)}" alt="">`
          : `<div class="ph">🛒</div>`;
        const sub = [it.description, it.price != null ? money(it.price * it.quantity, it.currency) : ""]
          .filter(Boolean)
          .join(" · ");
        const nameHtml = it.url
          ? `<a href="${escapeHtml(it.url)}" target="_blank" rel="noopener">${escapeHtml(it.name)}</a>`
          : escapeHtml(it.name);
        return `
        <div class="row ${it.checked ? "done" : ""}">
          <input type="checkbox" data-check="${it.id}" ${it.checked ? "checked" : ""} title="${it.checked ? T.done : T.toBuy}">
          ${thumb}
          <div class="info"><div class="nm">${nameHtml}</div>${sub ? `<div class="sub">${escapeHtml(sub)}</div>` : ""}</div>
          <div class="qty">
            <button data-dec="${it.id}">−</button><span>${it.quantity}</span><button data-inc="${it.id}">+</button>
          </div>
          <span class="tag ${it.recurring ? "on" : ""}" data-rec-toggle="${it.id}" title="${T.recurring}">🔁 ${T.everyWeek}</span>
          <button class="icon" data-del="${it.id}" title="${T.remove}">✕</button>
        </div>`;
      })
      .join("");
  }

  /* ---------- acties ---------- */

  async _search() {
    const q = this._query.trim();
    const seq = ++this._searchSeq;
    if (q.length < 2) {
      this._results = [];
      this._status = "";
      this._renderStatus();
      this._renderResults();
      return;
    }
    this._status = "loading";
    this._renderStatus();
    try {
      const res = await this._ws({ type: "aldi_boodschappen/search", query: q });
      if (seq !== this._searchSeq) return; // verouderd antwoord
      this._results = res.results || [];
      this._status = "";
    } catch (err) {
      if (seq !== this._searchSeq) return;
      this._results = [];
      this._status = `error:${err.message || err}`;
    }
    this._renderStatus();
    this._renderResults();
  }

  async _onResultClick(e) {
    const btn = e.target.closest("[data-add]");
    if (!btn) return;
    const idx = Number(btn.dataset.add);
    const product = this._results[idx];
    const rec = this.shadowRoot.querySelector(`[data-rec="${idx}"]`)?.checked ?? false;
    await this._ws({
      type: "aldi_boodschappen/add",
      name: product.name,
      product,
      quantity: 1,
      recurring: rec,
    });
    btn.textContent = "✓";
    setTimeout(() => (btn.textContent = T.add), 900);
  }

  async _addPlain() {
    const name = this._query.trim();
    if (!name) return;
    await this._ws({ type: "aldi_boodschappen/add", name, quantity: 1, recurring: false });
    this._query = "";
    this._results = [];
    this._status = "";
    this.shadowRoot.getElementById("q").value = "";
    this._renderStatus();
    this._renderResults();
  }

  _item(id) {
    return this._items.find((i) => i.id === id);
  }

  async _onListClick(e) {
    const t = e.target;
    if (t.dataset.del) {
      await this._ws({ type: "aldi_boodschappen/remove", item_id: t.dataset.del });
    } else if (t.dataset.inc || t.dataset.dec) {
      const id = t.dataset.inc || t.dataset.dec;
      const it = this._item(id);
      if (!it) return;
      const quantity = Math.max(1, it.quantity + (t.dataset.inc ? 1 : -1));
      await this._ws({ type: "aldi_boodschappen/update", item_id: id, quantity });
    } else if (t.dataset.recToggle) {
      const it = this._item(t.dataset.recToggle);
      if (!it) return;
      await this._ws({ type: "aldi_boodschappen/update", item_id: it.id, recurring: !it.recurring });
    }
  }

  async _onListChange(e) {
    const t = e.target;
    if (t.dataset.check) {
      await this._ws({ type: "aldi_boodschappen/update", item_id: t.dataset.check, checked: t.checked });
    }
  }
}

customElements.define("aldi-boodschappen-panel", AldiBoodschappenPanel);
