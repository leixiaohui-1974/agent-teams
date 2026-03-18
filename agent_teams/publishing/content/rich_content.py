"""Rich content: Nano Banana优先的图片/公式/表格 + 编号/引用系统."""
from __future__ import annotations

import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_teams.publishing.models import (
    BibEntry, DocumentSpec, EquationSpec, FigureSpec, OutputFormat, Section, TableSpec,
)


# =============================================================================
# Nano Banana Visual Generator (图片、公式图、表格图)
# =============================================================================

class NanoBananaRenderer:
    """用 Nano Banana (Gemini) 生成插图、图表、封面等图片内容。

    注意：公式和表格不使用图片，用 LaTeX/Markdown/HTML 文本格式（更精确、可编辑）。
    Nano Banana 只用于：插图、示意图、流程图、封面、概念图等视觉内容。
    """

    def __init__(self, client=None):
        self._client = client

    async def _get_client(self):
        if self._client is None:
            from agent_teams.core.client import get_client
            self._client = get_client()
        return self._client

    async def generate_illustration(self, description: str, output_dir: Path, name: str) -> str:
        """生成插图/示意图。"""
        client = await self._get_client()
        prompt = (
            f"Generate a high-quality, professional illustration: {description}\n"
            "Style: clean, modern, suitable for publication. No text watermarks."
        )
        try:
            resp = await client.generate_image_via_gemini(prompt, model="gemini-2.5-flash")
            content = resp["choices"][0]["message"]["content"]
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / f"{name}.md"
            path.write_text(f"# Image: {name}\n\nPrompt: {description}\n\nResponse:\n{content}", encoding="utf-8")
            return str(path)
        except Exception as e:
            return f"[Image generation failed: {e}]"

    async def generate_diagram(self, description: str, output_dir: Path, name: str) -> str:
        """生成流程图/架构图/概念图。"""
        client = await self._get_client()
        prompt = (
            f"Create a professional diagram/flowchart as an image:\n\n"
            f"{description}\n\n"
            f"Style: clean lines, modern design, clear labels, professional color scheme, "
            f"suitable for publication in a book or article."
        )
        try:
            resp = await client.generate_image_via_gemini(prompt, model="gemini-2.5-flash")
            content = resp["choices"][0]["message"]["content"]
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / f"diag_{name}.md"
            path.write_text(f"# Diagram: {name}\n\n{description}\n\nResponse:\n{content}", encoding="utf-8")
            return str(path)
        except Exception:
            return ""

    async def generate_cover(self, title: str, style: str, output_dir: Path) -> str:
        """生成封面图片（公众号封面、书籍封面等）。"""
        client = await self._get_client()
        prompt = (
            f"Create a professional cover image for: '{title}'\n"
            f"Style: {style}. High quality, visually striking, no text in the image."
        )
        try:
            resp = await client.generate_image_via_gemini(prompt, model="gemini-2.5-flash")
            content = resp["choices"][0]["message"]["content"]
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / "cover.md"
            path.write_text(f"# Cover: {title}\n\nStyle: {style}\n\nResponse:\n{content}", encoding="utf-8")
            return str(path)
        except Exception:
            return ""


# =============================================================================
# 表格管理器 (文本格式 + Nano Banana图片双模式)
# =============================================================================

class TableManager:
    """表格渲染：优先 Nano Banana 图片，降级到文本格式。"""

    def to_markdown(self, t: TableSpec) -> str:
        align_map = {"l": ":---", "c": ":---:", "r": "---:"}
        header = "| " + " | ".join(t.headers) + " |"
        aligns = t.alignment or ["l"] * len(t.headers)
        sep = "| " + " | ".join(align_map.get(a, "---") for a in aligns) + " |"
        rows = "\n".join("| " + " | ".join(row) + " |" for row in t.rows)
        caption = f"\n\n**Table: {t.caption}**" if t.caption else ""
        return f"{header}\n{sep}\n{rows}{caption}"

    def to_latex(self, t: TableSpec) -> str:
        align_str = "".join(a if a in "lcr" else "l" for a in (t.alignment or ["l"] * len(t.headers)))
        lines = [
            f"\\begin{{table}}[htbp]",
            f"\\centering",
            f"\\caption{{{t.caption}}}",
            f"\\label{{{t.table_id}}}",
            f"\\begin{{tabular}}{{{align_str}}}",
            "\\toprule",
            " & ".join(f"\\textbf{{{h}}}" for h in t.headers) + " \\\\",
            "\\midrule",
        ]
        for row in t.rows:
            lines.append(" & ".join(row) + " \\\\")
        lines += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
        return "\n".join(lines)

    def to_html(self, t: TableSpec) -> str:
        rows_html = ""
        header_html = "".join(
            f"<th style='padding:10px 14px;border-bottom:2px solid #333;background:#f7f7f7;"
            f"font-weight:bold;text-align:left'>{h}</th>" for h in t.headers
        )
        rows_html += f"<tr>{header_html}</tr>"
        for i, row in enumerate(t.rows):
            bg = "#fff" if i % 2 == 0 else "#fafafa"
            cells = "".join(
                f"<td style='padding:8px 14px;border-bottom:1px solid #eee;background:{bg}'>{c}</td>"
                for c in row
            )
            rows_html += f"<tr>{cells}</tr>"
        caption = (
            f"<caption style='font-weight:bold;font-size:14px;margin-bottom:10px;"
            f"text-align:center;color:#555'>{t.caption}</caption>"
            if t.caption else ""
        )
        return (
            f"<table style='border-collapse:collapse;width:100%;margin:20px 0;"
            f"font-size:15px;line-height:1.6'>{caption}{rows_html}</table>"
        )

    def to_description(self, t: TableSpec) -> str:
        """生成表格的文字描述，供 Nano Banana 渲染为图片。"""
        desc = f"Table: {t.caption}\n\nColumns: {', '.join(t.headers)}\n\nData:\n"
        for row in t.rows:
            desc += "  " + " | ".join(row) + "\n"
        return desc


