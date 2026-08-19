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

import base64
import mimetypes
from pathlib import Path

from .ats import ATSFormatError, CVDoc, _inline_html, parse_cv_markdown

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

/* Photo right, identity left. The photo is decoration in the strictest
   sense: it carries no text, so it cannot affect what a parser extracts. */
.masthead {{
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8mm;
}}

.masthead .who {{ flex: 1; }}

.masthead img {{
  width: 24mm;
  height: 30mm;
  object-fit: cover;
  object-position: center top;
  border-radius: 1.5pt;
  flex: none;
}}

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
   not argument, so it sits back from the bullets that follow it.

   Only when bullets DO follow. On the compressed stations that single
   paragraph is the whole entry, and muting it would grey out the content
   instead of the label. `render_designed_html` decides which is which. */
p.context {{
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


def _photo_data_uri(path: Path) -> str:
    """Inline the photo so the PDF is self-contained and leaks no local path."""
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def render_designed_html(doc: CVDoc, photo: Path | None = None) -> str:
    out: list[str] = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{_inline_html(doc.name)}</title>",
        f"<style>{DESIGN_CSS}</style></head><body>",
        "<div class='masthead'><div class='who'>",
        f"<h1>{_inline_html(doc.name)}</h1>",
    ]
    if doc.title:
        out.append(f"<p class='target-title'>{_inline_html(doc.title)}</p>")
    for line in doc.contact:
        out.append(f"<p class='contact'>{_inline_html(line)}</p>")
    out.append("</div>")
    if photo is not None:
        out.append(f"<img src='{_photo_data_uri(Path(photo))}' alt=''>")
    out.append("</div>")
    out.append("<div class='rule'></div>")

    for section in doc.sections:
        css_class = "skills" if "skill" in section.heading.lower() else "block"
        out.append(f"<section class='{css_class}'>")
        out.append(f"<h2>{_inline_html(section.heading)}</h2>")
        open_list = False
        blocks = section.blocks
        for i, block in enumerate(blocks):
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
                # A paragraph under a role is a label only when bullets carry
                # the substance after it. Where it is the entry's only line,
                # it is the substance and keeps full weight.
                follows_role = i > 0 and blocks[i - 1].kind == "role"
                bullets_follow = i + 1 < len(blocks) and blocks[i + 1].kind == "bullet"
                css = "para context" if (follows_role and bullets_follow) else "para"
                out.append(f"<p class='{css}'>{_inline_html(block.text)}</p>")
        if open_list:
            out.append("</ul>")
        out.append("</section>")

    out.append("</body></html>")
    return "".join(out)


def render_designed_pdf(doc: CVDoc, dest: Path, photo: Path | None = None) -> Path:
    from weasyprint import HTML  # lazy: heavy import

    dest.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=render_designed_html(doc, photo=photo)).write_pdf(str(dest))
    return dest


def build_designed_cv(
    source: Path, out_dir: Path, stem: str | None = None, photo: Path | None = None
) -> Path:
    """Render `source` as the human-facing PDF and return its path.

    `photo` is passed in rather than read from a fixed location on purpose.
    The repository is public, so a portrait must never live inside it, and the
    ATS render never takes one at all: images are a parsing hazard, and in the
    US and UK a photo on a CV is a screening liability rather than a nicety.
    """
    doc = parse_cv_markdown(Path(source).read_text(encoding="utf-8"))
    stem = stem or Path(source).stem
    return render_designed_pdf(doc, Path(out_dir) / f"{stem}.pdf", photo=photo)


# --------------------------------------------------------------------------
# Cover letters
#
# A letter is not a CV, so it does not go through parse_cv_markdown: it has no
# sections, no roles and no dates to typeset. It shares the typography, the
# masthead and the audit, which is the part that matters. The editorial
# renderer in pipeline.py is what the older letters in data/applications use,
# and it is the one whose text layer shatters, so new letters come through
# here instead.
# --------------------------------------------------------------------------

LETTER_CSS = DESIGN_CSS + f"""
body {{ font-size: 9.4pt; line-height: 1.58; }}
.letter p {{ margin: 7.5pt 0 0 0; }}
.letter p.subject {{
  font-family: {_STRUCT};
  font-weight: 600;
  font-size: 8.8pt;
  text-transform: uppercase;
  color: #10484a;
  margin-top: 13pt;
}}
.letter p.salutation {{ margin-top: 13pt; }}
.letter p.signoff {{ margin-top: 13pt; }}
"""


def render_letter_html(md: str, photo: Path | None = None) -> str:
    """Render a cover letter written in the letterhead shape.

        # Name. *Subtitle.*
        Contact line
        Re: subject line
        Salutation
        ...body paragraphs...
        Best regards,
        Name
    """
    lines = [ln.strip() for ln in md.splitlines() if ln.strip()]
    if not lines or not lines[0].startswith("# "):
        raise ATSFormatError("a letter must open with '# Name. *Subtitle.*'")

    head = lines[0][2:].strip()
    name, _, subtitle = head.partition(".")
    subtitle = subtitle.strip().strip("*").strip(". ")
    contact, subject, body = lines[1], "", []
    for i, ln in enumerate(lines[2:], start=2):
        if not subject and (ln.startswith("Re:") or ln.startswith("Betreff:")):
            subject = ln
            body = lines[i + 1:]
            break
    else:
        body = lines[2:]

    out = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        f"<title>{_inline_html(name)}</title>",
        f"<style>{LETTER_CSS}</style></head><body>",
        "<div class='masthead'><div class='who'>",
        f"<h1>{_inline_html(name.strip())}</h1>",
    ]
    if subtitle:
        out.append(f"<p class='target-title'>{_inline_html(subtitle)}</p>")
    out.append(f"<p class='contact'>{_inline_html(contact)}</p>")
    out.append("</div>")
    if photo is not None:
        out.append(f"<img src='{_photo_data_uri(Path(photo))}' alt=''>")
    out.append("</div><div class='rule'></div><div class='letter'>")
    if subject:
        out.append(f"<p class='subject'>{_inline_html(subject)}</p>")
    for i, para in enumerate(body):
        css = "salutation" if i == 0 else ("signoff" if para.startswith("Best regards") else "")
        out.append(f"<p class='{css}'>{_inline_html(para)}</p>")
    out.append("</div></body></html>")
    return "".join(out)


def build_letter(source: Path, out_dir: Path, stem: str | None = None,
                 photo: Path | None = None) -> Path:
    from weasyprint import HTML

    md = Path(source).read_text(encoding="utf-8")
    dest = Path(out_dir) / f"{stem or Path(source).stem}.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=render_letter_html(md, photo=photo)).write_pdf(str(dest))
    return dest
