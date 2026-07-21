"""Orchestrazione dei comandi: files, still, init, report.

Il flusso replica quello reale ricostruito dai log del progetto ISIDE:

FILES:
  1. rileva la cartella DAY master in DAILY_FILES (creata da Silverstack)
  2. rileva la spola (volume montato con prefisso configurato)
  3. copia i report della spola  -> DAY_master/REPORTS
  4. copia i report            -> Drive/REPORTS/<DAY>
  5. copia le cartelle sorgente da TODAY_FILES -> DAY_master
  6. copia il DAY_master DENTRO il DAY già esistente su ogni disco
     (dischi fissi + spola), con verifica checksum, MHL e controllo spazio
  7. svuota le cartelle di TODAY_FILES SOLO se la verifica è ok su tutti i dischi

STILL:
  1. rileva il DAY
  2. elimina i .drx dalla sorgente still
  3. copia sul Drive solo le still degli ultimi N minuti (prompt)

Le funzioni "pure" (rilevamento DAY, costruzione nomi) sono separate e testabili
senza macOS.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

from . import copyops, diskutils, gui, report, scaffold
from .config import ProjectConfig
from .daylog import DayLogger

# Nome cartella DAY master: es. "DAY023_20260525" (DAY + numero + _ + data ripresa).
_DAY_FOLDER_RE = re.compile(r"^DAY\d+_\d{6,8}$", re.IGNORECASE)
_DAY_NUM_RE = re.compile(r"DAY(\d+)", re.IGNORECASE)


# ----------------------------------------------------------------------
# Helper puri (testabili)
# ----------------------------------------------------------------------
def list_day_folders(daily_files: str) -> List[str]:
    """Cartelle DAY master presenti in DAILY_FILES (create da Silverstack)."""
    if not os.path.isdir(daily_files):
        return []
    return sorted(
        name for name in os.listdir(daily_files)
        if os.path.isdir(os.path.join(daily_files, name)) and _DAY_FOLDER_RE.match(name)
    )


def day_number(day_folder_name: str) -> str:
    m = _DAY_NUM_RE.search(day_folder_name)
    return m.group(1) if m else ""


def find_day_folder_on_disk(disk_root: str, day_num: str) -> Optional[str]:
    """Trova sul disco la cartella DAY già esistente (contiene i dailies).

    Match tollerante: cartella il cui nome contiene 'DAY<num>' (stesso numero).
    """
    if not os.path.isdir(disk_root):
        return None
    token = f"day{day_num}".lower()
    for name in sorted(os.listdir(disk_root)):
        full = os.path.join(disk_root, name)
        if os.path.isdir(full) and token in name.lower():
            return full
    return None


def detect_day_from_stills(source_still: str) -> List[str]:
    """Numeri DAY distinti dai nomi dei file nella cartella still."""
    if not os.path.isdir(source_still):
        return []
    nums = set()
    for name in os.listdir(source_still):
        m = _DAY_NUM_RE.search(name)
        if m:
            nums.add(m.group(1))
    return sorted(nums)


# ----------------------------------------------------------------------
# Rilevamento DAY master e spola (con menu se multipli)
# ----------------------------------------------------------------------
def resolve_master_day(config: ProjectConfig) -> Tuple[str, str]:
    """Ritorna (nome_cartella_DAY, numero_DAY) rilevando il DAY in DAILY_FILES.

    NB: la cartella la crea Silverstack (= nome del bin) e il suo nome contiene
    la data di RIPRESA, non quella odierna: per questo va rilevata, non costruita.
    """
    folders = list_day_folders(config.daily_files)
    if not folders:
        raise RuntimeError(
            f"Nessuna cartella DAY trovata in {config.daily_files}. "
            "Crea prima il DAY in Silverstack."
        )
    chosen = folders[0] if len(folders) == 1 else gui.choose_from_list(
        folders, "Più cartelle DAY trovate. Quale usare?"
    )
    return chosen, day_number(chosen)


def resolve_spola(config: ProjectConfig, volumes_root: str = diskutils.VOLUMES_ROOT) -> str:
    disks = diskutils.find_spola_disks(config.spola_prefix, volumes_root)
    if not disks:
        raise RuntimeError(
            f"Nessuna spola trovata (prefisso '{config.spola_prefix}'). "
            "Verifica che il disco sia montato."
        )
    if len(disks) == 1:
        return disks[0]
    return gui.choose_from_list(disks, "Più spole montate. Quale usare?")


# ----------------------------------------------------------------------
# Comando FILES
# ----------------------------------------------------------------------
def run_files_mode(config: ProjectConfig, volumes_root: str = diskutils.VOLUMES_ROOT) -> None:
    log = DayLogger(config, "files")
    log.start()

    spola = resolve_spola(config, volumes_root)
    log.write(f"Spola trovata: {spola}")

    day_name, day_num = resolve_master_day(config)
    log.write(f"Day trovato: {day_num} (cartella {day_name})")

    master = os.path.join(config.daily_files, day_name)
    reports_dir = os.path.join(master, config.reports_subfolder)

    # 1) Report della spola -> DAY_master/REPORTS
    spola_reports = os.path.join(config.daily_files, spola, config.spola_reports_subfolder)
    if os.path.isdir(spola_reports):
        copyops.copy_into(spola_reports, reports_dir)
        log.write(f"{copyops.count_files(spola_reports)} report spola copiati in {reports_dir}")
    else:
        log.write(f"ATTENZIONE: report spola non trovati in {spola_reports}")

    # 2) Report -> Drive/REPORTS/<DAY>
    if config.drive_reports:
        drive_reports_dest = os.path.join(config.drive_reports, day_name)
        copyops.copy_into(reports_dir, drive_reports_dest)
        log.write(f"{copyops.count_files(reports_dir)} report copiati su Drive: {drive_reports_dest}")

    # 3) Cartelle sorgente da TODAY_FILES -> DAY_master
    for folder in config.files_folders:
        src = os.path.join(config.today_files, folder)
        if not os.path.isdir(src):
            log.write(f"ATTENZIONE: sorgente inesistente, saltata: {folder}")
            continue
        copyops.copy_into(src, os.path.join(master, folder))
        log.write(f"{copyops.count_files(src)} file copiati da {folder} a {day_name}")

    # 4) Destinazioni = dischi fissi (+ spola)
    destinations = list(config.fixed_disks)
    if config.include_spola_as_disk and spola not in destinations:
        destinations.append(spola)

    needed = diskutils.dir_size_bytes(master)
    all_verified = True
    for disk in destinations:
        if not diskutils.disk_mounted(disk, volumes_root):
            _fail(log, f"Disco non montato: {disk}")
        disk_root = diskutils.disk_path(disk, volumes_root)
        disk_day = find_day_folder_on_disk(disk_root, day_num)
        if not disk_day:
            _fail(log, f"La cartella DAY{day_num} non esiste su {disk}. "
                       "Disco sbagliato o dailies video/audio non ancora scaricati.")
        if config.check_space and not diskutils.has_enough_space(disk_day, needed):
            _fail(log, f"Spazio insufficiente su {disk} per {needed} byte.")

        copyops.copy_into(master, disk_day)
        if config.write_mhl:
            copyops.write_mhl(master, os.path.join(disk_day, f"{day_name}.mhl"))
        if config.verify_checksum:
            result = copyops.verify_copy(master, disk_day)
            if result.ok:
                log.write(f"Verifica OK su {disk}: {result.checked} file")
            else:
                all_verified = False
                log.write(f"VERIFICA FALLITA su {disk}: "
                          f"mancanti={len(result.missing)} diversi={len(result.mismatched)}")
        else:
            log.write(f"Copia completata su {disk} (verifica disattivata)")

    # 5) Pulizia TODAY: solo se tutte le verifiche sono passate
    if all_verified:
        for folder in config.files_folders:
            src = os.path.join(config.today_files, folder)
            if os.path.isdir(src):
                copyops.recreate_folder(src)
                log.write(f"{src} eliminata e ricreata vuota.")
        gui.display_notification("Backup documenti completato e verificato.")
    else:
        gui.display_alert("Verifica integrità fallita: le cartelle TODAY NON sono state svuotate.")
        log.end()
        raise SystemExit(2)

    # 6) Report giornaliero (HTML + PDF)
    _try_report(log)
    log.end()


# ----------------------------------------------------------------------
# Comando STILL
# ----------------------------------------------------------------------
def run_still_mode(config: ProjectConfig, volumes_root: str = diskutils.VOLUMES_ROOT) -> None:
    log = DayLogger(config, "still")
    log.start()

    # DAY: prima prova dal master in DAILY_FILES, poi dai nomi delle still.
    try:
        day_name, day_num = resolve_master_day(config)
    except RuntimeError:
        nums = detect_day_from_stills(config.still_source_path)
        if not nums:
            _fail(log, "Nessun DAY rilevato (né in DAILY_FILES né dalle still).")
        if len(nums) == 1:
            day_num = nums[0]
        else:
            day_num = gui.choose_from_list(
                [f"DAY{n}" for n in nums], "Più DAY trovati. Quale usare?"
            ).replace("DAY", "")
        day_name = f"DAY{day_num}"
    log.write(f"Day trovato: {day_num}")

    src = config.still_source_path

    # Elimina i .drx dalla sorgente still.
    if config.still_delete_drx:
        copyops.delete_by_extension(src, ".drx")
        log.write(f"DRX eliminate dalla cartella {src}")

    # Prompt: ultimi N minuti.
    minutes_raw = gui.ask_text("Inserisci MIN da export:", str(config.still_default_minutes))
    try:
        minutes = int(minutes_raw)
    except ValueError:
        minutes = config.still_default_minutes
    log.write(f"Selezionati {minutes} minuti di file da copiare.")

    dest = os.path.join(config.drive_stills, day_name)
    copied = copyops.copy_recent_files(src, dest, minutes)
    log.write(f"Inizio copia di {len(copied)} still da {src} a {dest}")

    if config.verify_checksum and copied:
        result = copyops.verify_files(src, dest, copied)
        if not result.ok:
            gui.display_alert("Verifica integrità delle still fallita.")
            log.write(f"VERIFICA STILL FALLITA: mancanti={len(result.missing)} "
                      f"diversi={len(result.mismatched)}")
            log.end()
            raise SystemExit(2)

    log.write(f"{len(copied)} still copiate in {dest}")
    gui.display_notification("Copia still completata.")
    log.end()


# ----------------------------------------------------------------------
# Comando INIT / REPORT
# ----------------------------------------------------------------------
def run_init(config: ProjectConfig, base: str) -> dict:
    return scaffold.run(config, base)


def run_report(log_path: str) -> dict:
    return report.generate(log_path)


# ----------------------------------------------------------------------
# Utility interne
# ----------------------------------------------------------------------
def _fail(log: DayLogger, message: str) -> None:
    log.write("ERRORE: " + message)
    gui.display_alert(message)
    log.end()
    raise SystemExit(1)


def _try_report(log: DayLogger) -> None:
    try:
        out = report.generate(log.log_file)
        log.write(f"Report generato: {out['html']}" + (f" / {out['pdf']}" if out["pdf"] else ""))
    except Exception as exc:  # pragma: no cover - il report non deve bloccare
        log.write(f"ATTENZIONE: report non generato: {exc}")
