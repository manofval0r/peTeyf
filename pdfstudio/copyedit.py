"""Human-copy quality gate.

The generator does not pretend a regex can humanise prose.  It can, however,
stop the most obvious failure modes before they enter a finished PDF.  The
skill workflow uses the humanizer skill first; this module is the mechanical
last line of defence.

Checks
------
* em dashes, emoji, replacement characters
* stock AI phrases and over-long headings
* mixed UK/US spelling inside one document
* mixed measurement systems and currencies
* ambiguous numeric dates
* placeholder or "illustrative" data presented as fact
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import re
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class CopyIssue:
    severity: str
    code: str
    message: str
    line: int
    preview: str


EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "]",
    flags=re.UNICODE,
)

AI_PHRASES = (
    "delve into", "ever-evolving landscape", "unlock the power", "game-changer",
    "seamlessly", "leverage synergies", "in today's fast-paced world",
    "it is important to note", "a testament to", "robust solution",
    "transformative journey", "revolutionize the way", "at the forefront of",
)

# Spelling pairs that read as one voice if used consistently.  Mixing them
# inside one document is the tell that two writers (or two prompts) met.
SPELLING_PAIRS: Tuple[Tuple[str, str], ...] = (
    ("organize", "organise"),
    ("organization", "organisation"),
    ("recognize", "recognise"),
    ("prioritize", "prioritise"),
    ("optimize", "optimise"),
    ("analyze", "analyse"),
    ("color", "colour"),
    ("behavior", "behaviour"),
    ("favor", "favour"),
    ("center", "centre"),
    ("meter", "metre"),
    ("liter", "litre"),
    ("program", "programme"),
    ("catalog", "catalogue"),
    ("license", "licence"),
    ("defense", "defence"),
    ("traveled", "travelled"),
    ("modeling", "modelling"),
    ("fulfill", "fulfil"),
    ("judgment", "judgement"),
)

METRIC_UNITS = ("mm", "cm", "m", "km", "g", "kg", "ml", "l", "°c", "celsius")
IMPERIAL_UNITS = ("in", "ft", "yd", "mi", "oz", "lb", "lbs", "fl oz", "°f", "fahrenheit")

PLACEHOLDER_PHRASES = (
    "lorem ipsum", "[insert", "[placeholder", "tbd", "to be decided",
    "xxx", "placeholder text", "dummy data", "sample data", "dummy copy",
)

ILLUSTRATIVE_PHRASES = (
    "illustrative", "for illustration", "for illustrative purposes",
    "indicative only", "hypothetical", "assumed figures", "not actual",
)


def _find_terms(lower: str, terms: Iterable[str]) -> List[str]:
    found = []
    for term in terms:
        pattern = r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])"
        if re.search(pattern, lower):
            found.append(term)
    return found


def _spelling_audit(text: str) -> List[CopyIssue]:
    """Warn when a document mixes US and UK spelling of the same word."""
    lower_whole = text.casefold()
    mixed: List[str] = []
    for us, uk in SPELLING_PAIRS:
        forms = {
            form for form in (us, uk)
            if re.search(
                r"(?<![a-z0-9])" + re.escape(form) + r"(?:s|ed|ing|er|ers|ation)?(?![a-z0-9])",
                lower_whole,
            )
        }
        if len(forms) > 1:
            mixed.append(f"{us}/{uk}")
    if not mixed:
        return []
    return [CopyIssue(
        "warning", "mixed-spelling",
        "Mixed US/UK spelling: " + ", ".join(mixed[:6]) + ". Pick one locale.",
        0, ", ".join(mixed[:6]),
    )]


def _unit_audit(text: str) -> List[CopyIssue]:
    lower = text.casefold()
    issues: List[CopyIssue] = []
    metric = _find_terms(lower, METRIC_UNITS)
    imperial = _find_terms(lower, IMPERIAL_UNITS)
    # "in" is too common in prose to prove an imperial measurement.
    imperial = [unit for unit in imperial if unit != "in"]
    if metric and imperial:
        issues.append(CopyIssue(
            "warning", "mixed-units",
            f"Metric ({', '.join(metric[:4])}) and imperial "
            f"({', '.join(imperial[:4])}) units are both used.",
            0, f"{', '.join(metric[:4])} + {', '.join(imperial[:4])}",
        ))
    symbols = [symbol for symbol in ("$", "£", "€", "¥") if symbol in text]
    if len(symbols) > 1:
        issues.append(CopyIssue(
            "warning", "mixed-currency",
            f"More than one currency symbol appears ({', '.join(symbols)}); "
            "state the reporting currency once.",
            0, ", ".join(symbols),
        ))
    return issues


def _date_audit(text: str) -> List[CopyIssue]:
    """Flag ambiguous all-numeric dates (02/11/2026) and mixed date styles."""
    numeric = re.findall(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b", text)
    written = re.findall(
        r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{4}\b",
        text, re.I,
    )
    if numeric and written:
        return [CopyIssue(
            "warning", "mixed-date-style",
            "Both numeric and written dates are used; pick one style.",
            0, f"{numeric[0]} / {written[0]}",
        )]
    if numeric:
        return [CopyIssue(
            "warning", "ambiguous-date",
            f"All-numeric date '{numeric[0]}' is ambiguous across locales; "
            "write the month.",
            0, numeric[0],
        )]
    return []


def _data_audit(text: str) -> List[CopyIssue]:
    lower = text.casefold()
    issues: List[CopyIssue] = []
    placeholders = [p for p in PLACEHOLDER_PHRASES if p in lower]
    if placeholders:
        issues.append(CopyIssue(
            "error", "placeholder",
            "Placeholder copy is still present: " +
            ", ".join(f"'{p}'" for p in placeholders[:4]) + ".",
            0, placeholders[0],
        ))
    illustrative = [p for p in ILLUSTRATIVE_PHRASES if p in lower]
    if illustrative:
        issues.append(CopyIssue(
            "warning", "illustrative-data",
            "Illustrative data is presented without one clear planning "
            "assumption note. Add the note once, then remove 'illustrative' "
            "from chart titles.",
            0, illustrative[0],
        ))
    return issues


def audit_copy(text: str, locale: Optional[str] = None) -> List[CopyIssue]:
    issues: List[CopyIssue] = []
    for line_no, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if "—" in line:
            issues.append(CopyIssue(
                "error", "em-dash", "Em dashes are not allowed; rewrite the sentence.",
                line_no, stripped[:120],
            ))
        if EMOJI_RE.search(line):
            issues.append(CopyIssue(
                "error", "emoji", "Emoji are not allowed in document copy.",
                line_no, stripped[:120],
            ))
        if "\ufffd" in line:
            issues.append(CopyIssue(
                "error", "replacement-char", "Invalid replacement character found.",
                line_no, stripped[:120],
            ))
        lower = line.casefold()
        for phrase in AI_PHRASES:
            if phrase in lower:
                issues.append(CopyIssue(
                    "warning", "ai-phrase", f"Stock AI phrase: '{phrase}'.",
                    line_no, stripped[:120],
                ))
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            if len(heading) > 68:
                issues.append(CopyIssue(
                    "warning", "long-heading",
                    "Heading is too long for a confident print hierarchy.",
                    line_no, heading[:120],
                ))

    # Document-level checks: run once, on the whole text.
    issues.extend(_spelling_audit(text))
    issues.extend(_unit_audit(text))
    issues.extend(_date_audit(text))
    issues.extend(_data_audit(text))

    if locale:
        wanted = locale.casefold()
        if wanted in ("en-gb", "uk", "gb"):
            wrong = _find_terms(text.casefold(), [us for us, _uk in SPELLING_PAIRS])
            if wrong:
                issues.append(CopyIssue(
                    "warning", "locale-spelling",
                    f"Document is en-GB but uses US forms: {', '.join(wrong[:6])}.",
                    0, ", ".join(wrong[:6]),
                ))
        elif wanted in ("en-us", "us", "usa"):
            wrong = _find_terms(text.casefold(), [uk for _us, uk in SPELLING_PAIRS])
            if wrong:
                issues.append(CopyIssue(
                    "warning", "locale-spelling",
                    f"Document is en-US but uses UK forms: {', '.join(wrong[:6])}.",
                    0, ", ".join(wrong[:6]),
                ))
    return issues


def errors(issues: Iterable[CopyIssue]) -> List[CopyIssue]:
    return [issue for issue in issues if issue.severity == "error"]


def format_issues(issues: Iterable[CopyIssue]) -> str:
    rows = []
    for issue in issues:
        location = f"L{issue.line}" if issue.line else "doc"
        rows.append(
            f"{issue.severity.upper():7} {location:<5} {issue.code:<18} "
            f"{issue.message}  [{issue.preview}]"
        )
    return "\n".join(rows)
