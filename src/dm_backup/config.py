"""Caricamento e validazione della configurazione di progetto (config.yaml).

Sostituisce il blocco di variabili "MODIFICABILI" hardcoded nello script
AppleScript originale: ogni progetto ha il suo file YAML e il codice non va mai
toccato. Lo schema riflette la struttura reale del flusso (TODAY_FILES /
DAILY_FILES / dischi di backup), ricostruita dai log del progetto ISIDE.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

import yaml


class ConfigError(Exception):
    """Errore di configurazione con messaggio leggibile per l'utente."""


@dataclass
class StillRename:
    """Come costruire il pattern di rinomina still per DaVinci Resolve."""

    prefix: str = ""
    fields: List[str] = field(default_factory=list)
    separator: str = "_"
    day_token: str = "timeline"


@dataclass
class ProjectConfig:
    """Configurazione completa di un progetto."""

    # --- Crediti / intestazione del log ---
    film: str
    prod: str = ""
    regia: str = ""
    dop: str = ""
    dit: str = ""
    dmanager: str = ""

    # --- Percorsi principali ---
    project_root: str = ""     # radice del film (dove `init` crea la struttura)
    today_files: str = ""      # cartella di lavoro della giornata
    daily_files: str = ""      # dove Silverstack crea il DAY master + report spola
    log_folder: str = ""       # dove salvare i log (default: <project_root>/LOGS)
    drive_reports: str = ""    # cartella Drive per i report (si appende il DAY)
    drive_stills: str = ""     # cartella Drive per le still (si appende il DAY)

    # --- Struttura interna (relativa a today_files/daily_files) ---
    reports_subfolder: str = "03_REPORTS"   # sottocartella report nel DAY master
    still_source: str = "05_STILL"          # sorgente still (in today_files)
    files_folders: List[str] = field(default_factory=list)  # copiate da `files`

    # --- Spola ---
    spola_prefix: str = ""                  # prefisso del volume/cartella spola
    spola_reports_subfolder: str = "03_REPORTS"  # report spola: daily/<spola>/<qui>

    # --- Dischi di destinazione ---
    fixed_disks: List[str] = field(default_factory=list)  # sempre destinazioni
    include_spola_as_disk: bool = True      # la spola è anche destinazione

    # --- Modalità still ---
    still_default_minutes: int = 5          # default del prompt "ultimi N minuti"
    still_delete_drx: bool = True           # elimina i .drx prima della copia

    # --- Sicurezza ---
    verify_checksum: bool = True
    write_mhl: bool = True
    check_space: bool = True

    # --- Log ---
    log_folder_name: str = "LOGS"           # usato se log_folder non è assoluto

    # --- Scaffolding di inizio film (comando init) ---
    project_folders: List[str] = field(default_factory=list)

    # --- Rinomina still ---
    still_rename: StillRename = field(default_factory=StillRename)

    # ------------------------------------------------------------------
    @property
    def log_dir(self) -> str:
        if self.log_folder:
            return self.log_folder
        return os.path.join(self.project_root or self.daily_files, self.log_folder_name)

    @property
    def still_source_path(self) -> str:
        return os.path.join(self.today_files, self.still_source)

    def files_folder_paths(self) -> List[str]:
        return [os.path.join(self.today_files, f) for f in self.files_folders]

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        if not isinstance(data, dict):
            raise ConfigError("Il file di configurazione deve essere un dizionario YAML.")

        project = data.get("project", {}) or {}
        paths = data.get("paths", {}) or {}
        structure = data.get("structure", {}) or {}
        spola = data.get("spola", {}) or {}
        disks = data.get("disks", {}) or {}
        still_cfg = data.get("still", {}) or {}
        safety = data.get("safety", {}) or {}

        if not project.get("film"):
            raise ConfigError("Campo obbligatorio mancante: project.film")

        sr_data = data.get("still_rename", {}) or {}
        still_rename = StillRename(
            prefix=str(sr_data.get("prefix", "")),
            fields=list(sr_data.get("fields", []) or []),
            separator=str(sr_data.get("separator", "_")),
            day_token=str(sr_data.get("day_token", "timeline")),
        )

        cfg = cls(
            film=str(project["film"]),
            prod=str(project.get("prod", "")),
            regia=str(project.get("regia", "")),
            dop=str(project.get("dop", "")),
            dit=str(project.get("dit", "")),
            dmanager=str(project.get("dmanager", "")),
            project_root=str(paths.get("project_root", "")),
            today_files=str(paths.get("today_files", "")),
            daily_files=str(paths.get("daily_files", "")),
            log_folder=str(paths.get("log_folder", "")),
            drive_reports=str(paths.get("drive_reports", "")),
            drive_stills=str(paths.get("drive_stills", "")),
            reports_subfolder=str(structure.get("reports_subfolder", "03_REPORTS")),
            still_source=str(structure.get("still_source", "05_STILL")),
            files_folders=list(structure.get("files_folders", []) or []),
            spola_prefix=str(spola.get("prefix", "")),
            spola_reports_subfolder=str(spola.get("reports_subfolder", "03_REPORTS")),
            fixed_disks=list(disks.get("fixed_disks", []) or []),
            include_spola_as_disk=bool(disks.get("include_spola", True)),
            still_default_minutes=int(still_cfg.get("default_minutes", 5)),
            still_delete_drx=bool(still_cfg.get("delete_drx", True)),
            verify_checksum=bool(safety.get("verify_checksum", True)),
            write_mhl=bool(safety.get("write_mhl", True)),
            check_space=bool(safety.get("check_space", True)),
            project_folders=list(data.get("project_folders", []) or []),
            still_rename=still_rename,
        )
        cfg.validate()
        return cfg

    @classmethod
    def load(cls, path: str) -> "ProjectConfig":
        if not os.path.isfile(path):
            raise ConfigError(f"File di configurazione non trovato: {path}")
        with open(path, "r", encoding="utf-8") as fh:
            try:
                data = yaml.safe_load(fh)
            except yaml.YAMLError as exc:  # pragma: no cover
                raise ConfigError(f"YAML non valido in {path}: {exc}") from exc
        return cls.from_dict(data or {})

    # ------------------------------------------------------------------
    def validate(self) -> None:
        """Controlli minimi; i requisiti specifici sono verificati nei workflow."""
        if not self.project_root and not self.daily_files:
            raise ConfigError(
                "Serve almeno paths.project_root o paths.daily_files."
            )