# =============================================================================
# 公式管理器 (LaTeX文本 + Nano Banana图片双模式)
# =============================================================================

class MathManager:
    """公式渲染：LaTeX输出用文本，HTML/公众号优先 Nano Banana 图片。"""

    def render(self, latex: str, fmt: OutputFormat, inline: bool = False) -> str:
        """文本模式渲染（LaTeX/Markdown）。"""
        if fmt == OutputFormat.MARKDOWN:
            return f"${latex}$" if inline else f"\n$$\n{latex}\n$$\n"
        elif fmt == OutputFormat.LATEX:
            return f"\\({latex}\\)" if inline else f"\\[\n{latex}\n\\]"
        elif fmt == OutputFormat.HTML:
            # HTML场景建议用 Nano Banana 图片替代，这里做文本降级
            if inline:
                return f'<code style="background:#f5f5f5;padding:2px 4px;font-family:serif">{latex}</code>'
            return (
                f'<div style="text-align:center;margin:20px 0;padding:16px;'
                f'background:#fafafa;border-radius:4px;font-family:serif;font-size:18px">'
                f'{latex}</div>'
            )
        return latex

    def numbered_equation(self, eq: EquationSpec, number: int, fmt: OutputFormat) -> str:
        if fmt == OutputFormat.LATEX:
            return (
                f"\\begin{{equation}}\n"
                f"\\label{{{eq.eq_id}}}\n"
                f"{eq.latex}\n"
                f"\\end{{equation}}"
            )
        elif fmt == OutputFormat.MARKDOWN:
            return f"\n$$\n{eq.latex} \\tag{{{number}}}\n$$\n"
        else:
            return (
                f'<div style="display:flex;align-items:center;justify-content:center;'
                f'margin:20px 0;gap:20px">'
                f'<span style="font-family:serif;font-size:18px">{eq.latex}</span>'
                f'<span style="color:#999">({number})</span></div>'
            )


# =============================================================================
# 参考文献管理器
# =============================================================================

