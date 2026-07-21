"""Log giornaliero con intestazione automatica.

Replica la funzione `writeLog` dell'originale: un file di testo al giorno dentro
la cartella `SCRIPT LOGS` di `base_work`, con intestazione (crediti di progetto)
scritta una sola volta e righe nel formato `[what --> timestamp] messaggio`.
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from .config import ProjectConfig


class DayLogger:
    def __init__(self, config: "ProjectConfig", what: str, date: str | None = None):
        self.config = config
        self.what = what
        self.date = date or _dt.datetime.now().strftime("%Y%m%d")
        self.log_dir = os.path.join(config.base_work, config.log_folder_name)
        self.log_file = os.path.join(self.log_dir, f"backupScript_log_{self.date}.txt")

    # ------------------------------------------------------------------
    def _header(self) -> str:
        c = self.config
        lines = [
            "LOG - BackUp file giornalieri - Python - v2.0",
            "",
            f"{c.film} - {self.date}",
            f"Produzione - {c.prod}",
            f"Regia - {c.regia}",
            f"Fotografia - {c.dop}",
            f"DIT - {c.dit}",
            f"Data Manager - {c.dmanager}",
            "",
        ]
        return "\n".join(lines)

    def _ensure_header(self) -> None:
        os.makedirs(self.log_dir, exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, "w", encoding="utf-8") as fh:
                fh.write(self._header())

    # ------------------------------------------------------------------
    def write(self, message: str) -> None:
        self._ensure_header()
        ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.log_file, "a", encoding="utf-8") as fh:
            fh.write(f"[{self.what} --> {ts}] {message}\n")
