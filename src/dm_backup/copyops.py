"""Motore di copia con verifica di integrità.

Sostituisce le funzioni AppleScript `copyFolder` / `copyWithFind` (basate su
`cp -Rv` dentro `do shell script`) con:

- copia via `rsync` quando disponibile (gestisce nativamente spazi e caratteri
  strani nei nomi), con fallback Python puro se `rsync` non c'è;
- verifica **checksum** sorgente↔destinazione, che è la vera garanzia prima di
  qualsiasi cancellazione;
- generazione di un **manifest MHL** (Media Hash List) per ogni copia.

La regola d'oro: le cartelle sorgente non vengono MAI svuotate finché la verifica
checksum su tutte le destinazioni non è andata a buon fine.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Dict, List
from xml.sax.saxutils import escape as _xml_escape

_HASH_ALGO = "sha1"  # usato sia per la verifica sia per l'MHL
_CHUNK = 1024 * 1024


def rsync_available() -> bool:
    return shutil.which("rsync") is not None


# ----------------------------------------------------------------------
# Hashing / manifest
# ----------------------------------------------------------------------
def hash_file(path: str) -> str:
    h = hashlib.new(_HASH_ALGO)
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_tree(root: str) -> Dict[str, str]:
    """Mappa {percorso-relativo: hash} di tutti i file sotto `root`."""
    hashes: Dict[str, str] = {}
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            hashes[rel] = hash_file(full)
    return hashes


@dataclass
class VerifyResult:
    ok: bool
    checked: int = 0
    missing: List[str] = field(default_factory=list)   # presenti in src, assenti in dest
    mismatched: List[str] = field(default_factory=list)  # hash diverso


def verify_copy(src: str, dest: str) -> VerifyResult:
    """Confronta gli hash dei file di `src` con i corrispondenti in `dest`."""
    src_hashes = hash_tree(src)
    missing: List[str] = []
    mismatched: List[str] = []
    for rel, src_hash in src_hashes.items():
        dest_file = os.path.join(dest, rel)
        if not os.path.isfile(dest_file):
            missing.append(rel)
            continue
        if hash_file(dest_file) != src_hash:
            mismatched.append(rel)
    return VerifyResult(
        ok=not missing and not mismatched,
        checked=len(src_hashes),
        missing=missing,
        mismatched=mismatched,
    )


def write_mhl(root: str, mhl_path: str) -> str:
    """Scrive un manifest MHL v1.1 (mediahashlist.org) per l'albero `root`."""
    now = _dt.datetime.now().astimezone().replace(microsecond=0).isoformat()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<hashlist version="1.1">',
        "  <creatorinfo>",
        f"    <name>{_xml_escape(os.getenv('USER', 'dm-backup'))}</name>",
        "    <tool>dm-backup</tool>",
        f"    <startdate>{now}</startdate>",
        f"    <finishdate>{now}</finishdate>",
        "  </creatorinfo>",
    ]
    for rel, digest in sorted(hash_tree(root).items()):
        full = os.path.join(root, rel)
        size = os.path.getsize(full)
        lines += [
            "  <hash>",
            f"    <file>{_xml_escape(rel)}</file>",
            f"    <size>{size}</size>",
            f"    <{_HASH_ALGO}>{digest}</{_HASH_ALGO}>",
            "  </hash>",
        ]
    lines.append("</hashlist>")
    content = "\n".join(lines) + "\n"
    os.makedirs(os.path.dirname(mhl_path) or ".", exist_ok=True)
    with open(mhl_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return mhl_path


# ----------------------------------------------------------------------
# Copia
# ----------------------------------------------------------------------
def _copy_tree_python(src: str, dest: str) -> None:
    """Fallback puro Python: copia il CONTENUTO di src dentro dest (merge)."""
    for dirpath, _dirs, files in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        target_dir = os.path.join(dest, rel) if rel != "." else dest
        os.makedirs(target_dir, exist_ok=True)
        for name in files:
            shutil.copy2(os.path.join(dirpath, name), os.path.join(target_dir, name))


def copy_into(src: str, dest: str) -> None:
    """Copia il CONTENUTO di `src` dentro `dest` (merge, senza annidare `src`).

    Usato per aggiungere le cartelle documenti dentro la cartella DAY già
    esistente sui dischi di backup. Usa rsync se disponibile, altrimenti Python.
    """
    if not os.path.isdir(src):
        raise FileNotFoundError(f"Sorgente inesistente: {src}")
    os.makedirs(dest, exist_ok=True)
    if rsync_available():
        # I trailing slash sono importanti: "src/" -> copia il contenuto in "dest/".
        subprocess.run(
            ["rsync", "-a", os.path.join(src, ""), os.path.join(dest, "")],
            check=True,
        )
    else:
        _copy_tree_python(src, dest)


def count_files(path: str) -> int:
    return sum(len(files) for _r, _d, files in os.walk(path)) if os.path.isdir(path) else 0


def delete_by_extension(folder: str, ext: str) -> int:
    """Elimina i file con estensione `ext` (es. '.drx') dentro `folder`.

    Replica lo step 'DRX eliminate' della modalità still dell'originale.
    Ritorna il numero di file eliminati.
    """
    if not os.path.isdir(folder):
        return 0
    ext_low = ext.lower()
    removed = 0
    for dirpath, _dirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(ext_low):
                os.remove(os.path.join(dirpath, name))
                removed += 1
    return removed


def find_stills_with_drx(src: str, only_ext: str | None = None) -> List[str]:
    """Percorsi relativi delle still che hanno un .drx con lo stesso nome.

    Una still è "nuova" (mai passata dal ciclo di backup, che cancella i .drx)
    se accanto a lei esiste un .drx con lo stesso nome base. Va chiamata PRIMA
    di eliminare i .drx.
    """
    if not os.path.isdir(src):
        return []
    ext_low = only_ext.lower() if only_ext else None
    found: List[str] = []
    for dirpath, _dirs, files in os.walk(src):
        drx_stems = {os.path.splitext(n)[0].lower() for n in files
                     if n.lower().endswith(".drx")}
        for name in files:
            stem, ext = os.path.splitext(name)
            if ext.lower() == ".drx" or stem.lower() not in drx_stems:
                continue
            if ext_low and ext.lower() != ext_low:
                continue
            found.append(os.path.relpath(os.path.join(dirpath, name), src))
    return sorted(found)


def copy_files(src: str, dest: str, rel_paths: List[str]) -> List[str]:
    """Copia in `dest` i file elencati (percorsi relativi a `src`)."""
    os.makedirs(dest, exist_ok=True)
    for rel in rel_paths:
        target = os.path.join(dest, rel)
        os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
        shutil.copy2(os.path.join(src, rel), target)
    return list(rel_paths)


def copy_recent_files(src: str, dest: str, minutes: int,
                      only_ext: str | None = None) -> List[str]:
    """Copia in `dest` solo i file di `src` modificati negli ultimi `minutes`.

    Replica il filtro 'ultimi N minuti' della modalità still (find -mmin).
    Se `only_ext` è passato (es. '.jpg'), copia solo i file con quell'estensione.
    Ritorna la lista dei percorsi relativi copiati.
    """
    if not os.path.isdir(src):
        raise FileNotFoundError(f"Sorgente inesistente: {src}")
    os.makedirs(dest, exist_ok=True)
    cutoff = time.time() - minutes * 60
    ext_low = only_ext.lower() if only_ext else None
    copied: List[str] = []
    for dirpath, _dirs, files in os.walk(src):
        for name in files:
            if ext_low and not name.lower().endswith(ext_low):
                continue
            full = os.path.join(dirpath, name)
            try:
                if os.path.getmtime(full) < cutoff:
                    continue
            except OSError:
                continue
            rel = os.path.relpath(full, src)
            target = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            shutil.copy2(full, target)
            copied.append(rel)
    return copied


def verify_files(src: str, dest: str, rel_paths: List[str]) -> VerifyResult:
    """Verifica per checksum solo i file elencati (per copie parziali, es. still)."""
    missing: List[str] = []
    mismatched: List[str] = []
    for rel in rel_paths:
        src_file = os.path.join(src, rel)
        dest_file = os.path.join(dest, rel)
        if not os.path.isfile(dest_file):
            missing.append(rel)
            continue
        if hash_file(dest_file) != hash_file(src_file):
            mismatched.append(rel)
    return VerifyResult(
        ok=not missing and not mismatched,
        checked=len(rel_paths),
        missing=missing,
        mismatched=mismatched,
    )


def recreate_folder(path: str) -> None:
    """Cancella la cartella se esiste e la ricrea vuota (come `recreateFolder`)."""
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)
