import pytest

from dm_backup.config import ConfigError, ProjectConfig


BASE = {
    "project": {"film": "ISIDE", "prod": "CATTLEYA", "dop": "CATINARI"},
    "paths": {
        "project_root": "/tmp/ISIDE",
        "today_files": "/tmp/ISIDE/TODAY_FILES",
        "daily_files": "/tmp/ISIDE/DAILY_FILES",
        "drive_reports": "/tmp/Drive/REPORTS",
        "drive_stills": "/tmp/Drive/STILLs",
    },
    "structure": {
        "reports_subfolder": "03_REPORTS",
        "still_source": "05_STILL",
        "files_folders": ["04_DRP", "06_STILL_LAB", "05_STILL"],
    },
    "spola": {"prefix": "ISIDE_SHUTTLE", "reports_subfolder": "03_REPORTS"},
    "disks": {"fixed_disks": ["ISIDE_MASTER01", "ISIDE_TEMP01"], "include_spola": True},
    "still": {"default_minutes": 5, "delete_drx": True},
    "project_folders": ["TODAY_FILES/04_DRP", "DAILY_FILES", "LOGS"],
    "still_rename": {"prefix": "SC", "fields": ["scena", "clip"], "separator": "_"},
}


def test_from_dict_ok():
    cfg = ProjectConfig.from_dict(BASE)
    assert cfg.film == "ISIDE"
    assert cfg.files_folders == ["04_DRP", "06_STILL_LAB", "05_STILL"]
    assert cfg.fixed_disks == ["ISIDE_MASTER01", "ISIDE_TEMP01"]
    assert cfg.spola_prefix == "ISIDE_SHUTTLE"
    assert cfg.include_spola_as_disk is True
    assert cfg.still_default_minutes == 5
    assert cfg.project_folders == ["TODAY_FILES/04_DRP", "DAILY_FILES", "LOGS"]


def test_derived_paths():
    cfg = ProjectConfig.from_dict(BASE)
    assert cfg.still_source_path == "/tmp/ISIDE/TODAY_FILES/05_STILL"
    assert cfg.files_folder_paths()[0] == "/tmp/ISIDE/TODAY_FILES/04_DRP"
    assert cfg.log_dir == "/tmp/ISIDE/LOGS"  # default: <project_root>/LOGS


def test_log_folder_override():
    data = dict(BASE)
    data["paths"] = dict(BASE["paths"], log_folder="/custom/logs")
    cfg = ProjectConfig.from_dict(data)
    assert cfg.log_dir == "/custom/logs"


def test_safety_defaults_true():
    cfg = ProjectConfig.from_dict(BASE)
    assert cfg.verify_checksum and cfg.write_mhl and cfg.check_space


def test_missing_film_raises():
    with pytest.raises(ConfigError):
        ProjectConfig.from_dict({"paths": {"project_root": "/tmp"}})


def test_missing_roots_raises():
    with pytest.raises(ConfigError):
        ProjectConfig.from_dict({"project": {"film": "X"}})


def test_load_from_file(tmp_path):
    import yaml
    p = tmp_path / "config.yaml"
    p.write_text(yaml.safe_dump(BASE), encoding="utf-8")
    cfg = ProjectConfig.load(str(p))
    assert cfg.dop == "CATINARI"


def test_load_missing_file():
    with pytest.raises(ConfigError):
        ProjectConfig.load("/does/not/exist.yaml")


def test_resolve_drive_path_swaps_localized_root(tmp_path):
    from dm_backup.config import resolve_drive_path
    real = tmp_path / "GoogleDrive-x" / "Il mio Drive" / "TQCC" / "STILLS"
    real.mkdir(parents=True)
    stale = str(tmp_path / "GoogleDrive-x" / "My Drive" / "TQCC" / "STILLS")
    assert resolve_drive_path(stale) == str(real)


def test_resolve_drive_path_keeps_existing_and_unknown(tmp_path):
    from dm_backup.config import resolve_drive_path
    ok = tmp_path / "My Drive" / "TQCC"
    ok.mkdir(parents=True)
    assert resolve_drive_path(str(ok)) == str(ok)
    missing = str(tmp_path / "Altro" / "TQCC")
    assert resolve_drive_path(missing) == missing
    assert resolve_drive_path("") == ""
