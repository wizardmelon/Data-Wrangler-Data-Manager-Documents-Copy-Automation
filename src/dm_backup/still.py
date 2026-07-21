"""Costruzione del pattern di rinomina still per DaVinci Resolve.

L'utente scrive nello YAML, in parole semplici (alias), cosa vuole nel nome del
file; questo modulo traduce gli alias nei token Resolve `%{...}` e assembla la
stringa pronta da incollare nella pagina Deliver ("File name uses: Custom name").

Il token che porta il numero DAY (di default il Timeline Name, es. "DAY010")
viene sempre aggiunto in coda AUTOMATICAMENTE: non va elencato dall'utente,
perché serve alla modalità `still` per ritrovare la cartella DAY. Dalla stessa
configurazione deriviamo anche la regex per estrarre "DAY###" dai nomi file,
così pattern di export e logica di lettura restano sempre coerenti.
"""

from __future__ import annotations

import re
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .config import StillRename

# Alias amichevoli -> token DaVinci Resolve (pagina Deliver).
# Estendibile: aggiungere una voce qui rende l'alias subito usabile nello YAML.
ALIAS_TO_TOKEN: Dict[str, str] = {
    "scena": "%{Scene}",
    "scene": "%{Scene}",
    "clip": "%{Clip Name}",
    "clipname": "%{Clip Name}",
    "timeline": "%{Timeline Name}",
    "reel": "%{Reel Name}",
    "shot": "%{Shot}",
    "take": "%{Take}",
    "camera": "%{Camera #}",
    "roll": "%{Camera Roll}",
    "program": "%{Program Name}",
}

# Pattern del numero DAY: "DAY" seguito da cifre (es. DAY010).
DAY_REGEX = re.compile(r"DAY\d+", re.IGNORECASE)


class StillPatternError(Exception):
    """Alias non riconosciuto o configurazione still non valida."""


def _token_for(alias: str) -> str:
    key = alias.strip().lower().replace(" ", "").replace("_", "")
    if key not in ALIAS_TO_TOKEN:
        valid = ", ".join(sorted(set(ALIAS_TO_TOKEN)))
        raise StillPatternError(
            f"Alias sconosciuto per la rinomina still: '{alias}'. "
            f"Alias validi: {valid}"
        )
    return ALIAS_TO_TOKEN[key]


def build_resolve_pattern(still_rename: "StillRename") -> str:
    """Assembla il pattern `%{...}` da incollare in Resolve.

    Struttura: <prefix><campo1><sep><campo2>...<sep><token DAY in coda>.
    """
    sep = still_rename.separator or "_"
    parts: List[str] = [_token_for(f) for f in still_rename.fields]

    day_token = _token_for(still_rename.day_token)
    # Il token DAY va sempre in coda; se l'utente lo avesse già messo tra i
    # campi, non lo duplichiamo.
    if not parts or parts[-1] != day_token:
        parts.append(day_token)

    body = sep.join(parts)
    return f"{still_rename.prefix}{body}"


def day_regex() -> "re.Pattern[str]":
    """Regex per estrarre il numero DAY dai nomi file esportati."""
    return DAY_REGEX


def find_days(filenames: List[str]) -> List[str]:
    """DAY distinti trovati nei nomi file (upper-case, ordinati)."""
    found = set()
    for name in filenames:
        m = DAY_REGEX.search(name)
        if m:
            found.add(m.group(0).upper())
    return sorted(found)
