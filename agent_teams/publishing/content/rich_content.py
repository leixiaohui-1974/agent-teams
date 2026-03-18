"""Rich content handling: figures, tables, math, references, numbering."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_teams.publishing.models import (
    BibEntry, DocumentSpec, EquationSpec, FigureSpec, OutputFormat, Section, TableSpec,
)


# -- Tables --

class TableManager:
    def to_markdown(self, t: TableSpec) -> str:
        align_map = {"l": ":---", "c": ":---:", "r": "---:"}
        header = "| " + " | ".join(t.headers) + " |"
        aligns = t.alignment or ["l"] * len(t.headers)
        sep = "| " + " | ".join(align_map.get(a, "---") for a in aligns) + " |"
        rows = "\n".join("| " + " | ".join(row) + " |" for row in t.rows)
        caption = f"\n*{t.caption}*" if t.caption else ""
        return f"{header}\n{sep}\n{rows}{caption}"

    def to_latex(self, t: TableSpec) -> str:
        align_str = "".join(a if a in "lcr" else "l" for a in (t.alignment or ["l"] * len(t.headers)))
        lines = [
            f"\\begin{{table}}[htbp]",
            f"\\centering",
            f"\\caption{{{t.caption}}}",
            f"\\label{{{t.table_id}}}",
            f"\\begin{{tabular}}{{{align_str}}}",
            "\\hline",
            " & ".join(f"\\textbf{{{h}}}" for h in t.headers) + " \\\\",
            "\\hline",
        ]
        for row in t.rows:
            lines.append(" & ".join(row) + " \\\\")
        lines += ["\\hline", "\\end{tabular}", "\\end{table}"]
        return "\n".join(lines)

    def to_html(self, t: TableSpec) -> str:
        rows_html = ""
        header_html = "".join(f"<th style='padding:8px;border:1px solid #ddd;background:#f5f5f5'>{h}</th>" for h in t.headers)
        rows_html += f"<tr>{header_html}</tr>"
        for row in t.rows:
            cells = "".join(f"<td style='padding:8px;border:1px solid #ddd'>{c}</td>" for c in row)
            rows_html += f"<tr>{cells}</tr>"
        caption = f"<caption style='font-weight:bold;margin-bottom:8px'>{t.caption}</caption>" if t.caption else ""
        return f"<table style='border-collapse:collapse;width:100%;margin:16px 0'>{caption}{rows_html}</table>"


# -- Math --

class MathManager:
    def render(self, latex: str, fmt: OutputFormat, inline: bool = False) -> str:
        if fmt == OutputFormat.MARKDOWN:
            return f"${latex}$" if inline else f"$${latex}$$"
        elif fmt == OutputFormat.LATEX:
            return f"\\({latex}\\)" if inline else f"\\[{latex}\\]"
        elif fmt == OutputFormat.HTML:
            if inline:
                return f'<span class="math">${latex}$</span>'
            return f'<div class="math" style="text-align:center;margin:16px 0">$${latex}$$</div>'
        return latex

    def numbered_equation(self, eq: EquationSpec, number: int, fmt: OutputFormat) -> str:
        if fmt == OutputFormat.LATEX:
            return f"\\begin{{equation}}\\label{{{eq.eq_id}}}\n{eq.latex}\n\\end{{equation}}"
        elif fmt == OutputFormat.MARKDOWN:
            return f"$${eq.latex} \\tag{{{number}}}$$"
        else:
            return f'<div style="text-align:center;margin:16px 0">$${eq.latex}$$ ({number})</div>'


# -- References --

class ReferenceManager:
    def __init__(self):
        self.entries: dict[str, BibEntry] = {}

    def add(self, entry: BibEntry) -> None:
        self.entries[entry.cite_key] = entry

    def cite(self, key: str) -> str:
        entry = self.entries.get(key)
        if not entry:
            return f"[{key}?]"
        authors = entry.authors[0].split(",")[0] if entry.authors else "Unknown"
        if len(entry.authors) > 1:
            authors += " et al."
        return f"({authors}, {entry.year})"

    def format_bibliography(self, fmt: OutputFormat) -> str:
        if not self.entries:
            return ""
        lines = []
        for i, (key, e) in enumerate(sorted(self.entries.items()), 1):
            authors = ", ".join(e.authors) if e.authors else "Unknown"
            if fmt == OutputFormat.LATEX:
                lines.append(f"\\bibitem{{{key}}} {authors}. {e.title}. {e.journal} {e.year}.")
            else:
                lines.append(f"[{i}] {authors}. *{e.title}*. {e.journal}, {e.year}.")
        if fmt == OutputFormat.LATEX:
            return "\\begin{thebibliography}{99}\n" + "\n".join(lines) + "\n\\end{thebibliography}"
        return "## References\n\n" + "\n\n".join(lines)

    def export_bibtex(self) -> str:
        entries = []
        for key, e in self.entries.items():
            fields = [f"  title = {{{e.title}}}"]
            if e.authors:
                fields.append(f"  author = {{{' and '.join(e.authors)}}}")
            if e.year:
                fields.append(f"  year = {{{e.year}}}")
            if e.journal:
                fields.append(f"  journal = {{{e.journal}}}")
            if e.doi:
                fields.append(f"  doi = {{{e.doi}}}")
            if e.url:
                fields.append(f"  url = {{{e.url}}}")
            entries.append(f"@{e.entry_type}{{{key},\n" + ",\n".join(fields) + "\n}")
        return "\n\n".join(entries)


# -- Numbering & Cross-references --

class NumberingEngine:
    def assign_numbers(self, sections: list[Section], prefix: str = "") -> None:
        for i, sec in enumerate(sections, 1):
            sec.number = f"{prefix}{i}" if prefix else str(i)
            self.assign_numbers(sec.subsections, f"{sec.number}.")

    def resolve_refs(self, content: str, fig_map: dict[str, str], tbl_map: dict[str, str], eq_map: dict[str, str]) -> str:
        """Replace {ref:fig:id} with 'Figure X', etc."""
        for fid, num in fig_map.items():
            content = content.replace(f"{{ref:{fid}}}", f"Figure {num}")
        for tid, num in tbl_map.items():
            content = content.replace(f"{{ref:{tid}}}", f"Table {num}")
        for eid, num in eq_map.items():
            content = content.replace(f"{{ref:{eid}}}", f"Eq. ({num})")
        return content


# -- Figures (Mermaid/PlantUML diagrams) --

class DiagramRenderer:
    @staticmethod
    def render_mermaid(source: str, output_path: Path) -> bool:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            r = subprocess.run(
                ["mmdc", "-i", "-", "-o", str(output_path), "-b", "transparent"],
                input=source, capture_output=True, text=True, timeout=30,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    @staticmethod
    def has_mermaid() -> bool:
        try:
            r = subprocess.run(["mmdc", "--version"], capture_output=True, timeout=5)
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
