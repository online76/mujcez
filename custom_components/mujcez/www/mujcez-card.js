// Můj ČEZ – karta odběrného místa (elektřina / plyn) s výběrem místa.
// type: custom:mujcez-card
// komodita: elektrina | plyn      (povinné)
// vychozi: "Veselí 125"            (výchozí odběrné místo – začátek názvu; výběr si karta pamatuje)
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const nf = (v, d = 0) => (v === null || v === undefined || v === '' || isNaN(v)) ? '–' : Number(v).toLocaleString('cs-CZ', { minimumFractionDigits: d, maximumFractionDigits: d });
const kc = (v) => (v === null || v === undefined) ? '–' : `${nf(v, Math.abs(v) < 100 && v % 1 ? 2 : 0)} Kč`;
const dt = (s, y = true) => {
  if (!s) return '–';
  const [Y, M, D] = String(s).slice(0, 10).split('-');
  return y ? `${+D}. ${+M}. ${Y}` : `${+D}. ${+M}.`;
};
const norm = (s) => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
const shortName = (n) => String(n || '').replace(/\s*-\s*\d{1,2}\.\d{1,2}\.\d{4}\s*$/, '');

class MujCezCard extends HTMLElement {
  setConfig(c) {
    if (!c.komodita || !['elektrina', 'plyn'].includes(c.komodita)) throw new Error('komodita: elektrina | plyn');
    this._c = { vychozi: 'Veselí 125', ...c };
    this._key = `mujcez-${c.komodita}`;
  }

  set hass(hass) {
    this._h = hass;
    const pts = Object.values(hass.states).filter((s) => s.attributes.mujcez_prehled && s.attributes.komodita === this._c.komodita);
    const sig = pts.map((s) => s.entity_id + s.last_updated).join('|') + '|' + this._sel;
    if (sig === this._sig) return;
    this._sig = sig;
    this._pts = pts.sort((a, b) => shortName(a.attributes.nazev).localeCompare(shortName(b.attributes.nazev), 'cs'));
    this._render();
  }

  _selected() {
    const pts = this._pts || [];
    let code = this._sel;
    if (!code) { try { code = localStorage.getItem(this._key); } catch (e) { /* */ } }
    let p = pts.find((s) => s.attributes.kod === code);
    if (!p) {
      const want = norm(this._c.vychozi);
      p = pts.find((s) => norm(s.attributes.nazev).startsWith(want)) || pts[0];
    }
    return p;
  }

  _chart(a) {
    const months = (a.spotreba_mesice || []).length > 1;
    const rows = (months ? a.spotreba_mesice : a.spotreba_roky || []).slice(-(months ? 13 : 6));
    if (!rows.length) return '<div class="muted">Historie spotřeby zatím není k dispozici.</div>';
    const two = this._c.komodita === 'elektrina' && rows.some((r) => (r.nt || 0) > 0);
    const W = 640, H = 190, pad = 26, bw = (W - 10) / rows.length;
    const max = Math.max(...rows.map((r) => r.kwh || 0), 1);
    const sc = (v) => (v || 0) / max * (H - pad - 22);
    const bars = rows.map((r, i) => {
      const x = 5 + i * bw + bw * 0.15, w = bw * 0.7;
      const lab = months ? `${String(r.od).slice(5, 7)}/${String(r.od).slice(2, 4)}` : `${String(r.od).slice(0, 4)}/${String(r.do).slice(2, 4)}`;
      const tip = `${dt(r.od)} – ${dt(r.do)}: ${nf(r.kwh)} kWh` + (two ? ` (VT ${nf(r.vt)}, NT ${nf(r.nt)})` : '') + (r.kc != null ? `, ${kc(r.kc)}` : '');
      let rect;
      if (two) {
        const hv = sc(r.vt), hn = sc(r.nt);
        rect = `<rect x="${x}" y="${H - pad - hn}" width="${w}" height="${hn}" rx="3" class="nt"/>` +
               `<rect x="${x}" y="${H - pad - hn - hv}" width="${w}" height="${hv}" rx="3" class="vt"/>`;
      } else {
        const h = sc(r.kwh);
        rect = `<rect x="${x}" y="${H - pad - h}" width="${w}" height="${h}" rx="4" class="bar"/>`;
      }
      return `<g><title>${esc(tip)}</title>${rect}
        <text x="${x + w / 2}" y="${H - pad - sc(r.kwh) - 6}" class="val">${nf(r.kwh)}</text>
        <text x="${x + w / 2}" y="${H - 8}" class="lab">${lab}</text></g>`;
    }).join('');
    const legend = two ? '<span class="lg"><i class="vt"></i>VT</span><span class="lg"><i class="nt"></i>NT</span>' : '';
    return `<div class="chead"><span>${months ? 'Měsíční spotřeba (kWh)' : 'Roční spotřeba (kWh)'}</span>${legend}</div>
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" class="chart">${bars}</svg>`;
  }

