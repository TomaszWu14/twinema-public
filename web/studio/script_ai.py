"""Szkic scenariusza z Claude API. Do modelu trafiają WYŁĄCZNIE zdania z `script.kpi_facts`
(zagregowane liczby) — bez nazwy modelu, materiałów, lokalizacji i surowych danych.

Brak ANTHROPIC_API_KEY → `ScriptAIError` z czytelnym komunikatem (funkcja wyłączona, nie 500).
"""
from typing import Literal

import anthropic
from django.conf import settings
from pydantic import BaseModel

from .script import MAX_SHOTS, MIN_SHOTS, PRESETS, TARGET_WORDS, clean_draft

TIMEOUT_S = 90                  # < timeout gunicorna (120 s)

SYSTEM = f"""Jesteś scenarzystą krótkich filmów prezentujących projekty magazynów dla zarządu.
Film nie ma lektora: piszesz po polsku napisy wyświetlane na ekranie — rzeczowo, krótkimi zdaniami,
bez marketingowego żargonu i bez wykrzykników. Widz czyta je, oglądając halę, więc mniej znaczy lepiej.
Film ma {MIN_SHOTS}–{MAX_SHOTS} ujęć i łącznie {TARGET_WORDS[0]}–{TARGET_WORDS[1]} słów (1,5–2,5 minuty).
Każde ujęcie to jeden napis (1–2 krótkie zdania) i jeden ruch kamery:
  przelot — przelot nad halą (otwarcie, kontekst),
  orbita — orbita wokół hali (całość układu, sprzęt),
  przejazd — przejazd nisko wzdłuż alejek (droga, praca wózków),
  plan — plan z góry (pojemność, strefy, powierzchnia),
  ogolny — statyczny widok ogólny (podsumowanie, zamknięcie).
Używaj wyłącznie liczb z podanych faktów, nie wymyślaj nowych i nie podawaj nazw firm ani miejsc.
Liczby zapisuj cyframi z jednostkami, jak w faktach (np. „2 300 miejsc paletowych”, „23 m”)."""


class ShotDraft(BaseModel):
    preset: Literal[PRESETS]
    text: str


class ScriptDraft(BaseModel):
    shots: list[ShotDraft]


class ScriptAIError(Exception):
    """Błąd do pokazania użytkownikowi (bez szczegółów technicznych)."""


def enabled():
    return bool(settings.ANTHROPIC_API_KEY)


def draft_script(facts, client=None):
    """facts: lista zdań z liczbami → (shots, ostrzeżenia). Rzuca ScriptAIError."""
    if not enabled():
        raise ScriptAIError("Szkic z AI wyłączony — ustaw ANTHROPIC_API_KEY w zmiennych serwera.")
    if not facts:
        raise ScriptAIError("Model hali nie ma jeszcze wskaźników (brak regałów) — nie ma o czym opowiadać.")
    client = client or anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=TIMEOUT_S, max_retries=1)
    try:
        resp = client.messages.parse(
            model=settings.CLAUDE_MODEL, max_tokens=8000, system=SYSTEM,
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": "Fakty o projekcie magazynu:\n- " + "\n- ".join(facts)
                       + "\n\nNapisz scenariusz filmu."}],
            output_format=ScriptDraft,
        )
    except anthropic.AuthenticationError as exc:
        raise ScriptAIError("Klucz ANTHROPIC_API_KEY został odrzucony — sprawdź go w zmiennych serwera.") from exc
    except anthropic.RateLimitError as exc:
        raise ScriptAIError("Limit zapytań do Claude — spróbuj ponownie za minutę.") from exc
    except anthropic.APITimeoutError as exc:
        raise ScriptAIError("Claude nie odpowiedział na czas — spróbuj ponownie.") from exc
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
        raise ScriptAIError("Usługa Claude jest chwilowo niedostępna — spróbuj ponownie.") from exc
    if resp.stop_reason == "refusal":
        raise ScriptAIError("Claude odmówił napisania szkicu — napisz teksty ręcznie.")
    if resp.stop_reason == "max_tokens" or resp.parsed_output is None:
        raise ScriptAIError("Szkic z AI przyszedł niekompletny — spróbuj ponownie.")
    return clean_draft([s.model_dump() for s in resp.parsed_output.shots])
