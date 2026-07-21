import os

from dm_backup import report


SAMPLE_LOG = """LOG - BackUp file giornalieri - Python - v2.0

TEST FILM - 20251122
Produzione - PROD
Regia - REGIA

[files --> 2025-11-22 18:00:01] === AVVIO modalità FILES ===
[files --> 2025-11-22 18:00:02] Disco SPOLA: ODC_SPOLA_03
[files --> 2025-11-22 18:00:10] Copiati 12 file da REPORTS
[files --> 2025-11-22 18:01:00] Verifica OK su ODC_BACKUP_01: 12 file
"""


def _write_log(tmp_path):
    p = tmp_path / "backupScript_log_20251122.txt"
    p.write_text(SAMPLE_LOG, encoding="utf-8")
    return str(p)


def test_parse_log(tmp_path):
    data = report.parse_log(_write_log(tmp_path))
    assert data.title.startswith("LOG - BackUp")
    assert "TEST FILM - 20251122" in data.subtitle or data.subtitle == "TEST FILM - 20251122"
    assert len(data.entries) == 4
    assert data.entries[0].what == "files"
    assert data.entries[0].timestamp == "2025-11-22 18:00:01"
    assert "AVVIO" in data.entries[0].message


def test_render_html(tmp_path):
    data = report.parse_log(_write_log(tmp_path))
    html = report.render_html(data)
    assert "<table>" in html
    assert "ODC_SPOLA_03" in html
    assert "Verifica OK" in html


def test_generate_writes_files(tmp_path):
    log_path = _write_log(tmp_path)
    out = report.generate(log_path)
    assert os.path.isfile(out["html"])
    assert out["entries"] == 4
    # Il PDF è opzionale (dipende da reportlab): se generato, esiste.
    if out["pdf"]:
        assert os.path.isfile(out["pdf"])
