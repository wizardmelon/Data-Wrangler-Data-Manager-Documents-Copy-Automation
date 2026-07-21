import os

from odc_backup.config import ProjectConfig, StillRename
from odc_backup import scaffold


def _cfg(base):
    return ProjectConfig(
        film="F",
        base_work=base,
        day_folders=["TODAY FILES", "DAILY FILES", "REPORTS", "STILL"],
        still_rename=StillRename(prefix="SC", fields=["scena", "clip"], day_token="timeline"),
    )


def test_create_day_structure(tmp_path):
    base = str(tmp_path / "giornata")
    cfg = _cfg(base)
    created = scaffold.create_day_structure(cfg, base)
    for name in cfg.day_folders:
        assert os.path.isdir(os.path.join(base, name))
    assert len(created) == 4


def test_reference_files_written(tmp_path):
    base = str(tmp_path / "giornata")
    cfg = _cfg(base)
    os.makedirs(base, exist_ok=True)
    refs = scaffold.write_reference_files(cfg, base)
    assert len(refs) == 2

    ss = os.path.join(base, "SILVERSTACK_report_path.txt")
    rp = os.path.join(base, "RESOLVE_still_pattern.txt")
    assert os.path.isfile(ss)
    assert os.path.isfile(rp)

    # Silverstack: stringa letterale, $projectName$ NON sostituito.
    assert "$projectName$" in open(ss, encoding="utf-8").read()
    # Resolve: pattern costruito dallo YAML con DAY in coda.
    assert "SC%{Scene}_%{Clip Name}_%{Timeline Name}" in open(rp, encoding="utf-8").read()


def test_run_full(tmp_path):
    base = str(tmp_path / "g")
    out = scaffold.run(_cfg(base), base)
    assert out["base"] == base
    assert len(out["folders"]) == 4
    assert len(out["references"]) == 2
