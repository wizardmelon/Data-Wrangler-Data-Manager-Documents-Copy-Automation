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
     oppure (modo --drx) tutte le still con un .drx omonimo, individuate
     PRIMA di eliminare i .drx

Le funzioni "pure" (rilevamento DAY, costruzione nomi) sono separate e testabili
senza macOS.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import List, Optional

from . import copyops, diskutils, gui, mailer, report, scaffold
from .config import ProjectConfig, shoot_date
from .daylog import DayLogger

# Numero DAY nei nomi file: "DAY" seguito da cifre (es. DAY023 -> "023").
_DAY_NUM_RE = re.compile(r"DAY(\d+)", re.IGNORECASE)


# ----------------------------------------------------------------------
# Helper puri (testabili)
# ----------------------------------------------------------------------
def build_folder_name(day_num: str, offset_hours: int) -> str:
    """Costruisce il nome cartella DAY come l'originale: DAY<num>_<data-ripresa>.

    Es. ('023', 6) -> 'DAY023_20260525'. La data è (adesso - offset ore).
    """
    return f"DAY{day_num}_{shoot_date(offset_hours)}"


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
# Rilevamento numero DAY (dalle still) e spola (con menu se multipli)
# ----------------------------------------------------------------------
def resolve_day_number(config: ProjectConfig) -> str:
    """Numero DAY, rilevato dai nomi dei jpg nella cartella still (come l'originale).

    Una still: usa quello. Più DAY: menu. Nessuno: chiede a mano ("Inserisci DAY:").
    Le still vengono esportate più volte al giorno, prima che esistano i report:
    per questo il DAY si legge da lì e la cartella si costruisce, non si rileva.
    """
    nums = detect_day_from_stills(config.still_source_path)
    if len(nums) == 1:
        return nums[0]
    if len(nums) > 1:
        choice = gui.choose_from_list([f"DAY{n}" for n in nums],
                                      "Più DAY trovati nelle still. Quale usare?")
        return re.sub(r"\D", "", choice)
    manual = gui.ask_text(
        "Nessun jpg con 'DAY###' nella cartella still. Inserisci DAY:")
    return re.sub(r"\D", "", manual)


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


def resolve_fixed_disk(name: str, volumes_root: str = diskutils.VOLUMES_ROOT) -> str:
    """Risolve il nome reale di un disco fisso montato.

    Match esatto se possibile; altrimenti per prefisso/contenuto (come la
    spola), per tollerare nomi con suffisso variabile giorno per giorno
    (es. "TQCC_Work01", "TQCC_Work02", ... configurato come "TQCC_Work0").
    """
    if diskutils.disk_mounted(name, volumes_root):
        return name
    matches = diskutils.find_spola_disks(name, volumes_root)
    if not matches:
        raise RuntimeError(f"Disco non montato: {name}")
    if len(matches) == 1:
        return matches[0]
    return gui.choose_from_list(matches, f"Più dischi trovati per '{name}'. Quale usare?")


# ----------------------------------------------------------------------
# Comando FILES
# ----------------------------------------------------------------------
def run_files_mode(config: ProjectConfig, volumes_root: str = diskutils.VOLUMES_ROOT) -> None:
    log = DayLogger(config, "files")
    log.start()

    spola = resolve_spola(config, volumes_root)
    log.write(f"Spola trovata: {spola}")

    day_num = resolve_day_number(config)
    day_name = build_folder_name(day_num, config.day_hour_offset)
    log.write(f"Day trovato: {day_num} (cartella {day_name})")

    master = os.path.join(config.daily_files, day_name)
    os.makedirs(master, exist_ok=True)
    reports_dir = os.path.join(master, config.reports_subfolder)

    # 1) Report della spola -> DAY_master/REPORTS (stop se mancano, come l'originale)
    spola_folder = os.path.join(config.daily_files, spola)
    spola_reports = os.path.join(spola_folder, config.spola_reports_subfolder)
    if not os.path.isdir(spola_reports):
        _fail(log, f"La cartella REPORT della spola non esiste: {spola_reports}")
    copyops.copy_into(spola_reports, reports_dir)
    log.write(f"{copyops.count_files(spola_reports)} report spola copiati in {reports_dir}")

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
        try:
            resolved_disk = resolve_fixed_disk(disk, volumes_root)
        except RuntimeError as exc:
            _fail(log, str(exc))
        if resolved_disk != disk:
            log.write(f"Disco '{disk}' risolto come '{resolved_disk}' (match per prefisso)")

        disk_root = diskutils.disk_path(resolved_disk, volumes_root)
        disk_day = find_day_folder_on_disk(disk_root, day_num)
        if not disk_day:
            _fail(log, f"La cartella DAY{day_num} non esiste su {resolved_disk}. "
                       "Disco sbagliato o dailies video/audio non ancora scaricati.")
        if config.check_space and not diskutils.has_enough_space(disk_day, needed):
            _fail(log, f"Spazio insufficiente su {resolved_disk} per {needed} byte.")

        copyops.copy_into(master, disk_day)
        if config.write_mhl:
            copyops.write_mhl(master, os.path.join(disk_day, f"{day_name}.mhl"))
        if config.verify_checksum:
            result = copyops.verify_copy(master, disk_day)
            if result.ok:
                log.write(f"Verifica OK su {resolved_disk}: {result.checked} file")
            else:
                all_verified = False
                log.write(f"VERIFICA FALLITA su {resolved_disk}: "
                          f"mancanti={len(result.missing)} diversi={len(result.mismatched)}")
        else:
            log.write(f"Copia completata su {resolved_disk} (verifica disattivata)")

    # 5) Pulizia: solo se tutte le verifiche sono passate
    if all_verified:
        for folder in config.files_folders:
            src = os.path.join(config.today_files, folder)
            if os.path.isdir(src):
                copyops.recreate_folder(src)
                log.write(f"{src} eliminata e ricreata vuota.")
        # Cancella la cartella della spola in DAILY_FILES (report già spostato).
        if config.cleanup_spola_folder and os.path.isdir(spola_folder):
            shutil.rmtree(spola_folder)
            log.write(f"Cartella spola rimossa: {spola_folder}")
        gui.display_notification("Backup documenti completato e verificato.")
    else:
        gui.display_alert("Verifica integrità fallita: le cartelle TODAY NON sono state svuotate.")
        log.end()
        raise SystemExit(2)

    # 6) Report giornaliero (HTML + PDF) e bozza email con i report allegati
    out = _try_report(log)
    _try_email(config, log, day_name, reports_dir, (out or {}).get("pdf"))
    log.end()