class ReferenceManager:
    """完整的参考文献管理：添加、引用、格式化、导出BibTeX。"""

    def __init__(self):
        self.entries: dict[str, BibEntry] = {}
        self._cite_order: list[str] = []  # 按引用顺序

    def add(self, entry: BibEntry) -> None:
        self.entries[entry.cite_key] = entry

    def cite(self, key: str, style: str = "numbered") -> str:
        """生成行内引用标记。"""
        if key not in self._cite_order:
            self._cite_order.append(key)
        num = self._cite_order.index(key) + 1

        entry = self.entries.get(key)
        if not entry:
            return f"[{num}]"

        if style == "numbered":
            return f"[{num}]"
        elif style == "author-year":
            first_author = entry.authors[0].split(",")[0] if entry.authors else "Unknown"
            if len(entry.authors) > 2:
                first_author += " et al."
            elif len(entry.authors) == 2:
                second = entry.authors[1].split(",")[0]
                first_author += f" & {second}"
            return f"({first_author}, {entry.year})"
        return f"[{num}]"

    def format_bibliography(self, fmt: OutputFormat, style: str = "numbered") -> str:
        """按引用顺序生成参考文献列表。"""
        if not self._cite_order and not self.entries:
            return ""

        # 用引用顺序，未引用的附加到末尾
        ordered_keys = list(self._cite_order)
        for key in self.entries:
            if key not in ordered_keys:
                ordered_keys.append(key)

        lines = []
        for i, key in enumerate(ordered_keys, 1):
            e = self.entries.get(key)
            if not e:
                continue
            authors = ", ".join(e.authors) if e.authors else "Unknown"

            if fmt == OutputFormat.LATEX:
                lines.append(f"\\bibitem{{{key}}} {authors}. \\textit{{{e.title}}}. {e.journal}, {e.year}.")
            elif fmt == OutputFormat.HTML:
                lines.append(
                    f'<p style="margin:8px 0;padding-left:28px;text-indent:-28px;font-size:14px;line-height:1.6">'
                    f'[{i}] {authors}. <em>{e.title}</em>. {e.journal}, {e.year}.'
                    f'{f" DOI: {e.doi}" if e.doi else ""}</p>'
                )
            else:  # Markdown
                doi_str = f" DOI: {e.doi}" if e.doi else ""
                url_str = f" [{e.url}]({e.url})" if e.url else ""
                lines.append(f"[{i}] {authors}. *{e.title}*. {e.journal}, {e.year}.{doi_str}{url_str}")

        if fmt == OutputFormat.LATEX:
            return "\\begin{thebibliography}{99}\n" + "\n".join(lines) + "\n\\end{thebibliography}"
        elif fmt == OutputFormat.HTML:
            header = '<h2 style="font-size:20px;margin:32px 0 16px;border-bottom:1px solid #eee;padding-bottom:8px">参考文献</h2>'
            return header + "\n".join(lines)
        else:
            return "## 参考文献\n\n" + "\n\n".join(lines)

    def export_bibtex(self) -> str:
        """导出 BibTeX 格式文件内容。"""
        entries = []
        for key, e in self.entries.items():
            fields = [f"  title = {{{e.title}}}"]
            if e.authors:
                fields.append(f"  author = {{{' and '.join(e.authors)}}}")
            if e.year:
                fields.append(f"  year = {{{e.year}}}")
            if e.journal:
                fields.append(f"  journal = {{{e.journal}}}")
            if e.publisher:
                fields.append(f"  publisher = {{{e.publisher}}}")
            if e.doi:
                fields.append(f"  doi = {{{e.doi}}}")
            if e.url:
                fields.append(f"  url = {{{e.url}}}")
            for k, v in e.extra.items():
                fields.append(f"  {k} = {{{v}}}")
            entries.append(f"@{e.entry_type}{{{key},\n" + ",\n".join(fields) + "\n}")
        return "\n\n".join(entries)

    def resolve_citations(self, content: str, style: str = "numbered") -> str:
        """把文中的 [@key] 替换为实际引用标记。"""
        def replacer(m):
            key = m.group(1)
            return self.cite(key, style)
        return re.sub(r'\[@(\w+)\]', replacer, content)


# =============================================================================
# 编号引擎 (章节/图/表/公式统一编号 + 交叉引用)
# =============================================================================

