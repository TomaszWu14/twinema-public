// Panele edytora layoutu: strefy, właściwości zaznaczenia, KPI na żywo, problemy, formularze dodawania.
// Panele z polami/przyciskami przebudowujemy tylko, gdy zmieniła się ich treść — fokus klawiatury zostaje.
import { makeBlock, mode, nextRackIds, snap, zoneColors } from './layout-core.js';
import { S, addItems, change, deleteSelected, duplicateSelected, keysAt, rotateSelected, selectZone, selected,
  setView, showKeys, viewCenter } from './layout-editor.js';
import { renderHall } from './layout-hall.js';
import { renderSitePanel, siteProps } from './layout-site.js';

const $ = (id) => document.getElementById(id);
const CFG = JSON.parse($('le-config').textContent);
const fmt = (v, d = 0) => (typeof v === 'number' ? v.toLocaleString('pl-PL', { maximumFractionDigits: d }) : '—');
const last = {};
// Domyślne wymiary nowych elementów hali [m] (szer. × głęb.) — do poprawienia w panelu właściwości.
const FEATURE_SIZE = { dock: [3.5, 2], gate: [4, 0.5], staging: [10, 6], station: [3, 3], leader: [3, 3],
  corridor: [20, 3], block_zone: [10, 10], returns: [6, 6], other: [5, 5], fire_route: [30, 4], charging: [8, 5],
  walkway: [30, 1.2], truckway: [30, 3.5], zone_temp: [15, 10], zone_adr: [10, 8], zone_oversize: [15, 8],
  zone_value: [8, 6] };

const eqValue = (r) => (r.equipment_id ? `eq:${r.equipment_id}` : `cat:${r.equipment}`);

/** Lista wyboru sprzętu regału(ów): kategoria ogólna albo klasa/model z katalogu (alejka, wysokość, udźwig
 *  z katalogu). Zmienia wszystkie zaznaczone naraz (np. cały blok VNA). */
function equipmentSelect(racks) {
  const same = racks.every((r) => eqValue(r) === eqValue(racks[0])) ? eqValue(racks[0]) : '';
  const set = (v) => change(() => racks.forEach((r) => {
    const [kind, key] = v.split(':');
    if (kind === 'cat') { r.equipment = key; r.equipment_id = null; return; }
    const eq = (CFG.catalog || []).find((e) => String(e.id) === key);
    r.equipment_id = eq.id;
    r.equipment = eq.category;   // kategoria regału z typu sprzętu (equipment.catalog.RACK_CATEGORY)
  }));
  const opt = (value, label) => h('option', { value, selected: value === same }, label);
  return h('label', { class: 'le-wide' }, racks.length > 1 ? `Sprzęt (${racks.length} regałów)` : 'Sprzęt obsługi',
    h('select', { class: 'form-control', onchange: (e) => set(e.target.value) },
      ...(same ? [] : [h('option', { value: '', disabled: true, selected: true }, '— różny —')]),
      h('optgroup', { label: 'Ogólnie (bez katalogu)' }, ...Object.entries(CFG.equipment).map(([k, v]) => opt(`cat:${k}`, v))),
      h('optgroup', { label: 'Z katalogu sprzętu' }, ...(CFG.catalog || []).map((e) =>
        opt(`eq:${e.id}`, `${e.name} — alejka ${fmt(e.aisle_m, 1)} m, do ${fmt(e.max_lift_m, 1)} m`)))));
}

/** Rola doku/bramy (S3b) — symulacja scenariusza wybiera po niej doki; puste = zgadywana z etykiety. */
function dockRoleSelect(f) {
  return h('label', { class: 'le-wide' }, 'Rola doku',
    h('select', { class: 'form-control', onchange: (e) => change(() => { f.dock_role = e.target.value; }) },
      h('option', { value: '', selected: !f.dock_role }, '— z etykiety —'),
      ...Object.entries(CFG.dockRoles || {}).map(([k, v]) => h('option', { value: k, selected: k === f.dock_role }, v))));
}

