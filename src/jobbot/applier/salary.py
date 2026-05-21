"""Apply-time salary resolution.

Two callers come through here:

  1. `parse_posting_salary(text)`, scan the job description for any
     stated salary range the EMPLOYER published. Returns a normalised
     `(low, high, currency, period)` tuple or `None` if nothing matched.

  2. `apply_salary_for(job, profile)`, the resolver the adapters call.
     Decides what number to write into the form's salary field:
       - If the posting stated a range → use the LOW END in the posting's
         own currency (so we match the field's expected unit and don't
         do a sketchy cross-currency conversion).
       - Else → fall back to the candidate's
         `profile.preferences.application_salary_eur_year` anchor
         (default 125000 EUR/year, set on 2026-05-15 after a 6666 EUR
         undershoot at GTO Wizard).
     Returns a `ApplySalary` dataclass that adapters can format for
     either a yearly field (`{amount}` + `{currency}/year`) or a
     monthly field (amount / 12 + `{currency}/month`).

User feedback on 2026-05-15:
  *"we need a script to customize salary expectations: if they provide
   one themselves, use the lower end. if they don't provide apply with
   125k."*
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ParsedSalary:
    low: int           # smaller integer in the matched currency, per period
    high: int          # larger integer, same currency/period
    currency: str      # "USD" | "EUR" | "GBP" | "CHF"
    period: str        # "year" | "month"


@dataclass
class ApplySalary:
    """The single number the adapter writes (in the posting's currency
    when known, EUR otherwise). Provides convenient helpers for the two
    field shapes we encounter on real ATSes."""
    amount_per_year: int
    currency: str          # "USD" | "EUR" | "GBP" | "CHF"
    sourced_from: str      # "posting" | "profile_anchor"

    @property
    def amount_per_month(self) -> int:
        return round(self.amount_per_year / 12)

    def for_yearly_field(self) -> str:
        """e.g. '166000 USD/year', for free-text salary fields."""
        return f"{self.amount_per_year} {self.currency}/year"

    def for_monthly_field(self) -> int:
        """For numeric-only monthly inputs (Recruitee's pattern)."""
        return self.amount_per_month


# Currency symbol → ISO code. Used to normalise '$', '€', '£', 'CHF', '₣'.
_CURRENCY_SYMBOL = {
    "$": "USD", "USD": "USD", "US$": "USD",
    "€": "EUR", "EUR": "EUR",
    "£": "GBP", "GBP": "GBP",
    "CHF": "CHF", "₣": "CHF",
}

# Match a money number, optionally suffixed with K/M (thousands/millions).
# Captures the numeric value and the optional suffix.
_MONEY = r"(\d{1,3}(?:[,.\s]\d{3})*(?:\.\d+)?)\s*([kKmM]?)"

# Currency anchor in front (e.g. "$166K") OR behind (e.g. "166,000 EUR").
_CUR_BEFORE = r"(?:US\$|CHF|EUR|GBP|USD|[\$€£])"
_CUR_AFTER  = r"(?:USD|EUR|GBP|CHF|EURO|EUROS?)"


def _normalise_amount(num_text: str, suffix: str) -> int:
    """'166K' → 166000; '120.000' → 120000; '85,000' → 85000; '1.5M' → 1500000."""
    s = num_text.replace(",", "").replace(" ", "")
    if s.count(".") == 1 and len(s.rsplit(".", 1)[1]) == 3:
        # European thousand-separator style: '120.000' → 120000
        s = s.replace(".", "")
    val = float(s)
    if suffix.lower() == "k":
        val *= 1_000
    elif suffix.lower() == "m":
        val *= 1_000_000
    return int(round(val))


def parse_posting_salary(text: str) -> ParsedSalary | None:
    """Scan a job description for an employer-stated salary range.

    Returns `ParsedSalary(low, high, currency, period)` on a confident
    match. Returns `None` when the text contains no salary signal we
    recognise.

    Match priority:
      1. Currency-prefixed range:    $166K - $208K
      2. Currency-suffixed range:    80,000 - 100,000 EUR / year
      3. Currency-prefixed single:   €120,000 per year   (low==high)
      4. Plain "salary: X" with currency in scope
    """
    if not text:
        return None
    t = text

    # 1) "$166K - $208K" / "€80K – €100K" / "$166K — $208K" / "USD 100,000 - 150,000"
    # The character class includes hyphen-minus, en-dash, em-dash, "to".
    # These are RECOGNISERS of separator characters in posting text — the
    # em-dash here is read, not written, so the "never generate em-dashes"
    # rule doesn't apply. The previous em-dash sweep stripped this and
    # broke single-amount parsing because the comma got mis-treated as a
    # range separator inside "150,000".
    _SEP = "[-–—]|\\sto\\s"
    for pat in (
        re.compile(rf"({_CUR_BEFORE})\s*{_MONEY}\s*(?:{_SEP})\s*(?:{_CUR_BEFORE})?\s*{_MONEY}", re.IGNORECASE),
    ):
        m = pat.search(t)
        if m:
            cur = _CURRENCY_SYMBOL.get(m.group(1).upper(), m.group(1).upper())
            low = _normalise_amount(m.group(2), m.group(3))
            high = _normalise_amount(m.group(4), m.group(5))
            if low > high:
                low, high = high, low
            return ParsedSalary(low, high, cur, _detect_period(t, m.start(), m.end()))

    # 2) "80,000 - 100,000 EUR / year"
    pat = re.compile(rf"{_MONEY}\s*(?:{_SEP})\s*{_MONEY}\s+({_CUR_AFTER})", re.IGNORECASE)
    m = pat.search(t)
    if m:
        cur = _CURRENCY_SYMBOL.get(m.group(5).upper(), m.group(5).upper())
        low = _normalise_amount(m.group(1), m.group(2))
        high = _normalise_amount(m.group(3), m.group(4))
        if low > high:
            low, high = high, low
        return ParsedSalary(low, high, cur, _detect_period(t, m.start(), m.end()))

    # 3) Single currency-prefixed amount (fall-back: low == high)
    pat = re.compile(rf"({_CUR_BEFORE})\s*{_MONEY}\s*(?:per\s+year|/year|/yr|annually|p\.?a\.?)", re.IGNORECASE)
    m = pat.search(t)
    if m:
        cur = _CURRENCY_SYMBOL.get(m.group(1).upper(), m.group(1).upper())
        amt = _normalise_amount(m.group(2), m.group(3))
        return ParsedSalary(amt, amt, cur, "year")

    return None


# Rough FX conversion to EUR for the salary-floor comparison. These are
# deliberately approximate, the floor filter only needs to decide whether
# the TOP of a stated range is clearly below the candidate's floor, not to
# do precise currency math. Update if rates drift materially.
_FX_TO_EUR = {
    "EUR": 1.0,
    "USD": 0.92,
    "GBP": 1.17,
    "CHF": 1.05,
}


def annualised_top_eur(parsed: ParsedSalary) -> int:
    """Top of the stated range, normalised to EUR per year.

    Uses the HIGH end so we only ever flag a posting when even its best
    case is below floor; a range like EUR 80k to 100k (top above floor)
    stays in play because it is negotiable into acceptable territory.
    """
    top = parsed.high
    if parsed.period == "month":
        top *= 12
    return int(round(top * _FX_TO_EUR.get(parsed.currency, 1.0)))


def posting_below_salary_floor(
    description: str, floor_eur_year: int,
) -> tuple[bool, str]:
    """Return (is_below, reason) for a posting whose STATED salary tops out
    below `floor_eur_year`.

    Rules:
      - floor <= 0 disables the check (returns False).
      - A posting with no parseable salary returns False, we never filter
        on unknown comp, only on a stated range that is clearly too low.
      - Otherwise compare the annualised EUR top of the range to the floor.
    """
    if floor_eur_year <= 0:
        return False, ""
    parsed = parse_posting_salary(description or "")
    if parsed is None:
        return False, ""
    top_eur = annualised_top_eur(parsed)
    if top_eur < floor_eur_year:
        return True, (
            f"salary_below_floor: stated top {top_eur} EUR/year "
            f"({parsed.high} {parsed.currency}/{parsed.period}) "
            f"< floor {floor_eur_year} EUR/year"
        )
    return False, ""


# Freelance hourly/daily rate, e.g. "80 €/Std", "80 EUR/h", "800 €/Tag",
# "90/hour", "700 EUR / day". Captures the number and the unit so we can
# normalise day-rates to an hourly figure.
_RATE_RE = re.compile(
    r"(\d{1,4}(?:[.,]\d{1,2})?)\s*"
    r"(?:€|eur|euro)?\s*(?:/|pro|per|p\.?)?\s*"
    r"(std|stunde|stunden|hour|hours|hr|h|tag|tage|day|days|d)\b",
    re.IGNORECASE,
)
# Hours per freelance day, used to convert a day-rate to an hourly rate.
_HOURS_PER_DAY = 8


def parse_hourly_rate_eur(text: str) -> float | None:
    """Best-effort hourly rate in EUR from a freelance project body.

    Handles hourly (€/Std, /h, /hour) and daily (€/Tag, /day) rates;
    day rates are divided by an 8h day. Returns None when no rate is
    stated (freelancermap often shows "auf Anfrage"), in which case the
    caller does not filter, same convention as the annual floor.
    """
    if not text:
        return None
    best: float | None = None
    for m in _RATE_RE.finditer(text):
        num = float(m.group(1).replace(",", "."))
        unit = m.group(2).lower()
        if unit.startswith(("tag", "day", "d")):
            num = num / _HOURS_PER_DAY
        # Ignore implausible matches (e.g. "8 h" experience years); a real
        # freelance rate is at least 20 EUR/h.
        if num < 20:
            continue
        if best is None or num > best:
            best = num
    return best


def posting_below_hourly_floor(
    description: str, floor_eur_hour: float,
) -> tuple[bool, str]:
    """Return (is_below, reason) for a freelance posting whose stated rate
    is below `floor_eur_hour`. No stated rate -> not filtered (same as the
    annual floor's unknown-comp rule)."""
    if floor_eur_hour <= 0:
        return False, ""
    rate = parse_hourly_rate_eur(description or "")
    if rate is None:
        return False, ""
    if rate < floor_eur_hour:
        return True, (
            f"rate_below_floor: stated ~{rate:.0f} EUR/h "
            f"< floor {floor_eur_hour:.0f} EUR/h"
        )
    return False, ""


def _detect_period(text: str, span_start: int, span_end: int) -> str:
    """Look at the words around the salary span to classify year vs month.

    Default to 'year', the dominant convention in job postings. Only
    flip to 'month' when explicit ('per month', '/mo', etc.) within ~50
    chars of the matched figure.
    """
    window = text[max(0, span_start - 50): span_end + 50].lower()
    if re.search(r"per\s+month|/\s*month|/\s*mo\b|monthly|monatlich|pro monat", window):
        return "month"
    return "year"


def apply_salary_for(
    description: str,
    profile_application_anchor_eur_year: int = 125_000,
) -> ApplySalary:
    """The number the adapter writes. See module docstring.

    `description` is the job-posting body (we look in there for an
    employer-stated range). `profile_application_anchor_eur_year` is
    the user's fallback (default 125_000 EUR/year, configurable via
    `profile.preferences.application_salary_eur_year`).
    """
    parsed = parse_posting_salary(description or "")
    if parsed is not None:
        # Use the employer's LOW END in the employer's own currency.
        # If they quoted monthly, annualise so the ApplySalary contract
        # always carries a yearly number, adapters that want monthly
        # call `.for_monthly_field()`.
        amount_year = parsed.low * 12 if parsed.period == "month" else parsed.low
        return ApplySalary(
            amount_per_year=amount_year,
            currency=parsed.currency,
            sourced_from="posting",
        )
    return ApplySalary(
        amount_per_year=int(profile_application_anchor_eur_year),
        currency="EUR",
        sourced_from="profile_anchor",
    )
