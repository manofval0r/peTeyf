"""Content loading and normalisation.

Accepts Markdown, JSON, or HTML and produces a single `Document` with:

* parsed frontmatter / metadata
* rendered HTML body
* a table-of-contents model (heading, id, level)
* deferred slots for images, charts, and metric blocks
* callout and figure styling

Special Markdown directives
---------------------------
Metric block::

    ```metrics
    CAC | $42 | -18%
    LTV | $310 | +12%
    ```

Chart block::

    ```chart bar
    Q1 | 12 | 18
    Q2 | 20 | 26
    ```

Image search (resolved later)::

    ![African retail market](search:african retail market)

Image file::

    ![Team photo](img:assets/team.jpg)

Callouts::

    > [!NOTE] Why this matters
    > Body text...

"""

from __future__ import annotations

import html as html_lib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:  # PyYAML is optional; a small parser is used otherwise.
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

try:
    import markdown as md_lib  # type: ignore
except Exception:  # pragma: no cover
    md_lib = None


SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = text.strip().lower()
    text = SLUG_RE.sub("-", text).strip("-")
    return text or "section"


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------

def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if value in ("null", "None", "~"):
        return None
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    if re.fullmatch(r"-?\d+", value):
        try:
            return int(value)
        except ValueError:
            pass
    if re.fullmatch(r"-?\d+\.\d+", value):
        try:
            return float(value)
        except ValueError:
            pass
    return value


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _mini_yaml(text: str) -> Dict[str, Any]:
    """A deliberately small frontmatter parser.

    Supports flat keys, one level of nesting, lists, and block scalars.
    It exists so the skill still works when PyYAML is unavailable.
    """
    data: Dict[str, Any] = {}
    lines = [l for l in text.splitlines()]
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#") or _indent(line) > 0:
            i += 1
            continue
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()

        if rest in ("|", ">"):
            block = []
            i += 1
            while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            data[key] = ("\n" if rest == "|" else " ").join(block).strip()
            continue

        if rest == "":
            nested: Dict[str, Any] = {}
            items: list = []
            j = i + 1
            while j < len(lines):
                child = lines[j]
                if not child.strip():
                    j += 1
                    continue
                if _indent(child) == 0:
                    break
                stripped = child.strip()
                if stripped.startswith("- "):
                    items.append(_parse_scalar(stripped[2:]))
                elif ":" in stripped:
                    ck, _, cv = stripped.partition(":")
                    nested[ck.strip()] = _parse_scalar(cv.strip())
                j += 1
            if items:
                data[key] = items
            elif nested:
                data[key] = nested
            else:
                data[key] = ""
            i = j
            continue

        data[key] = _parse_scalar(rest)
        i += 1
    return data


def parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() in ("---", "..."):
            end = idx
            break
    if end is None:
        return {}, text
    raw = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:])
    if yaml is not None:
        try:
            data = yaml.safe_load(raw) or {}
        except Exception as exc:
            raise ValueError(f'Invalid YAML frontmatter: {exc}') from exc
        if not isinstance(data, dict):
            raise ValueError('YAML frontmatter must be a mapping.')
        return data, body
    if any(_indent(line) >= 4 for line in raw.splitlines() if line.strip()):
        raise ValueError('Nested design frontmatter requires PyYAML; it cannot be safely flattened.')
    return _mini_yaml(raw), body


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class TocEntry:
    level: int
    text: str
    id: str


@dataclass
class ImageRequest:
    slot: str
    query: str = ""
    path: str = ""
    alt: str = ""
    caption: str = ""
    kind: str = "search"      # search | file | url
    url: str = ""


@dataclass
class ChartRequest:
    slot: str
    kind: str
    title: str = ""
    labels: List[str] = field(default_factory=list)
    series: List[List[float]] = field(default_factory=list)
    series_names: List[str] = field(default_factory=list)


@dataclass
class Document:
    meta: Dict[str, Any]
    body_html: str
    toc: List[TocEntry]
    image_requests: List[ImageRequest] = field(default_factory=list)
    chart_requests: List[ChartRequest] = field(default_factory=list)
    source_path: Optional[Path] = None
    warnings: List[str] = field(default_factory=list)
    blocks: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

