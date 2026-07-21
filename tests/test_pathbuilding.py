import os

from dm_backup import workflows


def test_build_folder_name():
    assert workflows.build_folder_name("DAY010", "20251122") == "DAY010_20251122"


def test_detect_day_from_stills(tmp_path):
    still_dir = tmp_path / "still"
    still_dir.mkdir()
    (still_dir / "SC01_A001_DAY007.jpg").write_text("x")
    (still_dir / "SC02_A002_DAY007.jpg").write_text("x")
    (still_dir / "SC03_A003_DAY008.jpg").write_text("x")
    (still_dir / "ignore.txt").write_text("x")

    from dm_backup.config import ProjectConfig
    cfg = ProjectConfig(film="F", base_work=str(tmp_path), source_still=str(still_dir))
    assert workflows.detect_day_from_stills(cfg.source_still) == ["DAY007", "DAY008"]


def test_detect_day_empty_folder(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    assert workflows.detect_day_from_stills(str(d)) == []
