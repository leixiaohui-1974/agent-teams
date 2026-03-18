"""Format conversion: Markdown, LaTeX, HTML (WeChat), PDF."""
from __future__ import annotations

import subprocess
from pathlib import Path

from agent_teams.publishing.models import DocumentSpec, OutputFormat


class FormatConverter:
    """Unified document format conversion."""

    def convert(self, content: str, doc: DocumentSpec, target: OutputFormat, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        stem = doc.title.replace(" ", "_")[:40]

        if target == OutputFormat.MARKDOWN:
            return self._save(content, output_dir / f"{stem}.md")

        elif target == OutputFormat.LATEX:
            latex = self._to_latex(content, doc)
            return self._save(latex, output_dir / f"{stem}.tex")

        elif target == OutputFormat.HTML:
            html = self._to_html(content, doc)
            return self._save(html, output_dir / f"{stem}.html")

        elif target == OutputFormat.PDF:
            return self._to_pdf(content, doc, output_dir, stem)

        return self._save(content, output_dir / f"{stem}.md")

    def _save(self, content: str, path: Path) -> Path:
        path.write_text(content, encoding="utf-8")
        return path

    def _to_latex(self, content: str, doc: DocumentSpec) -> str:
        is_chinese = "zh" in doc.language
        preamble = [
            "\\documentclass[12pt,a4paper]{article}",
            "\\usepackage[utf8]{inputenc}",
            "\\usepackage{amsmath,amssymb,amsfonts}",
            "\\usepackage{graphicx}",
            "\\usepackage{hyperref}",
            "\\usepackage{booktabs}",
            "\\usepackage{listings}",
            "\\usepackage[margin=2.5cm]{geometry}",
        ]
        if is_chinese:
            preamble.append("\\usepackage{xeCJK}")
            preamble.append("\\setCJKmainfont{SimSun}")
        preamble += [
            f"\\title{{{doc.title}}}",
            f"\\author{{{', '.join(doc.authors) or 'Agent Teams'}}}",
            "\\date{\\today}",
            "\\begin{document}",
            "\\maketitle",
        ]
        if doc.abstract:
            preamble += ["\\begin{abstract}", doc.abstract, "\\end{abstract}"]
        # Simple MD -> LaTeX conversion for body
        body = self._md_to_latex_body(content)
        return "\n".join(preamble) + "\n\n" + body + "\n\n\\end{document}"

    def _md_to_latex_body(self, md: str) -> str:
        """Basic Markdown to LaTeX body conversion."""
        import re
        text = md
        # Headings
        text = re.sub(r'^#### (.+)$', r'\\paragraph{\1}', text, flags=re.M)
        text = re.sub(r'^### (.+)$', r'\\subsubsection{\1}', text, flags=re.M)
        text = re.sub(r'^## (.+)$', r'\\subsection{\1}', text, flags=re.M)
        text = re.sub(r'^# (.+)$', r'\\section{\1}', text, flags=re.M)
        # Bold, italic
        text = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', text)
        text = re.sub(r'\*(.+?)\*', r'\\textit{\1}', text)
        # Code blocks
        text = re.sub(r'```(\w*)\n(.*?)```', r'\\begin{lstlisting}[language=\1]\n\2\\end{lstlisting}', text, flags=re.S)
        text = re.sub(r'`(.+?)`', r'\\texttt{\1}', text)
        return text

    def _to_html(self, content: str, doc: DocumentSpec) -> str:
        """Generate WeChat-compatible HTML with inline CSS."""
        import re
        html_body = content
        # Headings
        html_body = re.sub(r'^#### (.+)$', r'<h4 style="font-size:16px;margin:20px 0 10px">\1</h4>', html_body, flags=re.M)
        html_body = re.sub(r'^### (.+)$', r'<h3 style="font-size:18px;margin:24px 0 12px">\1</h3>', html_body, flags=re.M)
        html_body = re.sub(r'^## (.+)$', r'<h2 style="font-size:20px;margin:28px 0 14px">\1</h2>', html_body, flags=re.M)
        html_body = re.sub(r'^# (.+)$', r'<h1 style="font-size:24px;margin:32px 0 16px">\1</h1>', html_body, flags=re.M)
        # Bold, italic
        html_body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_body)
        html_body = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_body)
        # Code
        html_body = re.sub(r'```(\w*)\n(.*?)```',
            r'<pre style="background:#f6f8fa;padding:16px;border-radius:6px;overflow-x:auto;font-size:14px;line-height:1.6">\2</pre>',
            html_body, flags=re.S)
        html_body = re.sub(r'`(.+?)`',
            r'<code style="background:#f0f0f0;padding:2px 6px;border-radius:3px;font-size:14px">\1</code>', html_body)
        # Paragraphs
        html_body = re.sub(r'\n\n+', '</p><p style="margin:16px 0;line-height:1.8">', html_body)
        # Horizontal rules
        html_body = html_body.replace('---', '<hr style="border:none;border-top:1px solid #eee;margin:24px 0">')

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>{doc.title}</title></head>
<body style="max-width:680px;margin:0 auto;padding:20px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:16px;color:#333;line-height:1.8">
<h1 style="font-size:28px;text-align:center;margin-bottom:8px">{doc.title}</h1>
<p style="text-align:center;color:#999;font-size:14px">{', '.join(doc.authors) or 'Agent Teams'}</p>
<hr style="border:none;border-top:1px solid #eee;margin:24px 0">
<p style="margin:16px 0;line-height:1.8">{html_body}</p>
</body>
</html>"""

    def _to_pdf(self, content: str, doc: DocumentSpec, output_dir: Path, stem: str) -> Path:
        """Convert to PDF via pandoc or xelatex."""
        md_path = output_dir / f"{stem}.md"
        pdf_path = output_dir / f"{stem}.pdf"
        md_path.write_text(content, encoding="utf-8")

        is_chinese = "zh" in doc.language

        # Try pandoc first
        cmd = ["pandoc", str(md_path), "-o", str(pdf_path), "--pdf-engine=xelatex"]
        if is_chinese:
            cmd += ["-V", "CJKmainfont=SimSun", "-V", "geometry:margin=2.5cm"]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=120)
            if r.returncode == 0:
                return pdf_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Fallback: generate LaTeX, compile with xelatex
        tex_path = output_dir / f"{stem}.tex"
        latex = self._to_latex(content, doc)
        tex_path.write_text(latex, encoding="utf-8")
        try:
            subprocess.run(
                ["xelatex", "-interaction=nonstopmode", f"-output-directory={output_dir}", str(tex_path)],
                capture_output=True, timeout=120,
            )
            if pdf_path.exists():
                return pdf_path
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # If all fails, return the markdown
        return md_path
