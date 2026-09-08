import os

from dm_backup import mailer
from dm_backup.config import ProjectConfig, parse_flag, parse_recipients


def test_render_text_placeholders():
    out = mailer.render_text(
        "Report di {FILM}, giornata {DAY} del {DATA}.", "TQCC", "DAY023_20260525"
    )
    assert out == "Report di TQCC, giornata DAY023_20260525 del 20260525."


def test_render_text_without_date_part():
    assert mailer.render_text("{DATA}", "F", "DAY023") == ""


def test_parse_recipients_from_comma_string():
    assert parse_recipients(" a@b.com,c@d.com , ") == ["a@b.com", "c@d.com"]


def test_parse_recipients_from_list_and_empty():
    assert parse_recipients(["a@b.com", " c@d.com"]) == ["a@b.com", "c@d.com"]
    assert parse_recipients("") == []
    assert parse_recipients(None) == []


def test_parse_flag_yes_no():
    for yes in ["y", "Y", "si", "sì", "true", "1", True]:
        assert parse_flag(yes) is True
    for no in ["n", "no", "false", "0", False, None]:
        assert parse_flag(no) is False


def test_collect_attachments(tmp_path):
    reports = tmp_path / "03_REPORTS"
    reports.mkdir()
    (reports / "Bin Report.pdf").write_text("x")
    (reports / "Sound Report.pdf").write_text("x")
    (reports / ".DS_Store").write_text("x")  # va ignorato
    pdf = tmp_path / "log_report.pdf"
    pdf.write_text("x")

    found = mailer.collect_attachments(str(reports), str(pdf))
    assert [os.path.basename(p) for p in found] == [
        "Bin Report.pdf", "Sound Report.pdf", "log_report.pdf",
    ]


def test_collect_attachments_can_exclude(tmp_path):
    reports = tmp_path / "03_REPORTS"
    reports.mkdir()
    (reports / "Bin Report.pdf").write_text("x")
    pdf = tmp_path / "log_report.pdf"
    pdf.write_text("x")

    only_day = mailer.collect_attachments(str(reports), str(pdf), attach_report_pdf=False)
    assert [os.path.basename(p) for p in only_day] == ["Bin Report.pdf"]

    only_ours = mailer.collect_attachments(str(reports), str(pdf), attach_day_reports=False)
    assert [os.path.basename(p) for p in only_ours] == ["log_report.pdf"]


def test_collect_attachments_missing_paths(tmp_path):
    assert mailer.collect_attachments(str(tmp_path / "nope"), None) == []


def test_build_applescript_contains_recipients_and_attachments():
    script = mailer.build_applescript(
        ["a@b.com", "c@d.com"], "Oggetto", "Riga1\nRiga2", ["/tmp/report.pdf"],
    )
    assert 'address:"a@b.com"' in script
    assert 'address:"c@d.com"' in script
    assert 'subject:"Oggetto"' in script
    assert 'POSIX file "/tmp/report.pdf"' in script
    # La bozza va mostrata, mai inviata da sola.
    assert "visible:true" in script
    assert "send " not in script


def test_build_applescript_escapes_quotes():
    script = mailer.build_applescript([], 'Report "urgente"', "", [])
    assert 'subject:"Report \\"urgente\\""' in script


def test_email_config_from_yaml_dict():
    cfg = ProjectConfig.from_dict({
        "project": {"film": "TQCC"},
        "paths": {"project_root": "/tmp/x"},
        "email": {
            "invia_email": "y",
            "mailinglist": "uno@x.com, due@x.com",
            "oggetto": "Report {DAY}",
            "testo": "Ciao {DAY}",
            "allega_report_pdf": "n",
        },
    })
    assert cfg.email.enabled is True
    assert cfg.email.recipients == ["uno@x.com", "due@x.com"]
    assert cfg.email.attach_day_reports is True
    assert cfg.email.attach_report_pdf is False


def test_email_disabled_by_default():
    cfg = ProjectConfig.from_dict({
        "project": {"film": "TQCC"},
        "paths": {"project_root": "/tmp/x"},
    })
    assert cfg.email.enabled is False
    assert cfg.email.recipients == []
