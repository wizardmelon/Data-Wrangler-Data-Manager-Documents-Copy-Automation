import pytest

from dm_backup.config import ConfigError, ProjectConfig


BASE = {
    "project": {"film": "TEST FILM", "prod": "PROD", "dop": "VANNI"},
    "paths": {"base_work": "/tmp/base", "drive": "/Volumes/DRIVE"},
    "disks": {"backup_disks": ["D1", "D2"], "disc_spola": "SPOLA"},
    "sources": {"folders": ["DRP", "ALE"], "still": "/tmp/still"},
    "project_folders": ["DAILY FILES", "SCRIPT LOGS"],
    "still_rename": {"prefix": "SC", "fields": ["scena", "clip"], "separator": "_"},
}


def test_from_dict_ok():
    cfg = ProjectConfig.from_dict(BASE)
    assert cfg.film == "TEST FILM"
    assert cfg.source_folders == ["DRP", "ALE"]
    assert cfg.backup_disks == ["D1", "D2"]
    assert cfg.project_folders == ["DAILY FILES", "SCRIPT LOGS"]
    assert cfg.still_rename.fields == ["scena", "clip"]
    assert cfg.still_rename.day_token == "timeline"


def test_missing_film_raises():
    data = {"paths": {"base_work": "/tmp"}}
    with pytest.raises(ConfigError):
        ProjectConfig.from_dict(data)


def test_missing_base_work_raises():
    data = {"project": {"film": "X"}}
    with pytest.raises(ConfigError):
        ProjectConfig.from_dict(data)


def test_load_from_file(tmp_path):
    import yaml
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(BASE), encoding="utf-8")
    cfg = ProjectConfig.load(str(p))
    assert cfg.dop == "VANNI"


def test_load_missing_file():
    with pytest.raises(ConfigError):
        ProjectConfig.load("/does/not/exist.yaml")
