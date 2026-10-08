"""Caricamento e validazione della configurazione di progetto (config.yaml).

Sostituisce il blocco di variabili "MODIFICABILI" hardcoded nello script
AppleScript originale: ogni progetto ha il suo file YAML e il codice non va mai
toccato. Lo schema riflette la struttura reale del flusso (TODAY_FILES /
DAILY_FILES / dischi di backup), ricostruita dai log del progetto ISIDE.
"""

from __future__ import annotations

import datetime as _dt
import os
from dataclasses import dataclass, field
from typing import List

import yaml


class ConfigError(Exception):
    """Errore di configurazione con messaggio leggibile per l'utente."""


def shoot_date(offset_hours: int) -> str:
    """Data di ripresa in formato yyyymmdd = (adesso - offset_hours).

    Replica il `date -v -<N>H +%Y%m%d` dell'originale: sposta indietro l'orario
    così una copia lanciata dopo mezzanotte usa comunque il giorno di ripresa.
    """
    return (_dt.datetime.now() - _dt.timedelta(hours=offset_hours)).strftime("%Y%m%d")


# Nomi con cui l'app Google Drive può chiamare la radice del drive in CloudStorage.
# Cambia con la lingua dell'app o dopo un aggiornamento/riavvio.
DRIVE_ROOT_NAMES = ("My Drive", "Il mio Drive")


def resolve_drive_path(path: str) -> str:
    """Se `path` non esiste, riprova scambiando il nome della radice di Google Drive.

    La cartella `My Drive` può diventare `Il mio Drive` (e viceversa): il percorso
    nel config smette di funzionare e la scrittura fallisce con "Permission denied"
    perché la radice del mount è in sola lettura. Se nessuna variante esiste,
    ritorna `path` invariato.
    """
    if not path or os.path.exists(path):
        return path
    parts = path.split(os.sep)
    for i, part in enumerate(parts):
        if part in DRIVE_ROOT_NAMES:
            for alt in DRIVE_ROOT_NAMES:
                if alt == part:
                    continue
                candidate = os.sep.join(parts[:i] + [alt] + parts[i + 1:])
                if os.path.exists(candidate):
                    return candidate
            break
    return path


@dataclass
class StillRename:
    """Come costruire il pattern di rinomina still per DaVinci Resolve."""

    prefix: str = ""
    fields: List[str] = field(default_factory=list)
    separator: str = "_"
    day_token: str = "timeline"


@dataclass
class EmailConfig:
    """Bozza email di fine giornata con i report della giornata allegati."""

    enabled: bool = False
    recipients: List[str] = field(default_factory=list)
    subject: str = "Report di giornata {DAY}"
    body: str = ""
    attach_day_reports: bool = True
    attach_report_pdf: bool = True


def parse_recipients(value) -> List[str]:
    """Indirizzi da stringa separata da virgole (o da lista YAML)."""
    if not value:
        return []
    items = value if isinstance(value, list) else str(value).split(",")
    return [str(a).strip() for a in items if str(a).strip()]


def parse_flag(value, default: bool = False) -> bool:
    """Interpreta y/n (e si/no, true/false, 1/0) come booleano."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"y", "yes", "s", "si", "sì", "true", "1"}


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

    # --- Nome DAY ---
    day_hour_offset: int = 6                 # ore da sottrarre per la data di ripresa

    # --- Modalità still ---
    still_default_minutes: int = 5          # default del prompt "ultimi N minuti"
    still_mode: str = "minutes"             # "minutes" (ultimi N min) | "drx" (still con .drx)
    still_delete_drx: bool = True           # elimina i .drx prima della copia
    still_extension: str = ".jpg"           # estensione delle still copiate

    # --- Sicurezza ---
    verify_checksum: bool = True
    write_mhl: bool = True
    check_space: bool = True
    cleanup_spola_folder: bool = True       # rm -rf della cartella spola a fine copia

    # --- Log ---
    log_folder_name: str = "LOGS"           # usato se log_folder non è assoluto

    # --- Scaffolding di inizio film (comando init) ---
    project_folders: List[str] = field(default_factory=list)

    # --- Rinomina still ---
    still_rename: StillRename = field(default_factory=StillRename)

    # --- Email di fine giornata ---
    email: EmailConfig = field(default_factory=EmailConfig)

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
        cleanup = data.get("cleanup", {}) or {}

        if not project.get("film"):
            raise ConfigError("Campo obbligatorio mancante: project.film")

        sr_data = data.get("still_rename", {}) or {}
        still_rename = StillRename(
            prefix=str(sr_data.get("prefix", "")),
            fields=list(sr_data.get("fields", []) or []),
            separator=str(sr_data.get("separator", "_")),
            day_token=str(sr_data.get("day_token", "timeline")),
        )

        em_data = data.get("email", {}) or {}
        email = EmailConfig(
            enabled=parse_flag(em_data.get("invia_email"), False),
            recipients=parse_recipients(em_data.get("mailinglist")),
            subject=str(em_data.get("oggetto", "Report di giornata {DAY}")),
            body=str(em_data.get("testo", "")),
            attach_day_reports=parse_flag(em_data.get("allega_report_giornata"), True),
            attach_report_pdf=parse_flag(em_data.get("allega_report_pdf"), True),
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
            drive_reports=resolve_drive_path(str(paths.get("drive_reports", ""))),
            drive_stills=resolve_drive_path(str(paths.get("drive_stills", ""))),
            reports_subfolder=str(structure.get("reports_subfolder", "03_REPORTS")),
            still_source=str(structure.get("still_source", "05_STILL")),
            files_folders=list(structure.get("files_folders", []) or []),
            spola_prefix=str(spola.get("prefix", "")),
            spola_reports_subfolder=str(spola.get("reports_subfolder", "03_REPORTS")),
            fixed_disks=list(disks.get("fixed_disks", []) or []),
            include_spola_as_disk=bool(disks.get("include_spola", True)),
            day_hour_offset=int(data.get("day_hour_offset", 6)),
            still_default_minutes=int(still_cfg.get("default_minutes", 5)),
            still_mode=str(still_cfg.get("mode", "minutes")).strip().lower(),
            still_delete_drx=bool(still_cfg.get("delete_drx", True)),
            still_extension=str(still_cfg.get("extension", ".jpg")),
            verify_checksum=bool(safety.get("verify_checksum", True)),
            write_mhl=bool(safety.get("write_mhl", True)),
            check_space=bool(safety.get("check_space", True)),
            cleanup_spola_folder=bool(cleanup.get("spola_folder", True)),
            project_folders=list(data.get("project_folders", []) or []),
            still_rename=still_rename,
            email=email,
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