function h(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'style') e.style.cssText = v;        // CSSOM — atrybut style= blokuje CSP (R-20)
    else if (v !== false && v !== null && v !== undefined) e.setAttribute(k, v === true ? '' : v);
  }
  e.append(...children.filter((c) => c !== null && c !== undefined));
  return e;
}

/** Zmienił się podpis panelu? (i nie piszesz akurat w jego polu — wtedy nie przerywamy) */
function stale(name, sig, box) {
  if (last[name] === sig) return false;
  if (box.contains(document.activeElement) && last[`${name}:sel`] === S.sel.size + [...S.sel].join()) return false;
  last[name] = sig;
  last[`${name}:sel`] = S.sel.size + [...S.sel].join();
  return true;
}

function renderZones() {
  const box = $('le-zones'), counts = {};
  S.racks.forEach((r) => { counts[r.zone] = (counts[r.zone] || 0) + 1; });
  const colors = zoneColors(S.racks);
  const sig = JSON.stringify(counts);
  if (!stale('zones', sig, box)) return;
  box.replaceChildren(...Object.keys(colors).map((z) => h('li', {},
    h('button', { type: 'button', class: 'btn btn-ghost btn-sm', onclick: () => selectZone(z) },
      h('span', { class: 'le-swatch', style: `background:${colors[z]}`, 'aria-hidden': 'true' }),
      `Strefa ${z} · ${counts[z]} regałów`))));
  if (!S.racks.length) box.replaceChildren(h('li', { class: 'text-muted text-sm' }, 'Brak regałów — dodaj blok.'));
}

/** Pole liczbowe/tekstowe zmieniające jedną właściwość elementu (z walidacją przeglądarki). */
function field(label, item, key, { wide, ...attrs }, parse = Number) {
  const input = h('input', { class: 'form-control', value: item[key], ...attrs,
    onchange: (e) => {
      if (!e.target.checkValidity()) { e.target.reportValidity(); return; }
      const v = parse(e.target.value);
      if (v !== item[key]) change(() => { item[key] = v; });
    } });
  return h('label', wide ? { class: 'le-wide' } : {}, label, input);
}

