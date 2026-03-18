"""Document data models for publishing-grade content."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class DocType(str, Enum):
    BOOK = "book"
    PAPER = "paper"
    ARTICLE = "article"
    WECHAT = "wechat"
    TECH_DOC = "tech_doc"
    REPORT = "report"


class OutputFormat(str, Enum):
    MARKDOWN = "md"
    LATEX = "latex"
    HTML = "html"
    PDF = "pdf"


class ElementType(str, Enum):
    PARAGRAPH = "paragraph"
    FIGURE = "figure"
    TABLE = "table"
    EQUATION = "equation"
    CODE_BLOCK = "code_block"
    QUOTE = "quote"
    LIST = "list"


@dataclass
class BibEntry:
    cite_key: str
    entry_type: str  # article, book, inproceedings, etc.
    title: str
    authors: list[str] = field(default_factory=list)
    year: str = ""
    journal: str = ""
    publisher: str = ""
    url: str = ""
    doi: str = ""
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class FigureSpec:
    fig_id: str          # e.g. "fig:architecture"
    description: str     # prompt for generation
    caption: str = ""
    style: str = "illustration"  # illustration, diagram, chart, photo
    source_path: str = ""  # after generation
    width: str = "80%"


@dataclass
class TableSpec:
    table_id: str
    caption: str
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    alignment: list[str] = field(default_factory=list)  # "l", "c", "r"


@dataclass
class EquationSpec:
    eq_id: str
    latex: str
    caption: str = ""
    inline: bool = False


@dataclass
class ContentElement:
    element_id: str
    element_type: ElementType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Section:
    section_id: str
    title: str
    level: int = 1
    number: str = ""
    content: str = ""
    elements: list[ContentElement] = field(default_factory=list)
    subsections: list[Section] = field(default_factory=list)


@dataclass
class ReviewIssue:
    severity: str  # critical, major, minor
    location: str  # section_id or general
    issue: str
    suggestion: str


@dataclass
class ReviewResult:
    pass_name: str
    reviewer: str
    model: str
    issues: list[ReviewIssue] = field(default_factory=list)
    approved: bool = False
    summary: str = ""


@dataclass
class DocumentSpec:
    doc_type: DocType
    title: str
    language: str = "zh-CN"
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    target_audience: str = ""
    sections: list[Section] = field(default_factory=list)
    bibliography: list[BibEntry] = field(default_factory=list)
    figures: list[FigureSpec] = field(default_factory=list)
    tables: list[TableSpec] = field(default_factory=list)
    equations: list[EquationSpec] = field(default_factory=list)
    output_formats: list[OutputFormat] = field(default_factory=lambda: [OutputFormat.MARKDOWN])
    reviews: list[ReviewResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