def _markdown_to_html(text: str) -> str:
    if md_lib is None:
        # Minimal fallback: escape and convert headings/paragraphs.
        escaped = html_lib.escape(text)
        escaped = re.sub(r"^###### (.*)$", r"<h6>\1</h6>", escaped, flags=re.M)
        escaped = re.sub(r"^##### (.*)$", r"<h5>\1</h5>", escaped, flags=re.M)
        escaped = re.sub(r"^#### (.*)$", r"<h4>\1</h4>", escaped, flags=re.M)
        escaped = re.sub(r"^### (.*)$", r"<h3>\1</h3>", escaped, flags=re.M)
        escaped = re.sub(r"^## (.*)$", r"<h2>\1</h2>", escaped, flags=re.M)
        escaped = re.sub(r"^# (.*)$", r"<h1>\1</h1>", escaped, flags=re.M)
        return "<p>" + escaped.replace("\n\n", "</p><p>") + "</p>"
    return md_lib.markdown(
        text,
        extensions=[
            "extra",
            "tables",
            "fenced_code",
            "attr_list",
            "md_in_html",
            "sane_lists",
            "smarty",
            "toc",
        ],
        output_format="html5",
    )


# ---------------------------------------------------------------------------
# Block transforms
# ---------------------------------------------------------------------------

CALLOUT_LABELS = {
    "NOTE": ("note", "Note"),
    "TIP": ("tip", "Tip"),
    "WARNING": ("warning", "Warning"),
    "IMPORTANT": ("important", "Important"),
    "CAUTION": ("caution", "Caution"),
    "KEY": ("key", "Key takeaway"),
    "QUOTE": ("quote", "Quote"),
    "INSIGHT": ("insight", "Insight"),
    "RISK": ("risk", "Risk"),
    "ACTION": ("action", "Action"),
}


def _transform_callouts(html: str) -> str:
    def render_callout(segment: str) -> str:
        m = re.match(
            r"\s*<p>\s*\[!(NOTE|TIP|WARNING|IMPORTANT|CAUTION|KEY|QUOTE|INSIGHT|RISK|ACTION)\]\s*(.*?)</p>(.*)",
            segment,
            flags=re.S | re.I,
        )
        if not m:
            return ""
        kind = m.group(1).lower()
        title = m.group(2).strip()
        rest = m.group(3)
        cls, default_title = CALLOUT_LABELS.get(m.group(1).upper(), ("note", "Note"))
        # A lazy continuation line joins the title and body in one <p>.
        if "\n" in title:
            first, _, remainder = title.partition("\n")
            title = first.strip()
            remainder = remainder.strip()
            if remainder:
                rest = f"<p>{remainder}</p>{rest}"
        title = title or default_title
        return (
            f'<div class="callout callout--{cls}">'
            f'<div class="callout__title">{title}</div>'
            f'<div class="callout__body">{rest}</div>'
            f"</div>"
        )

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        # Two callouts separated by a blank line still arrive as one
        # blockquote.  Split on the next marker so each gets its own panel
        # instead of leaking "[!KEY]" into the previous body.
        parts = re.split(
            r"(?=<p>\s*\[!(?:NOTE|TIP|WARNING|IMPORTANT|CAUTION|KEY|QUOTE|INSIGHT|RISK|ACTION)\])",
            inner,
            flags=re.I,
        )
        if len(parts) > 1:
            rendered = [render_callout(part) for part in parts if part.strip()]
            if all(rendered):
                return "".join(rendered)
        return render_callout(inner) or match.group(0)

    # blockquotes, including nested paragraphs
    return re.sub(r"<blockquote>(.*?)</blockquote>", repl, html, flags=re.S)


def _metrics_html(lines: List[str]) -> str:
    cards = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in re.split(r"\s*\|\s*", line)]
        if len(parts) < 2:
            continue
        label = parts[0]
        value = parts[1]
        delta = parts[2] if len(parts) > 2 else ""
        cls = ""
        if delta:
            if delta.startswith("-") or delta.lower().startswith("down"):
                cls = "metric--down"
            elif delta.startswith("+") or delta.lower().startswith("up"):
                cls = "metric--up"
        cards.append(
            f'<div class="metric {cls}">'
            f'<div class="metric__value">{html_lib.escape(value)}</div>'
            f'<div class="metric__label">{html_lib.escape(label)}</div>'
            f'{f"<div class=metric__delta>{html_lib.escape(delta)}</div>" if delta else ""}'
            f"</div>"
        )
    if not cards:
        return ""
    count = min(len(cards), 6)
    return f'<div class="metrics metrics--n{count}">{"".join(cards)}</div>'