class NumberingEngine:
    """统一编号系统：自动为章节、图、表、公式分配编号并解析交叉引用。"""

    def __init__(self):
        self.section_numbers: dict[str, str] = {}
        self.figure_numbers: dict[str, str] = {}
        self.table_numbers: dict[str, str] = {}
        self.equation_numbers: dict[str, str] = {}
        self._fig_counter = 0
        self._tbl_counter = 0
        self._eq_counter = 0

    def assign_section_numbers(self, sections: list[Section], prefix: str = "") -> None:
        """递归为章节分配层级编号: 1, 1.1, 1.1.1, ..."""
        for i, sec in enumerate(sections, 1):
            sec.number = f"{prefix}{i}" if prefix else str(i)
            self.section_numbers[sec.section_id] = sec.number
            self.assign_section_numbers(sec.subsections, f"{sec.number}.")

    def assign_figure_number(self, fig_id: str, chapter_num: str = "") -> str:
        """分配图片编号: Figure 1, Figure 2, ... 或 Figure 1.1 (按章)"""
        self._fig_counter += 1
        num = f"{chapter_num}.{self._fig_counter}" if chapter_num else str(self._fig_counter)
        self.figure_numbers[fig_id] = num
        return num

    def assign_table_number(self, tbl_id: str, chapter_num: str = "") -> str:
        self._tbl_counter += 1
        num = f"{chapter_num}.{self._tbl_counter}" if chapter_num else str(self._tbl_counter)
        self.table_numbers[tbl_id] = num
        return num

    def assign_equation_number(self, eq_id: str, chapter_num: str = "") -> str:
        self._eq_counter += 1
        num = f"{chapter_num}.{self._eq_counter}" if chapter_num else str(self._eq_counter)
        self.equation_numbers[eq_id] = num
        return num

    def resolve_all_refs(self, content: str, lang: str = "zh-CN") -> str:
        """解析所有交叉引用标记，替换为实际编号。

        支持标记格式:
          {ref:fig:id}  → 图 3 / Figure 3
          {ref:tbl:id}  → 表 2 / Table 2
          {ref:eq:id}   → 式(1) / Eq. (1)
          {ref:sec:id}  → 第2.1节 / Section 2.1
        """
        is_zh = "zh" in lang

        for fid, num in self.figure_numbers.items():
            label = f"图{num}" if is_zh else f"Figure {num}"
            content = content.replace(f"{{ref:fig:{fid}}}", label)
            content = content.replace(f"{{ref:{fid}}}", label)

        for tid, num in self.table_numbers.items():
            label = f"表{num}" if is_zh else f"Table {num}"
            content = content.replace(f"{{ref:tbl:{tid}}}", label)
            content = content.replace(f"{{ref:{tid}}}", label)

        for eid, num in self.equation_numbers.items():
            label = f"式({num})" if is_zh else f"Eq. ({num})"
            content = content.replace(f"{{ref:eq:{eid}}}", label)
            content = content.replace(f"{{ref:{eid}}}", label)

        for sid, num in self.section_numbers.items():
            label = f"第{num}节" if is_zh else f"Section {num}"
            content = content.replace(f"{{ref:sec:{sid}}}", label)
            content = content.replace(f"{{ref:{sid}}}", label)

        return content

    def auto_number_content(self, content: str, lang: str = "zh-CN") -> str:
        """扫描内容中的标记，自动分配编号，然后解析引用。

        扫描:
          ![caption](fig:xxx) → 自动分配图编号
          [Table: caption](tbl:xxx) → 自动分配表编号
          $$latex \\label{eq:xxx}$$ → 自动分配公式编号
        """
        is_zh = "zh" in lang

        # 图片编号: ![caption](fig:xxx)
        for m in re.finditer(r'!\[([^\]]*)\]\(fig:(\w+)\)', content):
            caption, fig_id = m.group(1), m.group(2)
            if fig_id not in self.figure_numbers:
                self.assign_figure_number(fig_id)
            num = self.figure_numbers[fig_id]
            label = f"图{num}" if is_zh else f"Figure {num}"
            content = content.replace(m.group(0), f"![{label}: {caption}](fig:{fig_id})")

        # 表格编号: [Table: caption](tbl:xxx)
        for m in re.finditer(r'\[Table:\s*([^\]]*)\]\(tbl:(\w+)\)', content):
            caption, tbl_id = m.group(1), m.group(2)
            if tbl_id not in self.table_numbers:
                self.assign_table_number(tbl_id)
            num = self.table_numbers[tbl_id]
            label = f"表{num}" if is_zh else f"Table {num}"
            content = content.replace(m.group(0), f"**{label}: {caption}**")

        # 公式编号: $$...\label{eq:xxx}$$
        for m in re.finditer(r'\$\$([^$]*?)\\label\{(eq:\w+)\}([^$]*?)\$\$', content):
            before, eq_id, after = m.group(1), m.group(2), m.group(3)
            if eq_id not in self.equation_numbers:
                self.assign_equation_number(eq_id)
            num = self.equation_numbers[eq_id]
            content = content.replace(m.group(0), f"$${before}{after} \\tag{{{num}}}$$")

        # 解析所有引用
        content = self.resolve_all_refs(content, lang)
        return content


# =============================================================================
# 后处理器：在输出前统一处理编号、引用、格式
# =============================================================================

class ContentPostProcessor:
    """对最终内容做统一后处理：编号、引用解析、格式转换。"""

    def __init__(self, lang: str = "zh-CN"):
        self.lang = lang
        self.numbering = NumberingEngine()
        self.references = ReferenceManager()
        self.tables = TableManager()
        self.math = MathManager()

    def process(self, content: str, fmt: OutputFormat = OutputFormat.MARKDOWN) -> str:
        """完整后处理流程。"""
        # 1. 自动编号（图、表、公式）
        content = self.numbering.auto_number_content(content, self.lang)

        # 2. 解析引用 [@key] → [1]
        content = self.references.resolve_citations(content)

        # 3. 附加参考文献列表
        bib = self.references.format_bibliography(fmt)
        if bib:
            content = content.rstrip() + "\n\n---\n\n" + bib

        return content


# =============================================================================
# Mermaid/PlantUML 图表 (作为 Nano Banana 的补充)
# =============================================================================

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
