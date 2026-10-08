"""Interfaccia grafica (pagina HTML locale) per leggere e scrivere config.yaml.

`dm-backup config` avvia un piccolo server SOLO su 127.0.0.1, apre il browser e
mostra un modulo con tutte le impostazioni. Al salvataggio:
  1. la config risultante è validata con la stessa logica usata dai comandi;
  2. il config.yaml esistente è copiato in `.backups/` (con data e ora);
  3. il nuovo file è scritto in modo atomico.
Le chiavi sconosciute presenti nel file vengono conservate.

Nota: i commenti del vecchio file non sopravvivono alla riscrittura (YAML).
"""

from __future__ import annotations

import copy
import datetime as _dt
import json
import os
import secrets
import shutil
import subprocess
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import yaml

from . import diskutils, still
from .config import ConfigError, ProjectConfig, StillRename

HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "configui.html")

HEADER = (
    "# dm-backup — configurazione di progetto\n"
    "# Generato dall'interfaccia grafica (dm-backup config). Puoi modificarlo anche a mano.\n"
    "# Template commentato campo per campo: config.example.yaml\n\n"
)

# Valori di partenza per i campi mancanti (stessa forma di config.example.yaml).
DEFAULTS: Dict[str, Any] = {
    "project": {"film": "", "prod": "", "regia": "", "dop": "", "dit": "", "dmanager": ""},
    "paths": {"project_root": "", "today_files": "", "daily_files": "", "log_folder": "",
              "drive_reports": "", "drive_stills": ""},
    "structure": {"reports_subfolder": "03_REPORTS", "still_source": "05_STILL",
                  "files_folders": []},
    "spola": {"prefix": "", "reports_subfolder": "03_REPORTS"},
    "disks": {"fixed_disks": [], "include_spola": True},
    "day_hour_offset": 8,
    "still": {"mode": "minutes", "default_minutes": 5, "delete_drx": True, "extension": ".jpg"},
    "safety": {"verify_checksum": True, "write_mhl": True, "check_space": True},
    "cleanup": {"spola_folder": True},
    "project_folders": [],
    "email": {"invia_email": "n", "mailinglist": "", "oggetto": "Report di giornata {DAY}",
              "testo": "", "allega_report_giornata": "y", "allega_report_pdf": "y"},
    "still_rename": {"prefix": "", "fields": [], "separator": "_", "day_token": "timeline"},
}

PATH_KEYS = ("project_root", "today_files", "daily_files", "log_folder",
             "drive_reports", "drive_stills")


def merge_defaults(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sovrappone `data` ai default, conservando le chiavi sconosciute."""
    out = copy.deepcopy(DEFAULTS)
    for key, value in (data or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key].update(value)
        else:
            out[key] = value
    return out


def load_raw(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        return merge_defaults({})
    with open(path, "r", encoding="utf-8") as fh:
        return merge_defaults(yaml.safe_load(fh) or {})


def collect_warnings(data: Dict[str, Any]) -> List[str]:
    """Avvisi non bloccanti: percorsi inesistenti, alias Resolve non validi."""
    warns: List[str] = []
    for key in PATH_KEYS:
        value = (data.get("paths") or {}).get(key)
        if value and not os.path.exists(value):
            warns.append(f"Il percorso non esiste (ancora): {key} = {value}")
    sr = data.get("still_rename") or {}
    try:
        still.build_resolve_pattern(StillRename(
            prefix=str(sr.get("prefix", "")), fields=list(sr.get("fields") or []),
            separator=str(sr.get("separator", "_")), day_token=str(sr.get("day_token", "timeline"))))
    except still.StillPatternError as exc:
        warns.append(str(exc))
    if (data.get("still") or {}).get("mode") not in ("minutes", "drx"):
        warns.append("still.mode deve essere 'minutes' o 'drx'.")
    return warns


def save_config(path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Valida, fa il backup del file esistente e scrive il nuovo YAML.

    Solleva ConfigError se la configurazione non è valida (nulla viene scritto).
    """
    if (data.get("still") or {}).get("mode") not in ("minutes", "drx"):
        raise ConfigError("still.mode deve essere 'minutes' o 'drx'.")
    try:
        sr = data.get("still_rename") or {}
        still.build_resolve_pattern(StillRename(
            prefix=str(sr.get("prefix", "")), fields=list(sr.get("fields") or []),
            separator=str(sr.get("separator", "_")), day_token=str(sr.get("day_token", "timeline"))))
    except still.StillPatternError as exc:
        raise ConfigError(str(exc)) from exc
    ProjectConfig.from_dict(copy.deepcopy(data))  # stessa validazione dei comandi

    text = HEADER + yaml.safe_dump(data, sort_keys=False, allow_unicode=True,
                                   default_flow_style=False, width=1000)
    # Controllo di coerenza: il testo riletto deve produrre una config valida.
    ProjectConfig.from_dict(yaml.safe_load(text))

    backup = None
    if os.path.isfile(path):
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(path)), ".backups")
        os.makedirs(backup_dir, exist_ok=True)
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = os.path.join(backup_dir, f"{os.path.basename(path)}.{stamp}")
        shutil.copy2(path, backup)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, path)
    return {"backup": backup, "warnings": collect_warnings(data)}


