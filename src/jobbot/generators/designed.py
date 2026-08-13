"""Designed CV rendering: the same Markdown source, typeset for a human reader.

`ats.py` renders for machines and is deliberately plain: Arial, one column,
no rules, no colour, nothing that can shatter a text layer. That document is
correct and it is also charmless, which matters, because a CV gets read twice.
A parser reads it on upload, and then a person reads it in a meeting.

So this module is the second render of the *same* `cv_general_ats.md`. Not a
second source: every fact, every date and every claim comes through
`parse_cv_markdown`, so the two documents cannot drift apart. What differs is
only the typesetting.

    jobbot cv-ats      -> output/ats/*.docx, *.pdf     for portals and parsers
    jobbot cv-design   -> output/designed/*.pdf        for humans and email

Design decisions worth stating, since they are the reason this file exists:

* **Charter for text.** Matthew Carter drew it for low-resolution output, so
  it holds together at 8.4pt where a Didone or a modern grotesque would not.
  It has warmth without being decorative, which suits a document arguing that
  its author is senior and unexcitable.
* **Avenir Next for structure.** Dates, section headings and skill labels are
  navigation, not prose. A geometric sans separates them from the text at a
  glance, so the eye can skip.
* **Smaller type, more air.** 8.4pt on 1.44 leading, against 9.5pt solid on
  the plain render. Shrinking the type is what buys the whitespace: the same
  words fit in two pages with room between the stations instead of a wall.
* **One accent, structural only.** A deep petrol carries the name, the
  section rules and nothing else. Colour that lands on content reads as
  decoration; colour that lands on structure reads as design.
* **No letter-spacing at all.** Not "a little": none. Tracking is what
  destroys an extracted text layer, and the damage starts far below the value
  that looks tasteful on screen. An early version of this file set 0.13em on
  the section headings, which reads beautifully and copy-pastes as
  `WO R K E X P E R I E N C E`. Headings earn their separation from
  uppercase, weight, colour and a rule instead. Anything that reintroduces
  tracking here must be checked with pdfminer, never pypdf: pypdf silently
  repairs the defect, so it will tell you the document is fine when it is
  not.
"""
from __future__ import annotations

from pathlib import Path

from .ats import CVDoc, _inline_html, parse_cv_markdown

# Families verified present on the target machine; each falls back to a
# widely available cousin so the render never silently drops to a default.
_TEXT = '"Charter", "Bitstream Charter", Georgia, "Times New Roman", serif'
_STRUCT = '"Avenir Next", "Avenir", "Segoe UI", "Helvetica Neue", sans-serif'

DESIGN_CSS = f"""
@page {{
  size: A4;
  margin: 14mm 15mm 12mm 15mm;
}}

html {{ font-size: 8.4pt; }}

body {{
  font-family: {_TEXT};
  font-size: 8.4pt;
  line-height: 1.44;
  color: #1b1f1e;
  margin: 0;
}}

/* ---- header ---------------------------------------------------------- */

h1 {{
  font-family: {_TEXT};
  font-size: 21pt;
  font-weight: 700;
  color: #10484a;
  margin: 0;
  line-height: 1.05;
}}

p.target-title {{
  font-family: {_STRUCT};
  font-size: 8.8pt;
  font-weight: 600;
  text-transform: uppercase;
  color: #4d5654;
  margin: 3.5pt 0 0 0;
}}

p.contact {{
  font-family: {_STRUCT};
  font-size: 7.4pt;
  color: #5b6462;
  margin: 1.6pt 0 0 0;
  line-height: 1.45;
}}

p.contact:first-of-type {{ margin-top: 6pt; }}

.rule {{
  border-bottom: 0.8pt solid #10484a;
  margin: 9pt 0 0 0;
}}

/* ---- sections -------------------------------------------------------- */

h2 {{
  font-family: {_STRUCT};
  font-size: 7.8pt;
  font-weight: 600;
  text-transform: uppercase;
  color: #10484a;
  margin: 0;
  padding-bottom: 2.2pt;
  border-bottom: 0.4pt solid #cfd8d5;
  break-after: avoid;
}}

/* The gap before a section lives on the section, never on the heading: an
   h2 is its section's first child, so a margin-top there is what a
   first-child reset silently eats. */
section {{ margin-top: 10pt; }}
section:first-of-type {{ margin-top: 7pt; }}

p {{ margin: 4pt 0 0 0; }}

p.para {{ margin-top: 5pt; }}

/* The line under a role says industry and product type. It is orientation,
   not argument, so it sits back from the bullets that follow it. */
p.role + p.para {{
  font-style: italic;
  font-size: 8.1pt;
  color: #55605d;
  margin-top: 1.5pt;
  break-after: avoid;
}}

/* ---- stations -------------------------------------------------------- */

p.role {{
  font-family: {_TEXT};
  font-size: 9.1pt;
  font-weight: 700;
  color: #14201e;
  margin: 6pt 0 0 0;
  break-after: avoid;
}}

p.role .dates {{
  font-family: {_STRUCT};
  font-size: 7.8pt;
  font-weight: 500;
  font-feature-settings: "tnum";
  color: #5b6462;
}}

p.role .sep {{ color: #b7c2bf; padding: 0 3pt; }}

p.note {{
  font-family: {_TEXT};
  font-style: italic;
  font-size: 8.1pt;
  color: #55605d;
  margin: 1.5pt 0 0 0;
  break-after: avoid;
}}

/* ---- bullets --------------------------------------------------------- */

ul {{ margin: 3.5pt 0 0 0; padding: 0; list-style: none; }}

li {{
  position: relative;
  padding-left: 9pt;
  margin: 2.4pt 0 0 0;
  break-inside: avoid;
}}

li::before {{
  content: "";
  position: absolute;
  left: 0;
  top: 4.6pt;
  width: 2.6pt;
  height: 2.6pt;
  background: #10484a;
  border-radius: 50%;
}}

li b, p b {{ font-weight: 700; color: #14201e; }}

/* Skills labels are navigation, so they take the structural face. */
section.skills li b {{
  font-family: {_STRUCT};
  font-size: 8.1pt;
  font-weight: 600;
}}

section.skills li {{ margin-top: 3pt; }}

a {{ color: inherit; text-decoration: none; }}
"""


