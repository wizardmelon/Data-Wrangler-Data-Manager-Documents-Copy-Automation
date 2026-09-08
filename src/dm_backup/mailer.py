"""Bozza email di fine giornata con i report allegati.

Prepara in Mail.app una mail **già pronta ma non inviata**: destinatari, testo e
allegati sono compilati dallo script, l'invio resta un gesto umano. Su una
mailing list di produzione questo evita che una giornata storta parta lo stesso.

Il metodo `mailto:` (quello dell'esempio Silverstack) non è utilizzabile qui
perché non supporta gli allegati: si usa AppleScript su Mail.app.
"""

from __future__ import annotations

import os
from typing import List, Optional


def render_text(template: str, film: str, day_name: str) -> str:
    """Sostituisce i segnaposto {DAY}, {FILM} e {DATA} nel testo dello YAML.

    {DAY} = DAY023_20260525, {DATA} = 20260525 (la parte dopo l'underscore).
    """
    date_part = day_name.split("_", 1)[1] if "_" in day_name else ""
    return (
        template.replace("{DAY}", day_name)
        .replace("{FILM}", film)
        .replace("{DATA}", date_part)
    )


def collect_attachments(reports_dir: str, report_pdf: Optional[str],
                        attach_day_reports: bool = True,
                        attach_report_pdf: bool = True) -> List[str]:
    """Report della giornata (da `reports_dir`) più il report riepilogativo."""
    paths: List[str] = []
    if attach_day_reports and os.path.isdir(reports_dir):
        for name in sorted(os.listdir(reports_dir)):
            full = os.path.join(reports_dir, name)
            if os.path.isfile(full) and not name.startswith("."):
                paths.append(full)
    if attach_report_pdf and report_pdf and os.path.isfile(report_pdf):
        paths.append(report_pdf)
    return paths


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def build_applescript(recipients: List[str], subject: str, body: str,
                      attachments: List[str], timeout_seconds: int = 300) -> str:
    """AppleScript che crea la bozza in Mail.app e la mostra (senza inviarla).

    Il blocco `with timeout` alza il limite di default degli AppleEvent (60s):
    la prima volta macOS chiede il permesso di controllare Mail e, finché non si
    risponde, l'evento resta in attesa — con 60s si otteneva un errore -1712.
    """
    lines = [
        'tell application "Mail"',
        f'  with timeout of {timeout_seconds} seconds',
        '    set newMessage to make new outgoing message with properties '
        f'{{subject:"{_escape(subject)}", content:"{_escape(body)}", visible:true}}',
        '    tell newMessage',
    ]
    for address in recipients:
        lines.append(
            '      make new to recipient at end of to recipients with properties '
            f'{{address:"{_escape(address)}"}}'
        )
    if attachments:
        # Gli allegati vanno aggiunti al contenuto, dopo che è stato impostato.
        lines.append('      tell content')
        for path in attachments:
            lines.append(
                '        make new attachment with properties '
                f'{{file name:(POSIX file "{_escape(path)}")}} '
                'at after the last paragraph'
            )
        lines.append('      end tell')
    lines += ['    end tell', '    activate', '  end timeout', 'end tell']
    return "\n".join(lines)
