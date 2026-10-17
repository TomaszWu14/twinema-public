// US-007: stan zadania z kolejki bez meta-refresh (WCAG 2.2.1) — fetch co 5 s, komunikat w aria-live,
// po końcu przycisk „Odśwież” (bez automatycznego przeładowania); wzór: twin/ewm_tasks/detail.html.
(function () {
  var box = document.getElementById('job-progress'); if (!box || !window.fetch) return;
  var URL = box.getAttribute('data-status-url'), EVERY_MS = 5000, MAX_FAILS = 5;
  var live = document.getElementById('job-progress-live'), meta = document.getElementById('job-progress-meta');
  var btn = document.getElementById('job-progress-toggle'), refresh = document.getElementById('job-refresh');
  var timer = null, paused = false, busy = false, fails = 0, finished = false;

  function schedule() { clearTimeout(timer); if (!paused && !finished) timer = setTimeout(poll, EVERY_MS); }
  function stop(msg) { finished = true; clearTimeout(timer); btn.hidden = true; if (msg) live.textContent = msg; }

  function poll() {
    if (paused || finished || busy) return;
    if (document.hidden) { schedule(); return; }
    busy = true;
    fetch(URL, {credentials: 'same-origin', cache: 'no-store', headers: {'Accept': 'application/json'}})
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (d) {
        fails = 0;
        meta.textContent = 'Status: ' + d.status_display + ' · sprawdzono ' + new Date().toLocaleTimeString('pl-PL');
        if (d.pending) return;
        stop(d.status === 'done' ? 'Obliczenie zakończone — odśwież, żeby zobaczyć wynik.'
          : 'Obliczenie zakończyło się błędem — odśwież, żeby zobaczyć szczegóły.');
        refresh.hidden = false;
        refresh.addEventListener('click', function () { location.reload(); });
      })
      .catch(function () {
        if (++fails >= MAX_FAILS) stop('Nie udało się sprawdzić stanu obliczenia — odśwież stronę ręcznie.');
        else meta.textContent = 'Nie udało się sprawdzić stanu — ponowię za 5 s.';
      })
      .then(function () { busy = false; schedule(); });
  }

  btn.addEventListener('click', function () {
    paused = !paused;
    btn.textContent = paused ? 'Wznów sprawdzanie' : 'Wstrzymaj sprawdzanie';
    live.textContent = paused ? 'Sprawdzanie stanu wstrzymane.' : 'Sprawdzanie stanu wznowione.';
    if (paused) clearTimeout(timer); else poll();
  });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) poll(); });
  schedule();
})();