function renderProps() {
  const box = $('le-props'), items = selected();
  const sig = JSON.stringify([S.floor, items, S.view]);
  if (!stale('props', sig, box)) return;
  const L = CFG.limits;
  const num = (k) => ({ type: 'number', required: true, min: L[k][0], max: L[k][1], step: 1 });
  const pos = { type: 'number', required: true, step: 0.1 };
  const txt = (max) => ({ required: true, maxlength: max });
  const text = (v) => v.trim();
  let form;
  if (S.view === 'site') {
    form = siteProps(items);
  } else if (!items.length) {
    form = h('div', { class: 'le-form' },
      field('Szerokość hali [m]', S.floor, 'width', { ...pos, min: 1, max: 5000 }),
      field('Głębokość hali [m]', S.floor, 'depth', { ...pos, min: 1, max: 5000 }),
      h('p', { class: 'text-muted text-sm le-wide', style: 'margin:0' }, 'Nic nie zaznaczono — kliknij regał albo element hali.'));
  } else if (items.length === 1 && items[0].n_bays !== undefined) {
    const r = items[0];
    form = h('div', { class: 'le-form' },
      field('Strefa', r, 'zone', txt(20), text), field('Numer', r, 'rack_id', txt(20), text),
      field('Gniazda', r, 'n_bays', num('n_bays')), field('Poziomy', r, 'n_levels', num('n_levels')),
      field('Szer. gniazda [cm]', r, 'bay_width_cm', num('bay_width_cm')), field('Głębokość [cm]', r, 'depth_cm', num('depth_cm')),
      field('Wys. poziomu [cm]', r, 'level_height_cm', num('level_height_cm')), field('Kąt [°]', r, 'angle', { ...pos, min: -360, max: 360 }),
      field('X [m]', r, 'x', pos), field('Y [m]', r, 'y', pos),
      field('Nośność miejsca [kg]', r, 'load_kg', { type: 'number', required: true, min: 50, max: 10000, step: 50 }),
      equipmentSelect([r]));
  } else if (items.length === 1) {
    const f = items[0];
    const kind = h('select', { class: 'form-control', onchange: (e) => change(() => { f.kind = e.target.value; }) },
      ...Object.entries(S.kinds).map(([k, v]) => h('option', { value: k, selected: k === f.kind }, v)));
    form = h('div', { class: 'le-form' }, h('label', { class: 'le-wide' }, 'Rodzaj', kind),
      field('Etykieta', f, 'label', { maxlength: 100, wide: true }, text),
      field('Szerokość [m]', f, 'width', { ...pos, min: 0.1, max: 5000 }), field('Głębokość [m]', f, 'depth', { ...pos, min: 0.1, max: 5000 }),
      field('X [m]', f, 'x', pos), field('Y [m]', f, 'y', pos), field('Kąt [°]', f, 'angle', { ...pos, min: -360, max: 360 }),
      f.kind === 'dock' || f.kind === 'gate' ? dockRoleSelect(f) : null);
  } else {
    const racks = items.filter((it) => it.n_bays !== undefined);
    form = h('div', { class: 'le-form' }, h('p', { class: 'text-sm le-wide', style: 'margin:0' }, `Zaznaczono ${items.length} elementów.`),
      racks.length ? equipmentSelect(racks) : null);
  }
  const editable = items.filter((it) => !it._hall);
  const actions = S.view === 'site' ? (editable.length ? h('div', { style: 'display:flex;flex-wrap:wrap;gap:6px;margin-top:10px' },
    h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: () => rotateSelected(90) }, 'Obróć 90°'),
    h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: duplicateSelected }, 'Duplikuj'),
    h('button', { type: 'button', class: 'btn btn-ghost btn-sm', onclick: deleteSelected }, 'Usuń')) : null)
    : items.length ? h('div', { style: 'display:flex;flex-wrap:wrap;gap:6px;margin-top:10px' },
    h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: () => rotateSelected(90) }, 'Obróć 90°'),
    h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: () => rotateSelected(-90) }, 'Obróć −90°'),
    h('button', { type: 'button', class: 'btn btn-secondary btn-sm', onclick: duplicateSelected }, 'Duplikuj'),
    h('button', { type: 'button', class: 'btn btn-ghost btn-sm', onclick: deleteSelected }, 'Usuń')) : null;
  box.replaceChildren(form, ...(actions ? [actions] : []));
}

function renderKpi() {
  const k = S.kpi || {}, t = k.travel || {}, hk = k.height;
  const rows = [['Miejsca paletowe', fmt(k.pallet_positions)], ['Miejsca na m² hali', fmt(k.positions_per_m2, 2)],
    ['Powierzchnia hali', `${fmt(k.floor_area_m2)} m²`], ['Zabudowa', `${fmt(k.built_area_m2)} m²`],
    ['Śr. droga do miejsca', `${fmt(t.avg_m, 1)} m`], ['Śr. droga — strefa A', `${fmt(t.a_zone_avg_m, 1)} m`],
    ['Regały', fmt(S.racks.length)], ['Elementy hali', fmt(S.features.length)], ['Słupy', fmt(k.columns)]];
  if (hk) {
    rows.push(['Wysokość użytkowa', `${fmt(hk.usable_m, 2)} m`]);
    for (const [z, v] of Object.entries(hk.zones)) rows.push([`Poziomy ${z} (maks.)`, `${v.levels} / ${v.max_levels}`]);
  }
  const s = k.site;
  if (s) {
    rows.push(['Działka', `${fmt(s.plot_m2)} m²`], ['Zabudowa działki', `${fmt(s.coverage_pct, 1)} %`],
      ['Biologicznie czynna', `${fmt(s.bio_pct, 1)} %`], ['Utwardzone', `${fmt(s.paved_pct, 1)} %`],
      ['Rezerwa pod rozbudowę', `${fmt(s.reserve_m2)} m²`], ['Wysokość budynku', `~${fmt(s.building_height_m, 1)} m`]);
  }
  $('le-kpi').replaceChildren(...rows.flatMap(([a, b]) => [h('dt', {}, a), h('dd', {}, b)]));
}

