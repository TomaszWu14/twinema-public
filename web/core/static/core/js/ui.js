// US-005: zachowania, które były w atrybutach onclick=/onsubmit=/onchange= (zablokowane przez CSP):
//   data-confirm="pytanie"  — na <form> (przy wysłaniu) albo przycisku/linku (przy kliknięciu)
//   data-autosubmit         — na <select>: zmiana wysyła formularz
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
