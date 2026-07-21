"""Utility sui volumi montati: ricerca SPOLA, verifica dischi, spazio libero.

Isola l'accesso al filesystem /Volumes così che la logica sia testabile
passando una `volumes_root` alternativa (es. una cartella temporanea nei test).
"""

from __future__ import annotations

import os
import shutil
from typing import List

VOLUMES_ROOT = "/Volumes"


def list_volumes(volumes_root: str = VOLUMES_ROOT) -> List[str]:
    if not os.path.isdir(volumes_root):
        return []
    return sorted(
        name for name in os.listdir(volumes_root)
        if os.path.isdir(os.path.join(volumes_root, name))
    )


def find_spola_disks(prefix: str, volumes_root: str = VOLUMES_ROOT) -> List[str]:
    """Volumi il cui nome contiene il prefisso della spola (case-insensitive)."""
    prefix_low = prefix.lower()
    return [v for v in list_volumes(volumes_root) if prefix_low in v.lower()]


def disk_mounted(name: str, volumes_root: str = VOLUMES_ROOT) -> bool:
    return os.path.isdir(os.path.join(volumes_root, name))


def disk_path(name: str, volumes_root: str = VOLUMES_ROOT) -> str:
    return os.path.join(volumes_root, name)


def day_folder_exists(disk_name: str, day_folder: str,
                      volumes_root: str = VOLUMES_ROOT) -> bool:
    """La cartella DAY DEVE già esistere sul disco (contiene i dailies video/audio)."""
    return os.path.isdir(os.path.join(volumes_root, disk_name, day_folder))


def free_space_bytes(path: str) -> int:
    return shutil.disk_usage(path).free


def dir_size_bytes(path: str) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            fp = os.path.join(root, name)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def has_enough_space(dest_path: str, needed_bytes: int, margin: float = 1.10) -> bool:
    """True se `dest_path` ha spazio per `needed_bytes` con un margine di sicurezza."""
    return free_space_bytes(dest_path) >= int(needed_bytes * margin)