function renderIssues() {
  const box = $('le-issues');
  if (last.issues === S.issues) return;
  last.issues = S.issues;
  const e = S.issues.filter((i) => i.severity === 'error').length;
  $('le-issue-count').textContent = S.issues.length ? `Problemy · błędy ${e}, ostrzeżenia ${S.issues.length - e}` : 'Problemy';
  box.replaceChildren(...(S.issues.length ? S.issues.map((it) => h('li', {},
    h('button', { type: 'button', class: `is-${it.severity}`, onclick: () => {
      const site = (it.areas?.length || it.hall) && !it.racks.length;          // problem działki → widok działki
      if (site !== (S.view === 'site')) setView(site ? 'site' : 'hall');
      showKeys(keysAt(it.racks, it.features, it.areas, it.hall));
    } },
      `${it.severity === 'error' ? 'Błąd' : 'Ostrzeżenie'}: ${it.message}`)))
    : [h('li', { class: 'text-muted text-sm' }, 'Brak problemów.')]));
}

function initForms() {
  if (last.forms || !Object.keys(S.kinds).length) return;
  last.forms = true;
  const b = $('le-block').elements;
  b.bay_width_cm.value = mode(S.racks.map((r) => r.bay_width_cm), 270);
  b.depth_cm.value = mode(S.racks.map((r) => r.depth_cm), 110);
  b.level_height_cm.value = mode(S.racks.map((r) => r.level_height_cm), 180);
  b.levels.value = mode(S.racks.map((r) => r.n_levels), 5);
  b.aisle.value = CFG.aisle;
  b.equipment.replaceChildren(...Object.entries(CFG.equipment).map(([k, v]) => h('option', { value: k }, v)));
  b.equipment.addEventListener('change', () => { b.aisle.value = CFG.aisles[b.equipment.value]; });
  $('le-block').addEventListener('submit', (e) => {
    e.preventDefault();
    const v = Object.fromEntries(['rows', 'bays', 'levels', 'bay_width_cm', 'depth_cm', 'level_height_cm', 'aisle']
      .map((k) => [k, Number(b[k].value)]));
    const zone = b.zone.value.trim(), [cx, cy] = viewCenter();
    const w = v.bays * v.bay_width_cm / 100, d = v.rows * (v.depth_cm / 100 + v.aisle);
    addItems(makeBlock({ x: snap(cx - w / 2), y: snap(cy - d / 2), rows: v.rows, bays: v.bays, levels: v.levels,
      bayWidthCm: v.bay_width_cm, depthCm: v.depth_cm, levelHeightCm: v.level_height_cm, aisle: v.aisle, zone,
      ids: nextRackIds(S.racks, zone, v.rows), backToBack: b.back.checked, backGap: CFG.backGap })
      .map((r) => ({ id: null, ...r, equipment: b.equipment.value })), S.racks);
  });
  const fk = $('le-feature-kind'), f = $('le-feature').elements;
  fk.replaceChildren(...Object.entries(S.kinds).map(([k, v]) => h('option', { value: k }, v)));
  fk.value = 'staging' in S.kinds ? 'staging' : fk.options[0]?.value;
  const sizes = () => { [f.width.value, f.depth.value] = FEATURE_SIZE[fk.value] || [5, 5]; };
  fk.addEventListener('change', sizes);
  sizes();
  $('le-feature').addEventListener('submit', (e) => {
    e.preventDefault();
    const [cx, cy] = viewCenter(), w = Number(f.width.value), d = Number(f.depth.value);
    addItems([{ id: null, kind: fk.value, label: S.kinds[fk.value], x: snap(cx - w / 2), y: snap(cy - d / 2),
      width: w, depth: d, angle: 0 }], S.features);
  });
}

export function renderPanels() {
  initForms();
  renderZones();
  renderProps();
  renderKpi();
  renderIssues();
  renderHall();
  renderSitePanel();
}
