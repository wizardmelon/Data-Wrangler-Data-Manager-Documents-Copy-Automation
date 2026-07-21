"""Caricamento e validazione della configurazione di progetto (config.yaml).

Sostituisce il blocco di variabili "MODIFICABILI" hardcoded nello script
AppleScript originale: ora ogni progetto ha il suo file YAML e il codice non
va mai toccato.
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
    """Come costruire il pattern di rinomina still per DaVinci Resolve.

    L'utente elenca in parole semplici (alias) cosa vuole nel nome; il modulo
    `still` traduce gli alias nei token Resolve `%{...}`. Il token che porta il
    numero DAY viene sempre aggiunto in coda automaticamente (vedi `day_token`).
    """

    prefix: str = ""
    fields: List[str] = field(default_factory=list)
    separator: str = "_"
    day_token: str = "timeline"  # alias del token che contiene "DAY###"


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
    project_root: str = ""         # radice del film: dove `init` crea la struttura
    base_work: str = ""            # cartella con le giornate + i report
    drive: str = ""               # drive condiviso dove va il backup delle still
    destination_still: str = ""    # sottocartella del drive per le still

    # --- Dischi ---
    backup_disks: List[str] = field(default_factory=list)  # nomi volumi in /Volumes
    disc_spola: str = ""           # prefisso del/i disco "spola" (auto-detect)

    # --- Sorgenti ---
    source_folders: List[str] = field(default_factory=list)  # copiate da `files` (estensibile)
    source_still: str = ""         # cartella sorgente delle still

    # --- Log ---
    log_folder_name: str = "SCRIPT LOGS"

    # --- Scaffolding di inizio film (comando init) ---
    project_folders: List[str] = field(default_factory=list)

    # --- Rinomina still ---
    still_rename: StillRename = field(default_factory=StillRename)

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, data: dict) -> "ProjectConfig":
        if not isinstance(data, dict):
            raise ConfigError("Il file di configurazione deve essere un dizionario YAML.")

        project = data.get("project", {}) or {}
        paths = data.get("paths", {}) or {}
        disks = data.get("disks", {}) or {}
        sources = data.get("sources", {}) or {}
        log = data.get("log", {}) or {}

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
            base_work=str(paths.get("base_work", "")),
            drive=str(paths.get("drive", "")),
            destination_still=str(paths.get("destination_still", "")),
            backup_disks=list(disks.get("backup_disks", []) or []),
            disc_spola=str(disks.get("disc_spola", "")),
            source_folders=list(sources.get("folders", []) or []),
            source_still=str(sources.get("still", "")),
            log_folder_name=str(log.get("folder_name", "SCRIPT LOGS")),
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
            except yaml.YAMLError as exc:  # pragma: no cover - dipende dall'input
                raise ConfigError(f"YAML non valido in {path}: {exc}") from exc
        return cls.from_dict(data or {})

    # ------------------------------------------------------------------
    def validate(self) -> None:
        """Controlli minimi di coerenza, con messaggi chiari."""
        if not self.base_work:
            raise ConfigError("Campo obbligatorio mancante: paths.base_work")
        # Le sorgenti/dischi possono essere vuoti in fase di sola inizializzazione,
        # ma per la copia servono: la verifica specifica avviene nei workflow.
