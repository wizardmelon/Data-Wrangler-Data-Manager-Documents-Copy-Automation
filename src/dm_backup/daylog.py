"""Log giornaliero con intestazione automatica.

Replica la funzione `writeLog` dell'originale: un file di testo al giorno con
intestazione (crediti di progetto) scritta una sola volta e righe nel formato
`[what --> timestamp] messaggio`, più i marcatori START/END come nei log reali.
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import TYPE_CHECKING

from .config import shoot_date

if TYPE_CHECKING:  # pragma: no cover
    from .config import ProjectConfig

_SEP = "-----------------------------------------------------------------------------------"
_END_SEP = "------------------------------------------------------"


class DayLogger:
    def __init__(self, config: "ProjectConfig", what: str, date: str | None = None):
        self.config = config
        self.what = what
        # Data di ripresa (adesso - offset): tiene insieme nello stesso file di
        # log anche i run lanciati dopo mezzanotte.
        self.date = date or shoot_date(config.day_hour_offset)
        self.log_dir = config.log_dir
        self.log_file = os.path.join(self.log_dir, f"backupScript_log_{self.date}.txt")

    # ------------------------------------------------------------------
    def _header(self) -> str:
        c = self.config
        lines = [
            "LOG - BackUp file giornalieri - Python - v2.0",
            "",
            f"{c.film} - {self.date}",
            "",
            f"Produzione - {c.prod}",
            f"Regia - {c.regia}",
            f"Fotografia - {c.dop}",
            f"DIT - {c.dit}",
            f"Data Manager - {c.dmanager}",
            "",
            "",
        ]
        return "\n".join(lines)

    def _ensure_header(self) -> None:
        os.makedirs(self.log_dir, exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", encoding="utf-8") as fh:
                fh.write(self._header())

    def _raw(self, line: str) -> None:
        self._ensure_header()
        with open(self.log_file, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    # ------------------------------------------------------------------
    def write(self, message: str) -> None:
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._raw(f"[{self.what} --> {ts}] {message}")

    def start(self) -> None:
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._raw(f"[START {self.what} --> {ts}] {_SEP}")

    def end(self) -> None:
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._raw("")
        self._raw(f"[END --> {ts}] {_END_SEP}")
        self._raw(f"[END --> {ts}] Chiusura dello script.")
        self._raw(f"[END --> {ts}] {_END_SEP}")
        self._raw("")
