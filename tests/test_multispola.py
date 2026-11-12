import os

import pytest

from dm_backup import gui, workflows
from dm_backup.config import ProjectConfig


def _setup(tmp_path):
    vol = tmp_path / "Volumes"
    root = tmp_path / "FILM"
    for disk in ("DISKA", "TRAV01", "TRAV02"):
        (vol / disk / "DAY012_20260101").mkdir(parents=True)
    for sp, rep in (("TRAV01", "r1.txt"), ("TRAV02", "r2.txt")):
        d = root / "DAILY_FILES" / sp / "03_REPORTS"
        d.mkdir(parents=True)
        (d / rep).write_text(rep)
    still = root / "TODAY_FILES" / "05_STILL"
    still.mkdir(parents=True)
    (still / "SC1_DAY012.jpg").write_text("img")
    (root / "TODAY_FILES" / "04_DRP").mkdir()
    (root / "TODAY_FILES" / "04_DRP" / "a.drp").write_text("drp")
    cfg = ProjectConfig.from_dict({
        "project": {"film": "F"},
        "paths": {"project_root": str(root), "drive_reports": ""},
        "structure": {"files_folders": ["04_DRP", "05_STILL"]},
        "spola": {"prefix": "TRAV"},
        "disks": {"fixed_disks": ["DISKA"], "include_spola": True},
        "safety": {"verify_checksum": True, "write_mhl": False, "check_space": False},
    })
    return cfg, str(vol), root


def test_resolve_spole_all(tmp_path, monkeypatch):
    cfg, vol, _ = _setup(tmp_path)
    monkeypatch.setattr(gui, "choose_from_list", lambda opts, prompt: workflows.ALL_SPOLE_LABEL)
    assert workflows.resolve_spole(cfg, vol) == ["TRAV01", "TRAV02"]
    monkeypatch.setattr(gui, "choose_from_list", lambda opts, prompt: "TRAV02")
    assert workflows.resolve_spole(cfg, vol) == ["TRAV02"]


def test_files_mode_with_two_spole(tmp_path, monkeypatch):
    cfg, vol, root = _setup(tmp_path)
    monkeypatch.setattr(gui, "choose_from_list", lambda opts, prompt: workflows.ALL_SPOLE_LABEL)
    monkeypatch.setattr(gui, "display_notification", lambda *a, **k: None)
    monkeypatch.setattr(gui, "display_alert", lambda *a, **k: None)
    monkeypatch.setattr(workflows, "_try_email", lambda *a, **k: None)
    workflows.run_files_mode(cfg, vol)
    for disk in ("DISKA", "TRAV01", "TRAV02"):
        day = os.path.join(vol, disk, "DAY012_20260101")
        found = {f for _r, _d, fs in os.walk(day) for f in fs}
        assert {"a.drp", "SC1_DAY012.jpg", "r1.txt", "r2.txt"} <= found, (disk, found)
    # cartelle spola in DAILY_FILES rimosse, TODAY svuotata
    assert not (root / "DAILY_FILES" / "TRAV01").exists()
    assert not (root / "DAILY_FILES" / "TRAV02").exists()
    assert os.listdir(root / "TODAY_FILES" / "05_STILL") == []
