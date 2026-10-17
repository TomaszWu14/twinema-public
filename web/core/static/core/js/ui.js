// US-005: zachowania, które były w atrybutach onclick=/onsubmit=/onchange= (zablokowane przez CSP):
//   data-confirm="pytanie"  — na <form> (przy wysłaniu) albo przycisku/linku (przy kliknięciu)
//   data-autosubmit         — na <select>: zmiana wysyła formularz
// R-20: wartości liczone po stronie serwera, które były w atrybutach style= (zablokowane przez CSP):
//   data-pct="42.5"   — szerokość w procentach (paski udziałów), 0–100
//   data-color="#hex" — kolor jako zmienna CSS --c (np. background: var(--c) w klasie elementu)
// Tylko liczba i kolor HEX — wstrzyknięty atrybut nie przemyci dowolnego CSS.
(function () {
  function applyStyles(root) {
    root.querySelectorAll('[data-pct]').forEach(function (el) {
      var n = parseFloat(String(el.getAttribute('data-pct')).replace(',', '.'));
      if (isFinite(n)) el.style.width = Math.max(0, Math.min(100, n)) + '%';
    });
    root.querySelectorAll('[data-color]').forEach(function (el) {
      var c = el.getAttribute('data-color');
      if (/^#[0-9a-f]{3,8}$/i.test(c)) el.style.setProperty('--c', c);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { applyStyles(document); });
  } else {
    applyStyles(document);
  }
  window.twApplyStyles = applyStyles;
})();
(function () {
  document.addEventListener('submit', function (e) {
    var form = e.target, q = form.getAttribute && form.getAttribute('data-confirm');
    if (q && !window.confirm(q)) e.preventDefault();
  }, true);
  document.addEventListener('click', function (e) {
    var el = e.target.closest && e.target.closest('button[data-confirm], a[data-confirm], input[data-confirm]');
    if (el && !window.confirm(el.getAttribute('data-confirm'))) e.preventDefault();
  }, true);
  document.addEventListener('change', function (e) {
    var el = e.target;
    if (el.matches && el.matches('select[data-autosubmit]') && el.form) el.form.submit();
  });
})();
