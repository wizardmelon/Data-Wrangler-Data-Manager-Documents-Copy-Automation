"""Report giornaliero dei documenti copiati (HTML + PDF).

Dopo la copia in modalità `files`, il log grezzo del giorno viene parsato e
trasformato in un "delivery report" leggibile da consegnare alla produzione.
L'HTML non ha dipendenze; il PDF usa `reportlab` (opzionale: se non installato,
si genera solo l'HTML).
"""

from __future__ import annotations

import html
import os
import re
from dataclasses import dataclass, field
from typing import List, Optional

_LINE_RE = re.compile(r"^\[(?P<what>[^\]]+?)\s*-->\s*(?P<ts>[^\]]+)\]\s*(?P<msg>.*)$")


@dataclass
class LogEntry:
    what: str
    timestamp: str
    message: str


@dataclass
class ReportData:
    header: List[str] = field(default_factory=list)
    entries: List[LogEntry] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.header[0] if self.header else "Report giornaliero"

    @property
    def subtitle(self) -> str:
        # La riga con "Film - Data" è tipicamente la prima non vuota dopo il titolo.
        for line in self.header[1:]:
            if line.strip():
                return line.strip()
        return ""


def parse_log(log_path: str) -> ReportData:
    data = ReportData()
    with open(log_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            m = _LINE_RE.match(line)
            if m:
                data.entries.append(
                    LogEntry(m.group("what"), m.group("ts").strip(), m.group("msg"))
                )
            else:
                # Righe di intestazione (prima della prima voce con timestamp).
                if not data.entries:
                    data.header.append(line)
    return data


def render_html(data: ReportData) -> str:
    rows = "\n".join(
        "<tr>"
        f"<td class='ts'>{html.escape(e.timestamp)}</td>"
        f"<td class='what'>{html.escape(e.what)}</td>"
        f"<td>{html.escape(e.message)}</td>"
        "</tr>"
        for e in data.entries
    )
    header_html = "<br>".join(html.escape(h) for h in data.header if h.strip())
    return f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<title>{html.escape(data.title)}</title>
<style>
 body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; margin: 40px; color: #1a1a1a; }}
 h1 {{ font-size: 20px; margin-bottom: 4px; }}
 .meta {{ color: #555; font-size: 13px; margin-bottom: 24px; line-height: 1.5; }}
 table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
 th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid #e2e2e2; vertical-align: top; }}
 th {{ background: #f4f4f4; }}
 td.ts {{ white-space: nowrap; color: #666; font-variant-numeric: tabular-nums; }}
 td.what {{ white-space: nowrap; font-weight: 600; }}
</style></head><body>
<h1>{html.escape(data.title)}</h1>
<div class="meta">{header_html}</div>
<table>
<thead><tr><th>Orario</th><th>Fase</th><th>Messaggio</th></tr></thead>
<tbody>
{rows}
</tbody></table>
</body></html>
"""


def render_pdf(data: ReportData, pdf_path: str) -> Optional[str]:
    """Genera il PDF con reportlab. Ritorna il percorso o None se reportlab manca."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        )
    except ImportError:  # pragma: no cover - dipende dall'ambiente
        return None

    styles = getSampleStyleSheet()
    left = right = 15 * mm
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            topMargin=20 * mm, bottomMargin=20 * mm,
                            leftMargin=left, rightMargin=right)

    # wordWrap="CJK" manda a capo anche a metà parola: i messaggi contengono
    # percorsi lunghi senza spazi, che altrimenti sborderebbero dalla cella.
    cell = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=8,
                          leading=10, spaceBefore=0, spaceAfter=0, wordWrap="CJK")
    cell_head = ParagraphStyle("cell_head", parent=cell, fontName="Helvetica-Bold")

    flow = [Paragraph(html.escape(data.title), styles["Title"])]
    for line in data.header[1:]:
        if line.strip():
            flow.append(Paragraph(html.escape(line), styles["Normal"]))
    flow.append(Spacer(1, 8 * mm))

    def cells(values, style):
        return [Paragraph(html.escape(v), style) for v in values]

    table_data = [cells(["Orario", "Fase", "Messaggio"], cell_head)]
    for e in data.entries:
        table_data.append(cells([e.timestamp, e.what, e.message], cell))

    # Le colonne devono stare dentro l'area stampabile (A4 meno i margini).
    usable = A4[0] - left - right
    table = Table(table_data, colWidths=[34 * mm, 22 * mm, usable - 56 * mm],
                  repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    flow.append(table)
    doc.build(flow)
    return pdf_path


def generate(log_path: str, out_dir: Optional[str] = None) -> dict:
    """Parsa il log e scrive HTML (+ PDF se possibile) accanto al log."""
    data = parse_log(log_path)
    out_dir = out_dir or os.path.dirname(log_path)
    base = os.path.splitext(os.path.basename(log_path))[0]

    html_path = os.path.join(out_dir, f"{base}_report.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(render_html(data))

    pdf_path = render_pdf(data, os.path.join(out_dir, f"{base}_report.pdf"))
    return {"html": html_path, "pdf": pdf_path, "entries": len(data.entries)}
