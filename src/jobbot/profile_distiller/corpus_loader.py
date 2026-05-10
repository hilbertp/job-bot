"""Load every artifact under `data/corpus/` into a single in-memory bundle
ready for distillation.

PRD §7.4 FR-PRO-01.

Public API:
    load_corpus(root: Path) -> CorpusBundle

CorpusBundle structure:
    primary_cv        : str             — extracted plaintext of PRIMARY_*
    other_cvs         : list[CorpusDoc] — non-primary CVs (path + plaintext)
    cover_letters     : list[CorpusDoc]
    website_pages     : list[CorpusDoc]

Supported file types: .pdf, .docx, .md, .txt.
PDFs are extracted via pypdf or pdfplumber (Copilot picks one).
DOCX via python-docx.
.md / .txt read as UTF-8.

Behavior:
- Exactly ONE file per corpus must be prefixed `PRIMARY_`. If zero or more
  than one, raise CorpusError with a clear message.
- Files smaller than 200 chars are ignored with a warning (likely empty).
- Hidden files (`.gitkeep`, `.DS_Store`) are skipped silently.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
from pathlib import Path


class CorpusError(Exception):
    """Raised when the corpus on disk doesn't satisfy the PRD invariants."""


@dataclass
class CorpusDoc:
    path: Path
    text: str


@dataclass
class CorpusBundle:
    primary_cv: str
    other_cvs: list[CorpusDoc]
    cover_letters: list[CorpusDoc]
    website_pages: list[CorpusDoc]


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".md", ".txt"}
MIN_DOC_CHARS = 200


def _is_hidden(path: Path) -> bool:
    """PRD §7.4 FR-PRO-01: skip hidden corpus files silently."""
    return any(part.startswith(".") for part in path.parts)


def _iter_docs(root: Path) -> list[Path]:
    """PRD §7.4 FR-PRO-01: gather supported corpus docs in stable order."""
    if not root.exists():
        return []
    files = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES and not _is_hidden(p)
    ]
    return sorted(files, key=lambda p: str(p).lower())


def _read_pdf(path: Path) -> str:
    """PRD §7.4 FR-PRO-01: extract plaintext from PDF files."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise CorpusError(
            f"Cannot read PDF {path}: install 'pypdf' to enable PDF corpus files"
        ) from exc

    reader = PdfReader(str(path))
    chunks = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(chunks).strip()


def _read_docx(path: Path) -> str:
    """PRD §7.4 FR-PRO-01: extract plaintext from DOCX files."""
    try:
        from docx import Document
    except ImportError as exc:
        raise CorpusError(
            f"Cannot read DOCX {path}: install 'python-docx' to enable DOCX corpus files"
        ) from exc

    doc = Document(str(path))
    return "\n".join(paragraph.text for paragraph in doc.paragraphs).strip()


def _read_text(path: Path) -> str:
    """PRD §7.4 FR-PRO-01: read UTF-8 text corpus files."""
    return path.read_text(encoding="utf-8", errors="ignore").strip()


def _read_doc(path: Path) -> str:
    """PRD §7.4 FR-PRO-01: dispatch reader by extension."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix == ".docx":
        return _read_docx(path)
    if suffix in {".md", ".txt"}:
        return _read_text(path)
    raise CorpusError(f"Unsupported corpus file type: {path}")


def _load_docs(root: Path) -> list[CorpusDoc]:
    """PRD §7.4 FR-PRO-01: load and filter short corpus docs."""
    docs: list[CorpusDoc] = []
    for path in _iter_docs(root):
        text = _read_doc(path)
        if len(text) < MIN_DOC_CHARS:
            warnings.warn(f"Ignoring short corpus file (<{MIN_DOC_CHARS} chars): {path}")
            continue
        docs.append(CorpusDoc(path=path, text=text))
    return docs


def load_corpus(root: Path) -> CorpusBundle:
    """Walk `root/cvs`, `root/cover_letters`, `root/website`, return a bundle.

    Raises CorpusError if PRIMARY_ marker is missing or duplicated.
    """
    cvs_dir = root / "cvs"
    cls_dir = root / "cover_letters"
    website_dir = root / "website"

    cv_docs = _load_docs(cvs_dir)
    primary_docs = [
        d for d in cv_docs
        if d.path.name.startswith("PRIMARY_")
    ]
    if not primary_docs:
        raise CorpusError(
            f"Missing PRIMARY_ CV in {cvs_dir}. Add exactly one PRIMARY_* file."
        )
    if len(primary_docs) > 1:
        names = ", ".join(sorted(d.path.name for d in primary_docs))
        raise CorpusError(
            f"Found multiple PRIMARY_ CV files in {cvs_dir}: {names}. Keep exactly one."
        )

    primary_path = primary_docs[0].path
    other_cvs = [d for d in cv_docs if d.path != primary_path]

    return CorpusBundle(
        primary_cv=primary_docs[0].text,
        other_cvs=other_cvs,
        cover_letters=_load_docs(cls_dir),
        website_pages=_load_docs(website_dir),
    )
