// Edytor layoutu — konstrukcja hali (E2b): siatka słupów, podkład (rzut PNG/JPG) z kalibracją skali.
// Słupy liczy serwer (`twin.layout.column_list`) i odsyła w uklad.json / sprawdz/ — jedna reguła, bez kopii w JS.
import { S, change, render, status, viewCenter } from './layout-editor.js';
import { round, snap } from './layout-core.js';

const NS = 'http://www.w3.org/2000/svg';
const $ = (id) => document.getElementById(id);
const CFG = JSON.parse($('le-config').textContent);
const CSRF = document.querySelector('[name=csrfmiddlewaretoken]').value;
const refKey = (ref) => JSON.stringify(ref);
let last = '';

function el(tag, attrs, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  parent?.appendChild(e);
  return e;
}

/** Podkład pod siatką i elementami (bez zdarzeń myszy — nie przeszkadza w zaznaczaniu). */
export function drawUnderlay(g) {
  const u = S.underlay;
  if (!u?.url || !u.w_px) return;
  el('image', { href: u.url, x: u.x, y: u.y, width: u.w_px * u.scale, height: u.h_px * u.scale,
    opacity: u.opacity, preserveAspectRatio: 'none', 'pointer-events': 'none' }, g);
}

/** Słupy nad elementami; klik zaznacza słup (Delete usuwa). Punkty kalibracji podkładu. */
export function drawColumns(g) {
  for (const c of S.colList) {
    const sel = S.selCol === refKey(c.ref);
    el('rect', { class: `le-col${sel ? ' is-selected' : ''}`, x: c.x - c.size / 2, y: c.y - c.size / 2,
      width: c.size, height: c.size, 'data-col': refKey(c.ref) }, g);
  }
  for (const [x, y] of S.calib?.pts || []) el('circle', { class: 'le-calib', cx: x, cy: y, r: 0.4 }, g);
}

/** Zdarzenie myszy na planie: true = obsłużone (kalibracja albo klik w słup). */
export function hallPointer(e, [wx, wy]) {
  if (S.calib && S.calib.pts.length < 2) {
    S.calib.pts.push([wx, wy]);
    status(S.calib.pts.length === 1 ? 'Kalibracja: kliknij drugi punkt o znanej odległości.'
      : 'Kalibracja: wpisz rzeczywistą odległość w panelu „Hala” i zastosuj.');
    render();
    return true;
  }
  const col = e.target.closest('.le-col');
  if (!col) { S.selCol = null; return false; }
  S.selCol = col.dataset.col;
  S.sel.clear();
  render();
  return true;
}

export function deleteSelectedColumn() {
  if (!S.selCol) return false;
  const ref = JSON.parse(S.selCol);
  change(() => {
    S.columns = { pitch_x: 0, pitch_y: 0, offset_x: 0, offset_y: 0, size: 0.6, removed: [], extra: [], ...S.columns };
    if (ref[0] === 'e') S.columns.extra.splice(ref[1], 1);
    else S.columns.removed.push(ref);
  });
  S.colList = S.colList.filter((c) => refKey(c.ref) !== S.selCol);   // od razu; serwer potwierdzi przy sprawdzeniu
  S.selCol = null;
  render();
  return true;
}

async function upload(fd) {
  const r = await fetch(CFG.urls.underlay, { method: 'POST', body: fd, credentials: 'same-origin',
    headers: { 'X-CSRFToken': CSRF } });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) { status(data.error || `Nie wgrano podkładu (${r.status}).`, 'error'); return; }
  S.underlay = data.underlay;
  document.activeElement?.blur();                      // panel „Hala” przebuduje się z przyciskami kalibracji
  status(S.underlay ? 'Podkład wgrany — skalibruj skalę dwoma punktami o znanej odległości.' : 'Podkład usunięty.', 'ok');
  render();
}

export function h(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'style') e.style.cssText = v;        // CSSOM — atrybut style= blokuje CSP (R-20)
    else if (v !== false && v !== null && v !== undefined) e.setAttribute(k, v === true ? '' : v);
  }
  e.append(...children.filter((c) => c !== null && c !== undefined));
  return e;
}

/** Pole liczbowe zmieniające jedną wartość obiektu `obj()` (pobieranego przy zmianie — po cofnij obiekt jest nowy). */
export function num(label, obj, key, attrs, after) {
  const cur = obj()?.[key];
  return h('label', {}, label, h('input', { class: 'form-control', type: 'number', step: 0.1, value: cur ?? '', ...attrs,
    onchange: (e) => {
      if (!e.target.checkValidity()) { e.target.reportValidity(); return; }
      const v = e.target.value === '' ? null : Number(e.target.value);
      change(() => { after?.(); obj()[key] = v; });
    } }));
}

const ensureCols = () => {
  S.columns = { pitch_x: 0, pitch_y: 0, offset_x: 0, offset_y: 0, size: 0.6, removed: [], extra: [], ...S.columns };
};

