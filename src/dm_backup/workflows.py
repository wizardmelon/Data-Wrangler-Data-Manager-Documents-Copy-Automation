"""Orchestrazione dei comandi: files, still, init, report.

Le funzioni "pure" (costruzione nomi/percorsi, ricerca della cartella DAY) sono
separate e testabili senza macOS. Le funzioni `run_*` legano insieme gui,
diskutils, copyops e log e vanno eseguite sul Mac di set.
"""

from __future__ import annotations

import datetime as _dt
import os
from typing import List, Optional

from . import copyops, diskutils, gui, report, scaffold, still
from .config import ProjectConfig
from .daylog import DayLogger


# ----------------------------------------------------------------------
# Helper puri (testabili)
# ----------------------------------------------------------------------
def build_folder_name(day: str, date: str) -> str:
    """Nome cartella di giornata, es. ('DAY010', '20251122') -> 'DAY010_20251122'."""
    return f"{day}_{date}"


def today_str() -> str:
    return _dt.datetime.now().strftime("%Y%m%d")


def find_day_folder_on_disk(disk_root: str, day: str) -> Optional[str]:
    """Trova sul disco la cartella DAY già esistente (contiene i dailies).

    Match tollerante: una cartella il cui nome contiene il token DAY (es.
    'DAY010'), così eventuali differenze nella data non bloccano.
    """
    if not os.path.isdir(disk_root):
        return None
    day_low = day.lower()
    for name in sorted(os.listdir(disk_root)):
        full = os.path.join(disk_root, name)
        if os.path.isdir(full) and day_low in name.lower():
            return full
    return None


def detect_day_from_stills(source_still: str) -> List[str]:
    """DAY distinti trovati nei nomi dei JPG nella cartella still."""
    if not os.path.isdir(source_still):
        return []
    names = [n for n in os.listdir(source_still) if n.lower().endswith((".jpg", ".jpeg"))]
    return still.find_days(names)


# ----------------------------------------------------------------------
# Selezione DAY (auto con menu, con eventuale fallback manuale)
# ----------------------------------------------------------------------
def resolve_day(config: ProjectConfig, allow_manual: bool = True) -> str:
    days = detect_day_from_stills(config.source_still)
    if len(days) == 1:
        return days[0]
    if len(days) > 1:
        return gui.choose_from_list(days, "Sono stati trovati più DAY. Quale usare?")
    if allow_manual:
        return gui.ask_text("Nessun DAY trovato nelle still. Inserisci il DAY (es. DAY010):")
    raise RuntimeError("Nessun DAY rilevato nelle still.")


# ----------------------------------------------------------------------
# Selezione disco SPOLA
# ----------------------------------------------------------------------
def resolve_spola(config: ProjectConfig, volumes_root: str = diskutils.VOLUMES_ROOT) -> str:
    disks = diskutils.find_spola_disks(config.disc_spola, volumes_root)
    if not disks:
        raise RuntimeError(
            f"Nessun disco SPOLA trovato (prefisso '{config.disc_spola}'). "
            "Verifica che il disco sia montato."
        )
    if len(disks) == 1:
        return disks[0]
    return gui.choose_from_list(disks, "Sono presenti più dischi SPOLA. Quale usare?")


