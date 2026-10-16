from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="core/login.html",
                                                redirect_authenticated_user=True), name="login"),
    path("demo/", views.demo, name="demo"),
    path("demo/wejdz/", views.demo_enter, name="demo_enter"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dziennik/", views.audit_log, name="audit_log"),
    path("2fa/", views.two_factor_verify, name="two_factor_verify"),
    path("2fa/konfiguracja/", views.two_factor_setup, name="two_factor_setup"),
    path("zadania/<int:pk>/stan/", views.job_status, name="job_status"),
]
