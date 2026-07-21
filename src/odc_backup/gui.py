"""Interazioni native macOS via `osascript`.

Tutte le chiamate a `osascript` sono incapsulate qui, così il resto del codice
non dipende da macOS ed è testabile ovunque (i test mockano queste funzioni).
Replica le finestre native usate dallo script AppleScript originale:
menu di scelta (SPOLA/DAY multipli), alert di errore, notifica finale.
"""

from __future__ import annotations

import subprocess
from typing import List, Optional


class UserCancelled(Exception):
    """L'utente ha annullato una finestra di scelta."""


def _osascript(script: str) -> str:
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # osascript restituisce codice != 0 anche quando l'utente annulla.
        raise UserCancelled(result.stderr.strip() or "Operazione annullata")
    return result.stdout.strip()


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def choose_from_list(options: List[str], prompt: str) -> str:
    """Menu a tendina nativo; ritorna l'opzione scelta o solleva UserCancelled."""
    items = ", ".join(f'"{_escape(o)}"' for o in options)
    script = (
        f'set theChoice to choose from list {{{items}}} '
        f'with prompt "{_escape(prompt)}"\n'
        'if theChoice is false then error number -128\n'
        'return item 1 of theChoice'
    )
    return _osascript(script)


def ask_text(prompt: str, default: str = "") -> str:
    """Finestra di input testo (equivalente di `display dialog ... default answer`)."""
    script = (
        f'set theResult to display dialog "{_escape(prompt)}" '
        f'default answer "{_escape(default)}"\n'
        'return text returned of theResult'
    )
    return _osascript(script)


def display_alert(message: str, title: str = "ODC Backup") -> None:
    script = (
        f'display alert "{_escape(title)}" message "{_escape(message)}" '
        'buttons {"OK"} default button 1'
    )
    try:
        _osascript(script)
    except UserCancelled:
        pass


def display_notification(message: str, title: str = "ODC Backup",
                         subtitle: Optional[str] = None) -> None:
    sub = f' subtitle "{_escape(subtitle)}"' if subtitle else ""
    script = (
        f'display notification "{_escape(message)}" '
        f'with title "{_escape(title)}"{sub}'
    )
    try:
        _osascript(script)
    except UserCancelled:
        pass