def _swot_html(raw: str) -> str:
    """Render a 2x2 SWOT matrix from `Label | item; item; item` lines."""
    order = [
        ("strengths", "s", "Strengths"),
        ("weaknesses", "w", "Weaknesses"),
        ("opportunities", "o", "Opportunities"),
        ("threats", "t", "Threats"),
    ]
    cells = []
    parsed = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        label, _, body = line.partition("|")
        items = [
            html_lib.escape(item.strip(" -•\t"))
            for item in re.split(r"[;•]|\n", body)
            if item.strip(" -•\t")
        ]
        parsed[label.strip().lower()] = items

    for key, letter, fallback in order:
        items = parsed.get(key, [])
        if not items:
            continue
        lis = "".join(f"<li>{item}</li>" for item in items)
        cells.append(
            f'<div class="swot__cell swot__cell--{letter}">'
            f'<h4 class="swot__title">{html_lib.escape(fallback)}</h4>'
            f"<ul>{lis}</ul></div>"
        )
    if not cells:
        return ""
    return f'<div class="swot">{"".join(cells)}</div>'


def _num(raw: str) -> float:
    """Parse a number from a cell, tolerating currency and thousands separators."""
    cleaned = (
        raw.strip()
        .replace(",", "")
        .replace("£", "")
        .replace("$", "")
        .replace("€", "")
        .replace("%", "")
        .replace(" ", "")
    )
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _parse_chart(kind: str, raw: str) -> ChartRequest:
    """Parse a pipe-delimited chart table.

    Shape::

        title: Optional title
        Month | Revenue | Cost      <- optional header row (names the series)
        Jan   | 12      | 8
        Feb   | 15      | 9
    """
    lines = [
        l.strip()
        for l in raw.strip().splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    title = ""
    labels: List[str] = []
    rows: List[List[float]] = []
    series_names: List[str] = []

    if lines and lines[0].lower().startswith("title:"):
        title = lines[0].split(":", 1)[1].strip()
        lines = lines[1:]

    for idx, line in enumerate(lines):
        parts = [p.strip() for p in re.split(r"\s*\|\s*", line)]
        while len(parts) > 1 and parts[-1] == "":
            parts.pop()
        if len(parts) < 2:
            continue
        numeric = [_num(p) for p in parts[1:]]
        is_header = (
            idx == 0
            and len(parts) > 2
            and all(not re.fullmatch(r"-?\d+(\.\d+)?", p) for p in parts[1:])
        )
        if is_header:
            series_names = parts[1:]
            continue
        labels.append(parts[0])
        rows.append(numeric)

    width = max((len(r) for r in rows), default=0)
    columns: List[List[float]] = []
    for c in range(width):
        columns.append([row[c] if c < len(row) else 0.0 for row in rows])
    if not series_names:
        series_names = [f"Series {i + 1}" for i in range(len(columns))]

    return ChartRequest(
        slot="",
        kind=kind,
        title=title,
        labels=labels,
        series=columns,
        series_names=series_names[: len(columns)],
    )


SPECIAL_FENCE_RE = re.compile(
    r"^[ \t]*```(metrics|swot|chart(?:[ \t]+[A-Za-z]+)?)[ \t]*\n(.*?)^[ \t]*```[ \t]*$",
    re.S | re.M,
)


def _prepare_markdown_blocks(md_text: str) -> tuple[str, Dict[str, str], List[ChartRequest]]:
    """Pull ```metrics / ```chart fences out of Markdown *before* conversion.

    Fenced-code info strings are not reliably supported by every Markdown
    extension, so special blocks are extracted first and replaced with plain
    placeholder tokens that survive conversion.
    """
    blocks: Dict[str, str] = {}
    charts: List[ChartRequest] = []
    counter = {"chart": 0}

    def repl(match: re.Match[str]) -> str:
        lang = " ".join(match.group(1).split())
        raw = match.group(2)
        if lang == "metrics":
            key = "@@METRICS_BLOCK@@"
            html_block = _metrics_html(raw.splitlines())
            blocks[key] = html_block or ""
            return f"\n\n{key}\n\n"

        if lang == "swot":
            key = "@@SWOT_BLOCK@@"
            blocks[key] = _swot_html(raw) or ""
            return f"\n\n{key}\n\n"

        bits = lang.split()
        kind = bits[1] if len(bits) > 1 else "bar"
        counter["chart"] += 1
        key = f"@@CHART_{counter['chart']}@@"
        req = _parse_chart(kind, raw)
        req.slot = key
        charts.append(req)
        return f"\n\n{key}\n\n"

    return SPECIAL_FENCE_RE.sub(repl, md_text), blocks, charts


def _extract_special_blocks(html: str) -> tuple[str, List[ChartRequest]]:
    charts: List[ChartRequest] = []
    counter = {"metric": 0, "chart": 0}

    def metrics_repl(match: re.Match[str]) -> str:
        raw = html_lib.unescape(match.group(1))
        html_block = _metrics_html(raw.splitlines())
        return html_block or match.group(0)

    html = re.sub(
        r'<pre><code class="language-metrics">(.*?)</code></pre>',
        metrics_repl, html, flags=re.S,
    )

    def chart_repl(match: re.Match[str]) -> str:
        lang = match.group(1) or "chart"
        raw = html_lib.unescape(match.group(2))
        kind = "bar"
        if lang.startswith("chart"):
            bits = lang.split()
            if len(bits) > 1:
                kind = bits[1]
        req = _parse_chart(kind, raw)
        counter["chart"] += 1
        slot = f"@@CHART_{counter['chart']}@@"
        req.slot = slot
        charts.append(req)
        return slot

    html = re.sub(
        r'<pre><code class="language-(chart[^"]*)">(.*?)</code></pre>',
        chart_repl, html, flags=re.S,
    )
    return html, charts


def _extract_images(html: str) -> tuple[str, List[ImageRequest]]:
    requests: List[ImageRequest] = []
    counter = {"img": 0}

    def fig_repl(match: re.Match[str]) -> str:
        tag = match.group(0)
        src_m = re.search(r'src="([^"]+)"', tag)
        alt_m = re.search(r'alt="([^"]*)"', tag)
        if not src_m:
            return tag
        src = src_m.group(1)
        alt = html_lib.unescape(alt_m.group(1)) if alt_m else ""
        counter["img"] += 1
        slot = f"@@IMG_{counter['img']}@@"
        kind = "search"
        query = path = url = ""
        if src.startswith("search:"):
            kind, query = "search", src[len("search:"):]
        elif src.startswith("img:"):
            kind, path = "file", src[len("img:"):]
        elif src.startswith("http://") or src.startswith("https://"):
            kind, url = "url", src
        else:
            kind, path = "file", src
        req = ImageRequest(slot=slot, query=query, path=path, alt=alt,
                           caption=alt, kind=kind, url=url)
        requests.append(req)
        return slot

    html = re.sub(r"<img\b[^>]*>", fig_repl, html, flags=re.I)
    return html, requests


NUMERIC_RE = re.compile(r"^[£$€]?\s?-?[\d,]+(?:\.\d+)?\s?%?$")


def _cell_text(cell_html: str) -> str:
    return re.sub(r"<[^>]+>", "", cell_html).strip()


def _decorate_tables(html: str, keep_max_rows: int = 9) -> str:
    """Improve tables for print.

    * short tables stay on one page (`class="keep"`)
    * numeric columns are right-aligned (`class="num"`)
    """
    def repl(match: re.Match[str]) -> str:
        table_html = match.group(0)
        rows = table_html.count("<tr")
        if rows <= keep_max_rows:
            table_html = table_html.replace("<table", '<table class="keep"', 1)

        body = re.search(r"<tbody>(.*?)</tbody>", table_html, flags=re.S | re.I)
        if not body:
            return table_html

        body_rows = re.findall(r"<tr[^>]*>(.*?)</tr>", body.group(1), flags=re.S | re.I)
        if not body_rows:
            return table_html

        column_count = 0
        parsed_rows = []
        for row in body_rows:
            cells = re.findall(r"<t([dh])[^>]*>(.*?)</t\1>", row, flags=re.S | re.I)
            parsed_rows.append(cells)
            column_count = max(column_count, len(cells))

        numeric_columns = []
        for col in range(column_count):
            values = [
                _cell_text(cells[col][1])
                for cells in parsed_rows
                if col < len(cells) and _cell_text(cells[col][1])
            ]
            if not values:
                numeric_columns.append(False)
                continue
            numeric = sum(1 for v in values if NUMERIC_RE.match(v.replace(" ", "")))
            numeric_columns.append(numeric / len(values) >= 0.6)

        if not any(numeric_columns):
            return table_html

        def fix_row(row_match: re.Match[str]) -> str:
            row_html = row_match.group(0)
            index = {"i": 0}

            def fix_cell(cell_match: re.Match[str]) -> str:
                tag, attrs, inner = cell_match.group(1), cell_match.group(2), cell_match.group(3)
                col = index["i"]
                index["i"] += 1
                if col < len(numeric_columns) and numeric_columns[col] and "num" not in attrs:
                    return f"<t{tag}{attrs} class=\"num\">{inner}</t{tag}>"
                return cell_match.group(0)

            return re.sub(r"<t([dh])([^>]*)>(.*?)</t\1>", fix_cell, row_html, flags=re.S | re.I)

        return re.sub(r"<tr[^>]*>.*?</tr>", fix_row, table_html, flags=re.S | re.I)

    return re.sub(r"<table\b.*?</table>", repl, html, flags=re.S | re.I)


def _add_heading_ids(html: str) -> tuple[str, List[TocEntry]]:
    toc: List[TocEntry] = []
    used: Dict[str, int] = {}

    def repl(match: re.Match[str]) -> str:
        level = int(match.group(1))
        attrs = match.group(2) or ""
        text = match.group(3)
        plain = re.sub(r"<[^>]+>", "", text).strip()
        if not plain:
            return match.group(0)
        # Markdown's toc extension already adds ids; drop them to avoid duplicates.
        existing_id = re.search(r'''\bid=["']([^"']+)["']''', attrs)
        attrs = re.sub(r'''\s+id=["'][^"']*["']''', "", attrs or "")
        if "no-toc" in attrs or "data-notoc" in attrs:
            sid = existing_id.group(1) if existing_id else slugify(plain)
            return f'<h{level}{attrs} id="{sid}">{text}</h{level}>'
        base = existing_id.group(1) if existing_id else slugify(plain)
        count = used.get(base, 0)
        used[base] = count + 1
        sid = base if count == 0 else f"{base}-{count + 1}"
        if level <= 3:
            # Store the raw text; Jinja autoescaping handles HTML safety.
            toc.append(TocEntry(level=level, text=plain, id=sid))
        return f'<h{level}{attrs} id="{sid}">{text}</h{level}>'

    html = re.sub(r"<h([1-6])([^>]*)>(.*?)</h\1>", repl, html, flags=re.S | re.I)
    return html, toc


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def _load_json(text: str) -> tuple[Dict[str, Any], str]:
    data = json.loads(text)
    meta = data.get("meta") or {}
    if "markdown" in data:
        return meta, data["markdown"]
    if "html" in data:
        return meta, data["html"]
    if "sections" in data:
        parts = []
        for sec in data["sections"]:
            if isinstance(sec, str):
                parts.append(sec)
            else:
                heading = sec.get("heading", "")
                body = sec.get("body", sec.get("markdown", sec.get("html", "")))
                level = sec.get("level", 2)
                if heading:
                    parts.append(f"{'#' * int(level)} {heading}\n\n{body}")
                else:
                    parts.append(body)
        return meta, "\n\n".join(parts)
    return meta, ""


def load_document(path: str | Path) -> Document:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    meta: Dict[str, Any] = {}
    body_text = text
    is_html = False

    if suffix == ".json":
        meta, body_text = _load_json(text)
        is_html = 'html' in json.loads(text) and 'markdown' not in json.loads(text)
    elif suffix in (".html", ".htm"):
        meta, body_text = parse_frontmatter(text)
        is_html = True
    else:
        meta, body_text = parse_frontmatter(text)

    chart_requests: List[ChartRequest] = []
    if is_html:
        body_html = body_text
        body_html = _transform_callouts(body_html)
        body_html, chart_requests = _extract_special_blocks(body_html)
    else:
        prepared, blocks, chart_requests = _prepare_markdown_blocks(body_text)
        body_html = _markdown_to_html(prepared)
        body_html = _transform_callouts(body_html)
        # Block placeholders may be wrapped in <p> by the converter.
        for key, value in blocks.items():
            body_html = re.sub(
                r"<p>\s*" + re.escape(key) + r"\s*</p>", lambda _m, v=value: v, body_html
            )
            body_html = body_html.replace(key, value)
        # Also allow raw HTML-style blocks in Markdown sources.
        body_html, extra_charts = _extract_special_blocks(body_html)
        chart_requests += extra_charts

    body_html, image_requests = _extract_images(body_html)
    body_html = _decorate_tables(body_html)
    body_html, toc = _add_heading_ids(body_html)

    doc = Document(
        meta=meta, body_html=body_html, toc=toc,
        image_requests=image_requests, chart_requests=chart_requests, source_path=path,
    )
    from .blocks import parse_blocks
    doc.blocks = list(parse_blocks(doc))
    return doc