def list_volumes(volumes_root: str = diskutils.VOLUMES_ROOT) -> List[str]:
    try:
        names = sorted(os.listdir(volumes_root))
    except OSError:
        return []
    return [n for n in names if not n.startswith(".")]


def browse_folder(prompt: str = "Scegli una cartella") -> Optional[str]:
    """Finestra nativa macOS 'scegli cartella'. None se annullata."""
    safe = prompt.replace("\\", "\\\\").replace('"', '\\"')
    result = subprocess.run(
        ["osascript", "-e", f'POSIX path of (choose folder with prompt "{safe}")'],
        capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip().rstrip("/") or "/"


def preview_pattern(sr: Dict[str, Any]) -> Dict[str, str]:
    try:
        return {"pattern": still.build_resolve_pattern(StillRename(
            prefix=str(sr.get("prefix", "")), fields=list(sr.get("fields") or []),
            separator=str(sr.get("separator", "_")),
            day_token=str(sr.get("day_token", "timeline"))))}
    except still.StillPatternError as exc:
        return {"error": str(exc)}


# ----------------------------------------------------------------------
# Server
# ----------------------------------------------------------------------
def make_handler(config_path: str, token: str, shutdown):
    class Handler(BaseHTTPRequestHandler):
        server_version = "dm-backup-config"

        def log_message(self, *args):  # silenzioso
            pass

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").split(":")[0]
            return host in ("127.0.0.1", "localhost")

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj: Any, code: int = 200) -> None:
            self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _authorized(self) -> bool:
            return self._host_ok() and self.headers.get("X-Token") == token

        def do_GET(self):
            path = urlparse(self.path).path
            if not self._host_ok():
                return self._json({"error": "host non valido"}, 403)
            if path == "/":
                with open(HTML_PATH, "rb") as fh:
                    html = fh.read().replace(b"__TOKEN__", token.encode())
                return self._send(200, html, "text/html; charset=utf-8")
            if not self._authorized():
                return self._json({"error": "non autorizzato"}, 403)
            if path == "/api/config":
                return self._json({"config": load_raw(config_path), "path": config_path,
                                   "aliases": sorted(still.ALIAS_TO_TOKEN)})
            if path == "/api/volumes":
                return self._json({"volumes": list_volumes()})
            self._json({"error": "non trovato"}, 404)

        def do_POST(self):
            path = urlparse(self.path).path
            if not self._authorized():
                return self._json({"error": "non autorizzato"}, 403)
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except ValueError:
                return self._json({"error": "JSON non valido"}, 400)
            if path == "/api/save":
                try:
                    return self._json({"ok": True, **save_config(config_path, payload)})
                except (ConfigError, ValueError, TypeError) as exc:
                    return self._json({"ok": False, "error": str(exc)}, 400)
            if path == "/api/browse":
                return self._json({"path": browse_folder(str(payload.get("prompt", "Scegli una cartella")))})
            if path == "/api/preview":
                return self._json(preview_pattern(payload))
            if path == "/api/quit":
                self._json({"ok": True})
                threading.Thread(target=shutdown, daemon=True).start()
                return
            self._json({"error": "non trovato"}, 404)

    return Handler


def run_config_ui(config_path: str, open_browser: bool = True) -> None:
    token = secrets.token_urlsafe(24)
    server_holder: Dict[str, ThreadingHTTPServer] = {}

    def shutdown():
        server_holder["s"].shutdown()

    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(config_path, token, shutdown))
    server_holder["s"] = server
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Editor configurazione: {url}\nFile: {config_path}\n(Ctrl+C o 'Chiudi' nella pagina per uscire)", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
