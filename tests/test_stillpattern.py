import pytest

from odc_backup.config import StillRename
from odc_backup import still


def test_build_pattern_appends_day_token():
    sr = StillRename(prefix="SC", fields=["scena", "clip"], separator="_", day_token="timeline")
    pattern = still.build_resolve_pattern(sr)
    assert pattern == "SC%{Scene}_%{Clip Name}_%{Timeline Name}"


def test_day_token_not_duplicated_if_last():
    sr = StillRename(prefix="", fields=["scena", "timeline"], separator="_", day_token="timeline")
    pattern = still.build_resolve_pattern(sr)
    assert pattern == "%{Scene}_%{Timeline Name}"
    assert pattern.count("%{Timeline Name}") == 1


def test_empty_fields_still_has_day():
    sr = StillRename(fields=[], day_token="timeline")
    assert still.build_resolve_pattern(sr) == "%{Timeline Name}"


def test_unknown_alias_raises_with_valid_list():
    sr = StillRename(fields=["pippo"], day_token="timeline")
    with pytest.raises(still.StillPatternError) as exc:
        still.build_resolve_pattern(sr)
    assert "scena" in str(exc.value)


def test_alias_case_and_spaces_insensitive():
    sr = StillRename(fields=["Clip Name"], day_token="timeline")
    assert still.build_resolve_pattern(sr) == "%{Clip Name}_%{Timeline Name}"


def test_find_days_from_filenames():
    names = [
        "SC01_A001_DAY010.jpg",
        "SC02_B002_DAY010.jpg",
        "SC03_C003_DAY011.jpg",
        "note.txt",
    ]
    assert still.find_days(names) == ["DAY010", "DAY011"]


def test_day_regex_coherent_with_export():
    # Il pattern esporta il Timeline Name che contiene DAYxxx: la stessa regex
    # deve poterlo rileggere.
    assert still.day_regex().search("SC01_A001_DAY010").group(0) == "DAY010"