/** Panel „Hala”: wysokość w świetle, siatka słupów, podkład i kalibracja. */
export function renderHall() {
  const box = $('le-hall');
  const sig = JSON.stringify([S.floor.clear_height, S.columns, S.underlay, S.selCol, S.calib, S.colList.length]);
  const typing = box.contains(document.activeElement) && document.activeElement.matches('input, select, textarea');
  if (sig === last || typing) return;               // nie przebudowuj pod kursorem; kliknięty przycisk — tak
  last = sig;
  const c = S.columns || {}, u = S.underlay;
  const cols = h('div', { class: 'le-form' },
    num('Wysokość w świetle [m]', () => S.floor, 'clear_height', { min: 2, max: 100, placeholder: 'brak' }),
    h('span', { class: 'text-muted text-sm le-wide', style: 'margin:0' },
      `Słupy: ${S.colList.length}${c.removed?.length ? `, usunięte ${c.removed.length}` : ''}. Rozstaw 0 = bez siatki.`),
    num('Rozstaw X [m]', () => S.columns, 'pitch_x', { min: 0, max: 500 }, ensureCols),
    num('Rozstaw Y [m]', () => S.columns, 'pitch_y', { min: 0, max: 500 }, ensureCols),
    num('Przesunięcie X [m]', () => S.columns, 'offset_x', { min: 0, max: 500 }, ensureCols),
    num('Przesunięcie Y [m]', () => S.columns, 'offset_y', { min: 0, max: 500 }, ensureCols),
    num('Wymiar słupa [m]', () => S.columns, 'size', { min: 0.1, max: 5, step: 0.05 }, ensureCols));
  const colActs = h('div', { class: 'le-acts' },
    h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: () => {
      const [x, y] = viewCenter();
      change(() => { ensureCols(); S.columns.extra.push([snap(x), snap(y)]); });
    } }, 'Dodaj słup na środku'),
    S.selCol ? h('button', { type: 'button', class: 'btn btn-ghost btn-sm', onclick: deleteSelectedColumn }, 'Usuń zaznaczony słup') : null,
    c.removed?.length ? h('button', { type: 'button', class: 'btn btn-ghost btn-sm',
      onclick: () => change(() => { S.columns.removed = []; }) }, 'Przywróć usunięte') : null);

  const file = h('input', { type: 'file', accept: 'image/png,image/jpeg', class: 'form-control', 'aria-label': 'Plik podkładu PNG lub JPG',
    onchange: (e) => { const fd = new FormData(); fd.append('file', e.target.files[0]); upload(fd); } });
  const under = [h('label', { class: 'le-wide' }, 'Podkład — rzut hali (PNG/JPG, maks. 10 MB)', file)];
  if (u) {
    const calib = S.calib;
    under.push(h('div', { class: 'le-form' },
      num('Podkład X [m]', () => S.underlay, 'x', { step: 0.1 }),
      num('Podkład Y [m]', () => S.underlay, 'y', { step: 0.1 }),
      h('label', { class: 'le-wide' }, `Przezroczystość: ${Math.round(u.opacity * 100)} %`,
        h('input', { type: 'range', min: 0, max: 1, step: 0.05, value: u.opacity,
          onchange: (e) => change(() => { S.underlay.opacity = Number(e.target.value); }) }))),
    h('p', { class: 'text-muted text-sm', style: 'margin:4px 0' }, `Skala: ${round(u.scale * 1000, 3)} m na 1000 px.`));
    if (calib?.pts.length === 2) {
      const [[x1, y1], [x2, y2]] = calib.pts;
      const dist = h('input', { type: 'number', class: 'form-control', min: 0.1, step: 0.01, required: true, 'aria-label': 'Rzeczywista odległość [m]' });
      under.push(h('div', { class: 'le-acts' }, h('label', {}, 'Rzeczywista odległość [m]', dist),
        h('button', { type: 'button', class: 'btn btn-primary btn-sm', onclick: () => {
          const real = Number(dist.value), measured = Math.hypot(x2 - x1, y2 - y1);
          if (!(real > 0) || !(measured > 0)) { dist.reportValidity(); return; }
          const k = real / measured;                       // skalowanie wokół pierwszego punktu
          change(() => Object.assign(S.underlay, { scale: S.underlay.scale * k,
            x: round(x1 - (x1 - S.underlay.x) * k), y: round(y1 - (y1 - S.underlay.y) * k) }));
          S.calib = null;
          status(`Skala podkładu skalibrowana (×${round(k, 3)}). Zapisz plan, żeby ją zachować.`, 'ok');
        } }, 'Zastosuj')));
    }
    under.push(h('div', { class: 'le-acts' },
      h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: () => {
        S.calib = calib ? null : { pts: [] };
        status(S.calib ? 'Kalibracja: kliknij pierwszy punkt o znanej odległości (np. róg hali).' : 'Kalibracja przerwana.');
        render();
      } }, calib ? 'Przerwij kalibrację' : 'Kalibruj skalę (2 punkty)'),
      h('button', { type: 'button', class: 'btn btn-ghost btn-sm', onclick: () => {
        const fd = new FormData(); fd.append('delete', '1'); upload(fd);
      } }, 'Usuń podkład')));
  }
  box.replaceChildren(cols, colActs, h('hr', { class: 'le-hr' }), ...under);
}
