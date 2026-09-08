"""Comando `init`: setup di INIZIO FILM.

Va eseguito una volta sola all'inizio del film. Dato il config e la cartella
radice del progetto, crea l'albero cartelle definito nello YAML
(`project_folders`) — cioè la struttura usata per tutta la produzione (quella in
cui poi vivono `base_work`, le sorgenti, ecc.) — e genera due file di
riferimento pronti da incollare nei software di set:
- `SILVERSTACK_report_path.txt` con la stringa-token del report path;
- `RESOLVE_still_pattern.txt` con il pattern di rinomina still costruito dallo YAML.
"""

from __future__ import annotations

import os
from typing import List, TYPE_CHECKING

from . import still

if TYPE_CHECKING:  # pragma: no cover
    from .config import ProjectConfig

def build_silverstack_report_path(reports_subfolder: str) -> str:
    """Stringa-token del report path da incollare in Silverstack.

    $objectName$, $projectName$, $reportType$ sono token di Silverstack stesso
    (non sostituiti da noi): $objectName$ è il nome del bin (= nome del DAY).
    Il nome della sottocartella dei report DEVE combaciare con quello che il
    resto del progetto si aspetta (`structure.reports_subfolder` /
    `spola.reports_subfolder` nello YAML) — altrimenti Silverstack scrive i
    report in una cartella che `dm-backup files` non trova.
    """
    return f"$objectName$/{reports_subfolder}/$projectName$ $reportType$_$objectName$"


def create_project_structure(config: "ProjectConfig", base: str) -> List[str]:
    """Crea le cartelle elencate in `config.project_folders` dentro `base`.

    `base` è la radice del film; le cartelle create sono la struttura usata per
    tutta la produzione. Ritorna la lista dei percorsi creati (o già esistenti).
    """
    created: List[str] = []
    os.makedirs(base, exist_ok=True)
    for folder in config.project_folders:
        path = os.path.join(base, folder)
        os.makedirs(path, exist_ok=True)
        created.append(path)
    return created


def write_reference_files(config: "ProjectConfig", base: str) -> List[str]:
    """Scrive i file di riferimento per Silverstack e Resolve dentro `base`."""
    written: List[str] = []

    ss_path = os.path.join(base, "SILVERSTACK_report_path.txt")
    report_path = build_silverstack_report_path(config.spola_reports_subfolder)
    with open(ss_path, "w", encoding="utf-8") as fh:
        fh.write(
            "Report path da incollare in Silverstack "
            "($projectName$ e $reportType$ li compila Silverstack):\n\n"
        )
        fh.write(report_path + "\n")
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
    folders = create_project_structure(config, base)
    refs = write_reference_files(config, base)
    return {"base": base, "folders": folders, "references": refs}
