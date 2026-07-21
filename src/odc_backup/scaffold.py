"""Comando `init`: scaffolding delle cartelle di giornata/progetto.

Dato il config e una cartella base, crea l'albero cartelle definito nello YAML
(`day_folders`) e genera due file di riferimento pronti da incollare nei
software di set:
- `SILVERSTACK_report_path.txt` con la stringa-token del report path;
- `RESOLVE_still_pattern.txt` con il pattern di rinomina still costruito dallo YAML.
"""

from __future__ import annotations

import os
from typing import List, TYPE_CHECKING

from . import still

if TYPE_CHECKING:  # pragma: no cover
    from .config import ProjectConfig

# Report path per Silverstack: stringa LETTERALE. $projectName$ è definito da
# Silverstack stesso, quindi non viene sostituito da noi.
SILVERSTACK_REPORT_PATH = "objectName$/REPORTS/$projectName$ $reportType$_$objectName$"


def create_day_structure(config: "ProjectConfig", base: str) -> List[str]:
    """Crea le cartelle elencate in `config.day_folders` dentro `base`.

    Ritorna la lista dei percorsi creati (o già esistenti).
    """
    created: List[str] = []
    os.makedirs(base, exist_ok=True)
    for folder in config.day_folders:
        path = os.path.join(base, folder)
        os.makedirs(path, exist_ok=True)
        created.append(path)
    return created


def write_reference_files(config: "ProjectConfig", base: str) -> List[str]:
    """Scrive i file di riferimento per Silverstack e Resolve dentro `base`."""
    written: List[str] = []

    ss_path = os.path.join(base, "SILVERSTACK_report_path.txt")
    with open(ss_path, "w", encoding="utf-8") as fh:
        fh.write(
            "Report path da incollare in Silverstack "
            "($projectName$ lo compila Silverstack):\n\n"
        )
        fh.write(SILVERSTACK_REPORT_PATH + "\n")
    written.append(ss_path)

    pattern = still.build_resolve_pattern(config.still_rename)
    rp_path = os.path.join(base, "RESOLVE_still_pattern.txt")
    with open(rp_path, "w", encoding="utf-8") as fh:
        fh.write(
            "Pattern da incollare in DaVinci Resolve "
            "(Deliver > File name uses: Custom name):\n\n"
        )
        fh.write(pattern + "\n")
    written.append(rp_path)

    return written


def run(config: "ProjectConfig", base: str) -> dict:
    """Esegue lo scaffolding completo e ritorna un riepilogo."""
    folders = create_day_structure(config, base)
    refs = write_reference_files(config, base)
    return {"base": base, "folders": folders, "references": refs}
