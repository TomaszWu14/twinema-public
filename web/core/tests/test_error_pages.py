"""US-020: własne strony „nie znaleziono” i „błąd serwera” zamiast standardowych stron Django."""
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase
from django.views.defaults import server_error


class ErrorPagesTests(TestCase):
    def test_expired_public_link_explains_what_happened(self):
        r = self.client.get("/p/nieistniejacy-klucz/")
        self.assertEqual(r.status_code, 404)
        self.assertContains(r, "mógł wygasnąć albo zostać wyłączony", status_code=404)
        self.assertContains(r, "Przejdź do logowania", status_code=404)

    def test_logged_user_gets_way_back_home(self):
        self.client.force_login(User.objects.create_superuser("a", "a@x.pl", "x"))
        r = self.client.get("/magazyn/model/999999/view/")
        self.assertContains(r, "Nie znaleziono strony", status_code=404)
        self.assertContains(r, "Wróć na start", status_code=404)

    def test_server_error_page_renders_without_request_context(self):
        r = server_error(RequestFactory().get("/"))
        self.assertEqual(r.status_code, 500)
        self.assertIn("Coś poszło nie tak", r.content.decode())
