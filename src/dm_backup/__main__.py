"""Entry point CLI.

Uso (da Stream Deck, senza virgolette sugli argomenti):
    dm-backup files             # uso quotidiano
    dm-backup still             # uso quotidiano (ultimi N minuti)
    dm-backup still --drx       # tutte le still con .drx omonimo
    dm-backup config            # editor grafico di config.yaml
    dm-backup init [base]       # setup di INIZIO FILM (una volta sola)
    dm-backup report <log>

La configurazione è cercata in --config, poi in $DM_BACKUP_CONFIG, poi in
./config.yaml nella cartella corrente.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Optional

from . import workflows
from .config import ConfigError, ProjectConfig
from . import gui


def _default_config_path() -> str:
    return os.environ.get("DM_BACKUP_CONFIG", os.path.join(os.getcwd(), "config.yaml"))


def _load_config(path: Optional[str]) -> ProjectConfig:
    return ProjectConfig.load(path or _default_config_path())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dm-backup", description="dm-backup — Data Manager tools")
    parser.add_argument("--config", help="Percorso a config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("files", help="Copia i documenti del giorno nei dischi di backup")
    p_still = sub.add_parser("still", help="Copia le still sul drive (autodetect DAY)")
    p_still.add_argument(
        "--drx", action="store_true",
        help="Copia tutte le still che hanno un .drx con lo stesso nome (niente prompt minuti)",
    )

    sub.add_parser("config", help="Apre l'editor grafico (pagina HTML locale) di config.yaml")

    p_init = sub.add_parser(
        "init",
        help="SETUP INIZIO FILM: crea la struttura del progetto + file di riferimento",
    )
    p_init.add_argument(
        "base", nargs="?",
        help="Cartella radice del progetto/film (default: paths.project_root del config)",
    )

    p_report = sub.add_parser("report", help="Rigenera il report da un file di log")
    p_report.add_argument("log_path", help="Percorso del file di log .txt")

    return parser


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.command == "report":
            out = workflows.run_report(args.log_path)
            print(f"Report: {out['html']}" + (f"\nPDF: {out['pdf']}" if out["pdf"] else ""))
            return 0

        if args.command == "config":
            from . import configui
            configui.run_config_ui(args.config or _default_config_path())
            return 0

        config = _load_config(args.config)

        if args.command == "files":
            workflows.run_files_mode(config)
        elif args.command == "still":
            workflows.run_still_mode(config, drx_mode=True if args.drx else None)
        elif args.command == "init":
            base = args.base or config.project_root or config.daily_files
            out = workflows.run_init(config, base)
            print(f"Struttura del progetto creata in: {out['base']}")
            for f in out["folders"]:
                print(f"  cartella: {f}")
            for r in out["references"]:
                print(f"  riferimento: {r}")
        return 0

    except ConfigError as exc:
        gui.display_alert(str(exc), title="Errore di configurazione")
        print(f"Errore di configurazione: {exc}", file=sys.stderr)
        return 1
    except gui.UserCancelled:
        print("Operazione annullata dall'utente.", file=sys.stderr)
        return 130
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover
        gui.display_alert(str(exc), title="Errore")
        print(f"Errore: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
