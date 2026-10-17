"""US-017 (decyzja PO Z-37): hasła kont uprzywilejowanych (Administrator, personel, superużytkownik) ≥ 12 znaków."""

from django.core.exceptions import ValidationError

from .roles import GROUP_ADMIN

MIN_PRIVILEGED = 12


def privileged(user):
    if user is None:
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    return bool(user.pk) and user.groups.filter(name=GROUP_ADMIN).exists()


class PrivilegedPasswordLengthValidator:
    def validate(self, password, user=None):
        if privileged(user) and len(password) < MIN_PRIVILEGED:
            raise ValidationError(f"Hasło konta uprzywilejowanego musi mieć co najmniej {MIN_PRIVILEGED} znaków.",
                                  code="password_too_short_privileged")

    def get_help_text(self):
        return f"Konta Administratorów: co najmniej {MIN_PRIVILEGED} znaków."