def _role_html(text: str) -> str:
    """Split a role line into its title and its trailing date range.

    The Markdown writes one bold line, `Role, Company, Location, 07/2024 -
    05/2025`. On the plain render that is fine as a single run. Here the dates
    want the structural face and a lighter colour, so they are separated on
    the last comma that is followed by something date-shaped.
    """
    head, sep, tail = text.rpartition(",")
    tail = tail.strip()
    looks_like_dates = sep and any(ch.isdigit() for ch in tail) or tail.endswith("Present")
    if not looks_like_dates:
        return _inline_html(text)
    return (
        f"{_inline_html(head.strip())}"
        f'<span class="sep">|</span>'
        f'<span class="dates">{_inline_html(tail)}</span>'
    )


def render_designed_html(doc: CVDoc) -> str:
    out: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{_inline_html(doc.name)}</title>",
        f"<style>{DESIGN_CSS}</style></head><body>",
        f"<h1>{_inline_html(doc.name)}</h1>",
    ]
    if doc.title:
        out.append(f"<p class='target-title'>{_inline_html(doc.title)}</p>")
    for line in doc.contact:
        out.append(f"<p class='contact'>{_inline_html(line)}</p>")
    out.append("<div class='rule'></div>")

    for section in doc.sections:
        css_class = "skills" if "skill" in section.heading.lower() else "block"
        out.append(f"<section class='{css_class}'>")
        out.append(f"<h2>{_inline_html(section.heading)}</h2>")
        open_list = False
        for block in section.blocks:
            if block.kind == "bullet":
                if not open_list:
                    out.append("<ul>")
                    open_list = True
                out.append(f"<li>{_inline_html(block.text)}</li>")
                continue
            if open_list:
                out.append("</ul>")
                open_list = False
            if block.kind == "role":
                out.append(f"<p class='role'>{_role_html(block.text)}</p>")
            elif block.kind == "note":
                out.append(f"<p class='note'>{_inline_html(block.text)}</p>")
            else:
                out.append(f"<p class='para'>{_inline_html(block.text)}</p>")
        if open_list:
            out.append("</ul>")
        out.append("</section>")

    out.append("</body></html>")
    return "".join(out)


def render_designed_pdf(doc: CVDoc, dest: Path) -> Path:
    from weasyprint import HTML  # lazy: heavy import

    dest.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=render_designed_html(doc)).write_pdf(str(dest))
    return dest


def build_designed_cv(source: Path, out_dir: Path, stem: str | None = None) -> Path:
    """Render `source` as the human-facing PDF and return its path."""
    doc = parse_cv_markdown(Path(source).read_text(encoding="utf-8"))
    stem = stem or Path(source).stem
    return render_designed_pdf(doc, Path(out_dir) / f"{stem}.pdf")