# ----------------------------------------------------------------------
# Comando FILES
# ----------------------------------------------------------------------
def run_files_mode(config: ProjectConfig, volumes_root: str = diskutils.VOLUMES_ROOT) -> None:
    log = DayLogger(config, "files")
    log.write("=== AVVIO modalità FILES ===")

    spola = resolve_spola(config, volumes_root)
    spola_root = diskutils.disk_path(spola, volumes_root)
    log.write(f"Disco SPOLA: {spola}")

    # 1) DAY e nomi
    day = resolve_day(config)
    folder_name = build_folder_name(day, today_str())
    work_dir = os.path.join(config.base_work, folder_name)
    log.write(f"DAY: {day} — cartella di giornata: {folder_name}")

    # 2) Verifica dischi di backup montati E che il DAY esista già su ciascuno
    day_dirs = {}
    for disk in config.backup_disks:
        if not diskutils.disk_mounted(disk, volumes_root):
            msg = f"Disco di backup non montato: {disk}"
            log.write("ERRORE: " + msg)
            gui.display_alert(msg)
            raise SystemExit(1)
        disk_root = diskutils.disk_path(disk, volumes_root)
        existing = find_day_folder_on_disk(disk_root, day)
        if not existing:
            msg = (f"La cartella {day} non esiste su {disk}. "
                   "Disco sbagliato o dailies video/audio non ancora scaricati.")
            log.write("ERRORE: " + msg)
            gui.display_alert(msg)
            raise SystemExit(1)
        day_dirs[disk] = existing

    # 3) Verifica cartella REPORTS nella spola
    report_source = os.path.join(spola_root, "REPORTS")
    if not os.path.isdir(report_source):
        msg = f"La cartella REPORTS non esiste nella spola: {report_source}"
        log.write("ERRORE: " + msg)
        gui.display_alert(msg)
        raise SystemExit(1)

    # 4) Assembla i documenti nella work dir (REPORTS + sorgenti configurate)
    copyops.recreate_folder(work_dir)
    copyops.copy_into(report_source, os.path.join(work_dir, "REPORTS"))
    log.write(f"Copiati {copyops.count_files(report_source)} file da REPORTS")
    for folder in config.source_folders:
        src = os.path.join(config.base_work, folder)
        if not os.path.isdir(src):
            log.write(f"ATTENZIONE: sorgente inesistente, saltata: {folder}")
            continue
        copyops.copy_into(src, os.path.join(work_dir, folder))
        log.write(f"Copiati {copyops.count_files(src)} file da {folder}")

    # 5) Controllo spazio + copia dentro il DAY esistente su ogni disco
    needed = diskutils.dir_size_bytes(work_dir)
    all_verified = True
    for disk, existing_day in day_dirs.items():
        if not diskutils.has_enough_space(existing_day, needed):
            msg = f"Spazio insufficiente su {disk} per {needed} byte."
            log.write("ERRORE: " + msg)
            gui.display_alert(msg)
            raise SystemExit(1)
        copyops.copy_into(work_dir, existing_day)
        copyops.write_mhl(work_dir, os.path.join(existing_day, f"{folder_name}.mhl"))
        result = copyops.verify_copy(work_dir, existing_day)
        if result.ok:
            log.write(f"Verifica OK su {disk}: {result.checked} file")
        else:
            all_verified = False
            log.write(
                f"VERIFICA FALLITA su {disk}: mancanti={len(result.missing)} "
                f"diversi={len(result.mismatched)}"
            )

    # 6) Cancellazioni SOLO se tutte le verifiche sono passate
    if all_verified:
        for folder in config.source_folders:
            src = os.path.join(config.base_work, folder)
            if os.path.isdir(src):
                copyops.recreate_folder(src)
                log.write(f"Svuotata cartella sorgente: {folder}")
        log.write("=== FINE modalità FILES (verifica integrità superata) ===")
        gui.display_notification("Backup documenti completato e verificato.")
    else:
        log.write("=== FINE con ERRORI: sorgenti NON cancellate (verifica fallita) ===")
        gui.display_alert("Verifica integrità fallita: le cartelle sorgente NON sono state svuotate.")
        raise SystemExit(2)

    # 7) Report giornaliero (HTML + PDF)
    try:
        out = report.generate(log.log_file)
        log.write(f"Report generato: {out['html']}" + (f" / {out['pdf']}" if out['pdf'] else ""))
    except Exception as exc:  # pragma: no cover - il report non deve bloccare
        log.write(f"ATTENZIONE: report non generato: {exc}")


# ----------------------------------------------------------------------
# Comando STILL (autodetect DAY sempre attivo)
# ----------------------------------------------------------------------
def run_still_mode(config: ProjectConfig, volumes_root: str = diskutils.VOLUMES_ROOT) -> None:
    log = DayLogger(config, "still")
    log.write("=== AVVIO modalità STILL ===")

    day = resolve_day(config, allow_manual=False)
    log.write(f"DAY rilevato: {day}")

    dest = config.destination_still or os.path.join(config.drive, day)
    os.makedirs(dest, exist_ok=True)

    copyops.copy_into(config.source_still, dest)
    result = copyops.verify_copy(config.source_still, dest)
    if result.ok:
        log.write(f"Still copiate e verificate: {result.checked} file in {dest}")
        gui.display_notification("Copia still completata e verificata.")
    else:
        log.write(f"VERIFICA STILL FALLITA: mancanti={len(result.missing)} diversi={len(result.mismatched)}")
        gui.display_alert("Verifica integrità delle still fallita.")
        raise SystemExit(2)


# ----------------------------------------------------------------------
# Comando INIT
# ----------------------------------------------------------------------
def run_init(config: ProjectConfig, base: str) -> dict:
    return scaffold.run(config, base)


# ----------------------------------------------------------------------
# Comando REPORT (rigenera da un log esistente)
# ----------------------------------------------------------------------
def run_report(log_path: str) -> dict:
    return report.generate(log_path)
