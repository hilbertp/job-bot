"""Post-generation QA gate for application packages.

Runs after every generation and writes `qa_report.json` next to the
artefacts. Checks encode the failure modes that actually kill
applications (research dossier, 2026-08):

- text layer: a CV PDF whose text cannot be extracted is invisible in
  recruiter search forever ("soft invisibility"). The select-and-copy
  test is the standard diagnostic; here it is automated with pypdf.
- page budget: the CV is a two-page document by design; page three is
  where recruiter attention goes to die.
- mirror coverage: terms present in both the posting and the base CV
  must survive into the tailored CV, they are what recruiter search
  and ranking layers match on.
- directive compliance: embedded posting instructions (trap words,
  reference codes) that go unanswered self-identify the application
  as machine-generated.
- banned content: "lovable" links (house rule: the canonical site is
  www.true-north.berlin), em/en dashes (AI tell, must be scrubbed
  upstream), and stock filler phrases that read as generic AI output.

`run_qa` never raises: a QA crash must not cost an otherwise sendable
package. Individual check errors degrade to `warn` with the exception
in the detail.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..profile import Profile
from .jd_signals import JdSignals, _term_pattern

QA_REPORT_FILENAME = "qa_report.json"


@dataclass
class QACheck:
    name: str
    status: str  # "pass" | "warn" | "fail"
    detail: str = ""


@dataclass
class QAReport:
    checks: list[QACheck] = field(default_factory=list)

    @property
    def worst(self) -> str:
        order = {"pass": 0, "warn": 1, "fail": 2}
        return max((c.status for c in self.checks),
                   key=lambda s: order.get(s, 1), default="pass")

    def to_dict(self) -> dict:
        return {"worst": self.worst, "checks": [asdict(c) for c in self.checks]}


# --- individual checks ---------------------------------------------------


def _pdf_text(pdf_path: str | Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


def _pdf_page_count(pdf_path: str | Path) -> int:
    from pypdf import PdfReader

    return len(PdfReader(str(pdf_path)).pages)


def check_pdf_text_layer(pdf_path: str, full_name: str, email: str) -> QACheck:
    """The automated select-and-copy test on the ATS-facing cv.pdf."""
    text = " ".join(_pdf_text(pdf_path).split()).lower()
    missing = []
    if full_name and full_name.lower() not in text:
        missing.append(f"name ({full_name})")
    if email and email.lower() not in text:
        missing.append(f"email ({email})")
    if not text.strip():
        return QACheck("pdf_text_layer", "fail",
                       "no extractable text at all; parsers will see a blank page")
    if missing:
        return QACheck("pdf_text_layer", "fail",
                       "not extractable from cv.pdf: " + ", ".join(missing))
    return QACheck("pdf_text_layer", "pass")


def check_page_budget(pdf_path: str) -> QACheck:
    pages = _pdf_page_count(pdf_path)
    if pages > 2:
        return QACheck("cv_page_budget", "fail",
                       f"cv.pdf is {pages} pages; the budget is 2")
    return QACheck("cv_page_budget", "pass", f"{pages} page(s)")


def check_mirror_coverage(cv_md: str, mirror_terms: list[str]) -> QACheck:
    """Every mirror term is claimable AND in the posting, so absence from the
    tailored CV is a tailoring defect, not a truthfulness question."""
    if not mirror_terms:
        return QACheck("mirror_coverage", "pass", "no mirror terms extracted")
    missing = [t for t in mirror_terms if not _term_pattern(t).search(cv_md)]
    if missing:
        return QACheck("mirror_coverage", "warn",
                       "missing from tailored CV: " + ", ".join(missing))
    return QACheck("mirror_coverage", "pass",
                   f"all {len(mirror_terms)} terms present")


def check_directive_compliance(cover_letter_md: str,
                               signals: JdSignals) -> QACheck:
    checkable = [d for d in signals.directives if d.must_contain]
    if not checkable:
        return QACheck("directive_compliance", "pass", "no verifiable directives")
    missing = [d.must_contain for d in checkable
               if d.must_contain.lower() not in cover_letter_md.lower()]
    if missing:
        return QACheck(
            "directive_compliance", "fail",
            "posting directives not satisfied in the cover letter: "
            + ", ".join(f'"{t}"' for t in missing),
        )
    return QACheck("directive_compliance", "pass",
                   f"all {len(checkable)} verifiable directives satisfied")


_DASH_RE = re.compile(r"[—–]")
_STOCK_PHRASES = (
    "i am passionate",
    "i am writing to apply",
    "i believe i would be a great",
    "great asset",
    "synergy",
    "rockstar",
    "ninja",
    "please find attached",
    "dear sir or madam",
)


def check_banned_content(*documents: str) -> QACheck:
    """Hard bans (lovable links, em/en dashes) fail; filler phrases warn."""
    text = "\n".join(d for d in documents if d)
    lowered = text.lower()
    problems: list[str] = []
    if "lovable" in lowered:
        problems.append('contains "lovable" (banned; canonical site is '
                        "www.true-north.berlin)")
    # Fenced code is exempt upstream in the scrubber; anything left is prose.
    prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    if _DASH_RE.search(prose):
        problems.append("em/en dash survived the scrub")
    if problems:
        return QACheck("banned_content", "fail", "; ".join(problems))
    fillers = [p for p in _STOCK_PHRASES if p in lowered]
    if fillers:
        return QACheck("banned_content", "warn",
                       "stock filler phrases: " + ", ".join(fillers))
    return QACheck("banned_content", "pass")


# --- orchestration -------------------------------------------------------


def _safe(check_fn, *args) -> QACheck:
    try:
        return check_fn(*args)
    except Exception as e:  # a QA crash must not cost a sendable package
        return QACheck(getattr(check_fn, "__name__", "check"), "warn",
                       f"check errored: {type(e).__name__}: {e}")


def run_qa(
    *,
    job_dir: Path,
    profile: Profile,
    signals: JdSignals | None,
    cv_md: str,
    cover_letter_md: str,
    package_md: str | None = None,
    cv_pdf_path: str | None = None,
) -> QAReport:
    report = QAReport()
    personal = profile.personal or {}
    full_name = str(personal.get("full_name", "") or "")
    email = str(personal.get("email", "") or "")

    if cv_pdf_path and Path(cv_pdf_path).is_file():
        report.checks.append(_safe(check_pdf_text_layer, cv_pdf_path,
                                   full_name, email))
        report.checks.append(_safe(check_page_budget, cv_pdf_path))
    else:
        report.checks.append(QACheck("pdf_text_layer", "warn",
                                     "cv.pdf missing; nothing to verify"))

    if signals is not None:
        report.checks.append(_safe(check_mirror_coverage, cv_md,
                                   signals.mirror_terms))
        report.checks.append(_safe(check_directive_compliance,
                                   cover_letter_md, signals))
    report.checks.append(_safe(check_banned_content, cv_md, cover_letter_md,
                               package_md or ""))

    try:
        (job_dir / QA_REPORT_FILENAME).write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
        )
    except Exception:
        pass  # the report is advisory; never block generation on it
    return report