  _render() {
    if (!this.shadowRoot) this.attachShadow({ mode: 'open' });
    const gas = this._c.komodita === 'plyn';
    const accent = gas ? '#3d9bff' : '#ffb020';
    const p = this._selected();
    const css = `<style>
      :host { display:block; }
      ha-card { padding:16px; font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text",Roboto,sans-serif; }
      .top { display:flex; align-items:center; gap:12px; flex-wrap:wrap; }
      .ic { width:44px; height:44px; border-radius:12px; display:grid; place-items:center; flex:none;
            background:color-mix(in srgb, ${accent} 20%, transparent); color:${accent}; }
      .ic ha-icon { --mdc-icon-size:26px; }
      .who { flex:1; min-width:180px; }
      .who h2 { margin:0; font-size:20px; font-weight:650; color:var(--primary-text-color); }
      .who div { font-size:13px; color:var(--secondary-text-color); margin-top:2px; }
      select { font:inherit; font-size:15px; padding:8px 34px 8px 12px; border-radius:10px; color:var(--primary-text-color);
               background:rgba(127,127,127,.16) url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8'%3E%3Cpath d='M1 1l5 5 5-5' stroke='%23999' stroke-width='2' fill='none'/%3E%3C/svg%3E") no-repeat right 12px center;
               border:1px solid rgba(127,127,127,.3); appearance:none; -webkit-appearance:none; max-width:100%; cursor:pointer; }
      select option { color:#000; }
      .kpis { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:10px; margin-top:16px; }
      .k { background:rgba(127,127,127,.12); border-radius:14px; padding:12px 14px; }
      .k .l { font-size:12px; color:var(--secondary-text-color); text-transform:uppercase; letter-spacing:.04em; }
      .k .v { font-size:22px; font-weight:700; color:var(--primary-text-color); margin-top:4px; font-variant-numeric:tabular-nums; }
      .k .s { font-size:12.5px; color:var(--secondary-text-color); margin-top:2px; }
      .k.warn .v { color:#ff6b5e; } .k.ok .v { color:#30d158; }
      h3 { margin:20px 0 8px; font-size:15px; font-weight:600; color:var(--primary-text-color); }
      .chead { display:flex; gap:14px; align-items:center; font-size:13px; color:var(--secondary-text-color); margin:18px 0 4px; }
      .chead span:first-child { flex:1; }
      .lg { display:inline-flex; align-items:center; gap:5px; } .lg i { width:10px; height:10px; border-radius:3px; display:inline-block; }
      .chart { width:100%; height:190px; display:block; }
      .bar, i.bar { fill:${accent}; background:${accent}; } .vt, i.vt { fill:#ffb020; background:#ffb020; } .nt, i.nt { fill:#3d9bff; background:#3d9bff; }
      .val { fill:var(--primary-text-color); font-size:11px; text-anchor:middle; }
      .lab { fill:var(--secondary-text-color); font-size:11px; text-anchor:middle; }
      table { width:100%; border-collapse:collapse; font-size:13.5px; }
      td, th { padding:7px 6px; text-align:left; border-bottom:1px solid rgba(127,127,127,.18); color:var(--primary-text-color); }
      th { font-weight:500; color:var(--secondary-text-color); font-size:12px; }
      td.r, th.r { text-align:right; font-variant-numeric:tabular-nums; }
      .st { font-size:12px; padding:2px 8px; border-radius:999px; background:rgba(127,127,127,.18); white-space:nowrap; }
      .st.paid { background:rgba(48,209,88,.18); color:#30d158; } .st.unpaid { background:rgba(255,107,94,.2); color:#ff6b5e; }
      .grid2 { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:0 24px; }
      dl { display:grid; grid-template-columns:auto 1fr; gap:6px 14px; margin:0; font-size:13.5px; }
      dt { color:var(--secondary-text-color); } dd { margin:0; color:var(--primary-text-color); }
      .muted { color:var(--secondary-text-color); font-size:13px; padding:8px 0; }
      .note { font-size:12.5px; color:var(--secondary-text-color); margin-top:10px; line-height:1.45; }
      a { color:${accent}; }
    </style>`;
    if (!p) {
      this.shadowRoot.innerHTML = `${css}<ha-card><div class="muted">Žádné odběrné místo (${gas ? 'plyn' : 'elektřina'}) z integrace Můj ČEZ.</div></ha-card>`;
      return;
    }
    const a = p.attributes;
    const opts = this._pts.map((s) => `<option value="${esc(s.attributes.kod)}" ${s === p ? 'selected' : ''}>${esc(shortName(s.attributes.nazev))}</option>`).join('');
    const unit = a.jednotka_meridla || (gas ? 'm³' : 'kWh');
    const lr = a.posledni_odecet || {};
    const lo = a.posledni_obdobi || {};
    const ly = a.posledni_rok || {};
    const lv = a.posledni_vyuctovani || null;
    const due = a.k_uhrade > 0;
    const meter = lr.datum
      ? (lr.nt != null && !gas ? `${nf(lr.vt)} / ${nf(lr.nt)} <small>${unit}</small>` : `${nf(lr.vt)} <small>${unit}</small>`)
      : '–';
    const kpis = [
      `<div class="k ${due ? 'warn' : 'ok'}"><div class="l">K úhradě</div><div class="v">${kc(a.k_uhrade || 0)}</div>
        <div class="s">${due ? `splatnost ${dt(a.k_uhrade_splatnost)}` : 'vše zaplaceno'}</div></div>`,
      `<div class="k"><div class="l">Záloha</div><div class="v">${a.zaloha ? kc(a.zaloha) : '–'}</div>
        <div class="s">${a.zaloha ? `${esc(a.zaloha_frekvence || '')}${a.zaloha_pristi ? ` · další ${dt(a.zaloha_pristi)}` : ''}` : (a.mesicni_fakturace ? 'měsíční fakturace' : 'bez záloh')}</div></div>`,
      `<div class="k"><div class="l">Stav ${gas ? 'plynoměru' : 'elektroměru'}${lr.nt != null && !gas ? ' VT/NT' : ''}</div><div class="v">${meter}</div>
        <div class="s">${lr.datum ? `${dt(lr.datum)} · ${esc(lr.zpusob || '')}` : 'bez odečtu'}</div></div>`,
      `<div class="k"><div class="l">${a.mesicni_fakturace ? 'Poslední měsíc' : 'Poslední období'}</div><div class="v">${nf(lo.kwh)} <small>kWh</small></div>
        <div class="s">${lo.od ? `${kc(lo.kc)} · ${dt(lo.od, false)}–${dt(lo.do)}` : '–'}</div></div>`,
    ];
    if (!a.mesicni_fakturace || (a.spotreba_roky || []).length) {
      kpis.push(`<div class="k"><div class="l">Roční spotřeba</div><div class="v">${nf(ly.kwh)} <small>kWh</small></div>
        <div class="s">${ly.od ? `${kc(ly.kc)} · ${String(ly.od).slice(0, 4)}/${String(ly.do).slice(2, 4)}` : '–'}</div></div>`);
    }
    if (lv) {
      kpis.push(`<div class="k"><div class="l">Poslední vyúčtování</div><div class="v">${kc(lv.castka)}</div>
        <div class="s">${dt(lv.datum)} · ${esc(lv.stav || '')}</div></div>`);
    }
    const docs = (a.doklady || []).slice(0, 10).map((d) => {
      const cls = d.zaplaceno ? 'paid' : (d.uhradit && d.zbyva > 0 ? 'unpaid' : '');
      return `<tr><td>${dt(d.datum)}</td><td>${esc(d.typ)}${d.obdobi_od && d.kod === 'VYU' ? `<br><small class="muted">${dt(d.obdobi_od, false)}–${dt(d.obdobi_do)}</small>` : ''}</td>
        <td class="r">${kc(d.castka)}</td><td>${d.splatnost ? dt(d.splatnost) : ''}</td><td><span class="st ${cls}">${esc(d.stav || (d.zaplaceno ? 'zaplaceno' : ''))}</span></td></tr>`;
    }).join('');
    const reads = (a.odecty || []).slice().reverse().slice(0, 8).map((r) =>
      `<tr><td>${dt(r.datum)}</td><td class="r">${nf(r.vt)}${r.nt != null && !gas ? ` / ${nf(r.nt)}` : ''} ${unit}</td>
       <td class="r">${r.spotreba != null ? nf(r.spotreba) : '–'}</td><td>${esc(r.zpusob)}</td></tr>`).join('');
    const info = [
      ['Produkt', a.produkt],
      ['Platnost', a.produkt_od ? `${dt(a.produkt_od)} – ${a.produkt_do ? dt(a.produkt_do) : 'na dobu neurčitou'}` : ''],
      [gas ? 'EIC' : 'EAN', a.kod],
      ['Adresa', a.adresa],
      ['Distributor', a.distributor],
      ['Distribuční sazba', a.sazba],
      ['Jistič', a.jistic_a ? `${a.jistic_a} A · ${a.faze || '?'} fáze` : ''],
      ['HDO', !gas ? (a.hdo ? 'ano' : 'ne') : ''],
      ['Měření', [a.mereni, a.typ_mereni].filter(Boolean).join(' · ')],
      ['Odečet', a.odecet],
      ['Kategorie', a.kategorie],
      ['Využití', a.vyuziti],
      [gas ? 'Číslo plynoměru' : 'Číslo elektroměru', a.meridlo],
      ['Typ místa', a.typ_mista],
      ['Fakturace', a.mesicni_fakturace ? 'měsíční' : 'roční'],
      ['Platba záloh', a.platba_zaloh],
      ['Změna záloh', a.zaloha_lze_zmenit ? 'možná' : (a.zaloha_proc_nelze || '')],
    ].filter(([, v]) => v !== '' && v !== null && v !== undefined)
      .map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('');

    this.shadowRoot.innerHTML = `${css}<ha-card>
      <div class="top">
        <div class="ic"><ha-icon icon="${gas ? 'mdi:fire' : 'mdi:flash'}"></ha-icon></div>
        <div class="who"><h2>${gas ? 'Plyn' : 'Elektřina'}</h2><div>${esc(a.adresa)} · ${gas ? 'EIC' : 'EAN'} ${esc(a.kod)}</div></div>
        <select aria-label="Odběrné místo">${opts}</select>
      </div>
      <div class="kpis">${kpis.join('')}</div>
      ${this._chart(a)}
      <div class="grid2">
        <div><h3>Vyúčtování a platby</h3>${docs ? `<table><tr><th>Datum</th><th>Doklad</th><th class="r">Částka</th><th>Splatnost</th><th>Stav</th></tr>${docs}</table>` : '<div class="muted">Žádné doklady.</div>'}</div>
        <div><h3>Odečty</h3>${reads ? `<table><tr><th>Datum</th><th class="r">Stav</th><th class="r">Spotřeba</th><th>Způsob</th></tr>${reads}</table>` : '<div class="muted">Žádné odečty.</div>'}</div>
      </div>
      <h3>Smlouva a odběrné místo</h3>
      <dl>${info}</dl>
      ${a.smlouva_text ? `<div class="note">${esc(a.smlouva_text)}</div>` : ''}
      <div class="note"><a href="https://muj.cez.cz/col/odberne-misto/${esc(a.uid || '')}" target="_blank" rel="noopener">Otevřít v Můj ČEZ ›</a></div>
    </ha-card>`;
    this.shadowRoot.querySelector('select').onchange = (e) => {
      this._sel = e.target.value;
      try { localStorage.setItem(this._key, this._sel); } catch (err) { /* */ }
      this._sig = null;
      this.hass = this._h;
    };
  }

  getCardSize() { return 12; }
  getGridOptions() { return { columns: 'full' }; }
  static getStubConfig() { return { komodita: 'elektrina', vychozi: 'Veselí 125' }; }
}

if (!customElements.get('mujcez-card')) customElements.define('mujcez-card', MujCezCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'mujcez-card', name: 'Můj ČEZ', description: 'Odběrné místo elektřiny nebo plynu z Můj ČEZ s výběrem místa' });