# ----------------------------------------------------------------------
# Comando STILL
# ----------------------------------------------------------------------
def run_still_mode(config: ProjectConfig, volumes_root: str = diskutils.VOLUMES_ROOT,
                   drx_mode: Optional[bool] = None) -> None:
    """`drx_mode`: None = usa still.mode del config; True/False forza il modo."""
    if drx_mode is None:
        drx_mode = config.still_mode == "drx"

    log = DayLogger(config, "still")
    log.start()

    day_num = resolve_day_number(config)
    day_name = build_folder_name(day_num, config.day_hour_offset)
    log.write(f"Day trovato: {day_num}")

    src = config.still_source_path

    # Modo DRX: individua le still nuove PRIMA di eliminare i .drx.
    drx_stills: List[str] = []
    if drx_mode:
        drx_stills = copyops.find_stills_with_drx(src, only_ext=config.still_extension)
        log.write(f"Modo DRX: {len(drx_stills)} still con .drx omonimo in {src}")

    # Elimina i .drx dalla sorgente still.
    if config.still_delete_drx:
        copyops.delete_by_extension(src, ".drx")
        log.write(f"DRX eliminate dalla cartella {src}")

    dest = os.path.join(config.drive_stills, day_name)
    if drx_mode:
        copied = copyops.copy_files(src, dest, drx_stills)
    else:
        # Prompt: ultimi N minuti.
        minutes_raw = gui.ask_text("Inserisci MIN da export:", str(config.still_default_minutes))
        try:
            minutes = int(minutes_raw)
        except ValueError:
            minutes = config.still_default_minutes
        log.write(f"Selezionati {minutes} minuti di file da copiare.")
        copied = copyops.copy_recent_files(src, dest, minutes, only_ext=config.still_extension)
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
    n = len(copied)
    if n:
        gui.display_notification(f"Cartella {day_name}", title=f"{n} still copiate")
    else:
        gui.display_notification("Nessuna still da copiare", title="Copia still completata")
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


def _try_report(log: DayLogger) -> Optional[dict]:
    try:
        out = report.generate(log.log_file)
        log.write(f"Report generato: {out['html']}" + (f" / {out['pdf']}" if out["pdf"] else ""))
        return out
    except Exception as exc:  # pragma: no cover - il report non deve bloccare
        log.write(f"ATTENZIONE: report non generato: {exc}")
        return None


def _try_email(config: ProjectConfig, log: DayLogger, day_name: str,
               reports_dir: str, report_pdf: Optional[str]) -> None:
    """Prepara la bozza email in Mail.app. Non deve mai bloccare il backup."""
    if not config.email.enabled:
        return
    if not config.email.recipients:
        log.write("ATTENZIONE: email attiva ma nessun destinatario in mailinglist.")
        return
    try:
        attachments = mailer.collect_attachments(
            reports_dir, report_pdf,
            config.email.attach_day_reports, config.email.attach_report_pdf,
        )
        script = mailer.build_applescript(
            config.email.recipients,
            mailer.render_text(config.email.subject, config.film, day_name),
            mailer.render_text(config.email.body, config.film, day_name),
            attachments,
        )
        gui.run_applescript(script)
        log.write(
            f"Bozza email preparata per {len(config.email.recipients)} destinatari "
            f"con {len(attachments)} allegati (da rivedere e inviare a mano)."
        )
    except Exception as exc:
        log.write(f"ATTENZIONE: bozza email non creata: {exc}")
