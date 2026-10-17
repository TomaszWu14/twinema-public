"""Zadanie kolejki: szkic scenariusza filmu z Claude (T-1) — do 90 s i jedno ponowienie, więc poza żądaniem."""

from . import script_ai
from .models import Presentation
from .script import kpi_facts


def draft_with_ai(p):
    from .views import _replace_shots, model_kpi
    pres = Presentation.objects.select_related("model").get(pk=p["presentation"])
    if not pres.is_draft:
        return {"error": "Prezentacja jest już zatwierdzona — szkic z AI pominięty."}
    try:
        shots, warnings = script_ai.draft_script(kpi_facts(model_kpi(pres.model)))
    except script_ai.ScriptAIError as exc:
        return {"error": str(exc)}
    if not shots:
        return {"error": "Szkic z AI nie zawierał żadnego poprawnego tekstu — obecne teksty bez zmian."}
    _replace_shots(pres, shots)
    return {"count": len(shots), "warnings": warnings}
