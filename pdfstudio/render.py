"""Rendering pipeline: one HTML document -> Chromium PDF -> accessibility finalize.

The cover and the body are rendered as *one* document.  Chromium can then
produce a single tagged PDF with a real structure tree; merging two PDFs with
pypdf or PyMuPDF silently drops ``StructTreeRoot``.  A named ``@page cover``
gives the first page a zero margin and suppresses the running header/footer.

After Chromium, PyMuPDF sets the metadata Chromium does not carry (author,
subject, keywords), the document language, the page mode, and the outline.
Saving with ``garbage=3`` keeps the structure tree, ``MarkInfo``, and ``Lang``.
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .art_direction import ArtDirection, DIRECTIONS
from .charts import make_chart
from .content import Document, TocEntry
from .images import (
    ResolvedImage,
    credits_html,
    figure_html,
    resolve_file,
    resolve_search,
    resolve_url,
)
from .scenarios import Scenario, get_scenario
from .tokens import DesignSystem, get_theme

try:
    from playwright.sync_api import sync_playwright  # type: ignore
except Exception:  # pragma: no cover
    sync_playwright = None

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None


ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT / "pdfstudio" / "templates"
CSS_DIR = ROOT / "assets" / "css"

PAGE_SIZES_MM = {
    "A3": (297.0, 420.0),
    "A4": (210.0, 297.0),
    "A5": (148.0, 210.0),
    "Letter": (215.9, 279.4),
    "Legal": (215.9, 355.6),
    "Tabloid": (279.4, 431.8),
}


# ---------------------------------------------------------------------------
# Options / result
# ---------------------------------------------------------------------------

@dataclass
class RenderOptions:
    output: Path
    scenario: Optional[str] = None
    theme: Optional[str] = None
    composition: Optional[str] = None
    output_mode: Optional[str] = None
    art_direction: Optional[str] = None
    page_size: Optional[str] = None
    landscape: Optional[bool] = None
    toc: Optional[bool] = None
    cover: Optional[bool] = None
    engine: str = "auto"          # auto | playwright | weasyprint
    images: str = "auto"          # auto | off
    preview: bool = True
    preview_pages: int = 6
    stamp: bool = True
    bookmarks: bool = True
    extra_css: str = ""
    contrast: bool = True
    work_dir: Optional[Path] = None
    keep_html: bool = False


@dataclass
class RenderResult:
    pdf_path: Path
    html_path: Optional[Path]
    pages: int
    cover_pages: int
    previews: List[Path] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    report: Dict[str, Any] = field(default_factory=dict)
    direction_id: str = ""
    direction_label: str = ""
    contrast_report: Dict[str, Any] = field(default_factory=dict)
    design_manifest: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mm(value: float) -> float:
    return value * 72.0 / 25.4


def _page_dims(page: str, landscape: bool) -> tuple[float, float]:
    w, h = PAGE_SIZES_MM.get(page, PAGE_SIZES_MM["A4"])
    return (h, w) if landscape else (w, h)


def _parse_margins(margin: str) -> tuple[float, float, float, float]:
    """Return (top, right, bottom, left) in mm from a CSS margin string."""
    vals = re.findall(r"(-?\d+(?:\.\d+)?)\s*mm", margin)
    nums = [float(v) for v in vals]
    if not nums:
        return 20.0, 18.0, 22.0, 18.0
    if len(nums) == 1:
        return nums[0], nums[0], nums[0], nums[0]
    if len(nums) == 2:
        return nums[0], nums[1], nums[0], nums[1]
    if len(nums) == 3:
        return nums[0], nums[1], nums[2], nums[1]
    return nums[0], nums[1], nums[2], nums[3]


def _hex_rgb(value: str) -> tuple[float, float, float]:
    value = value.strip().lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        r = int(value[0:2], 16) / 255.0
        g = int(value[2:4], 16) / 255.0
        b = int(value[4:6], 16) / 255.0
        return (r, g, b)
    except Exception:
        return (0.0, 0.0, 0.0)


def _abs_path(raw: str, doc: Document) -> Path:
    p = Path(raw)
    if p.is_absolute():
        return p
    base = doc.source_path.parent if doc.source_path else Path.cwd()
    return (base / p).resolve()


def _today() -> str:
    return _dt.date.today().strftime("%d %B %Y")


def _read_css() -> tuple[str, str, str, str]:
    base = (CSS_DIR / "base.css").read_text(encoding="utf-8")
    overrides = (CSS_DIR / "overrides.css").read_text(encoding="utf-8")
    fonts_path = CSS_DIR / "fonts.css"
    fonts = fonts_path.read_text(encoding="utf-8") if fonts_path.exists() else ""
    directions_path = CSS_DIR / "directions.css"
    directions = directions_path.read_text(encoding="utf-8") if directions_path.exists() else ""
    return base, overrides, fonts, directions


def _jinja() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _normalise(text: str) -> str:
    text = _html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip().casefold()
    return text


def _css_string(value: str) -> str:
    """Escape a value for a CSS generated-content string."""
    return '"' + str(value or "").replace("\\", "\\\\").replace('"', '\\"') + '"'


def _clip(text: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"


# ---------------------------------------------------------------------------
# CSS assembly
# ---------------------------------------------------------------------------

def _page_rules(ds: DesignSystem, scenario: Scenario, page_w: float,
                page_h: float, meta: Dict[str, Any], stamp: bool) -> str:
    """The @page rules, including running headers/footers.

    Chromium honours CSS margin boxes.  Using them keeps page furniture in the
    HTML/CSS layer, at a real 9pt in the brand font, and lets ``@page cover``
    suppress it without drawing over the artwork.
    """
    margin = ds.margin
    top, right, bottom, left = _parse_margins(margin)
    inner_w = max(10.0, page_w - left - right)
    inner_h = max(10.0, page_h - top - bottom)

    lines = [
        f"@page {{",
        f"  size: {page_w}mm {page_h}mm;",
        f"  margin: {margin};",
        f"  background: {ds.palette.bg};",
    ]

    header_on = bool(stamp and scenario.header and meta.get("header", True) is not False)
    footer_on = bool(stamp and scenario.footer and meta.get("footer", True) is not False)
    title = str(meta.get("running_title") or meta.get("title") or "")
    confidential = str(meta.get("confidential") or "")
    org = str(meta.get("org") or meta.get("author") or "")
    date = str(meta.get("date") or "")
    website = str(meta.get("website") or "")

    if header_on and title:
        lines += [
            "  @top-left {",
            f"    content: {_css_string(_clip(title, 64))};",
            "    font-family: var(--font-body);",
            "    font-size: 9pt;",
            "    color: var(--muted);",
            "    vertical-align: bottom;",
            "    padding-bottom: 2.5mm;",
            "  }",
        ]
    if header_on and confidential:
        lines += [
            "  @top-right {",
            f"    content: {_css_string(confidential.upper())};",
            "    font-family: var(--font-body);",
            "    font-size: 9pt;",
            "    color: var(--accent);",
            "    vertical-align: bottom;",
            "    padding-bottom: 2.5mm;",
            "  }",
        ]
    if footer_on and org:
        lines += [
            "  @bottom-left {",
            f"    content: {_css_string(_clip(org, 42))};",
            "    font-family: var(--font-body);",
            "    font-size: 9pt;",
            "    color: var(--muted);",
            "    vertical-align: top;",
            "    padding-top: 2.5mm;",
            "  }",
        ]
    if footer_on and (date or website):
        lines += [
            "  @bottom-center {",
            f"    content: {_css_string(_clip(website or date, 42))};",
            "    font-family: var(--font-body);",
            "    font-size: 9pt;",
            "    color: var(--muted);",
            "    vertical-align: top;",
            "    padding-top: 2.5mm;",
            "  }",
        ]
    if footer_on:
        lines += [
            "  @bottom-right {",
            '    content: "Page " counter(page) " of " counter(pages);',
            "    font-family: var(--font-body);",
            "    font-size: 9pt;",
            "    color: var(--muted);",
            "    vertical-align: top;",
            "    padding-top: 2.5mm;",
            "  }",
        ]
    lines.append("}")

    # The cover page: zero margin, no running furniture.
    lines += [
        "@page cover {",
        f"  size: {page_w}mm {page_h}mm;",
        "  margin: 0;",
        f"  background: {ds.palette.cover_bg or ds.palette.bg};",
        "  @top-left { content: none; }",
        "  @top-center { content: none; }",
        "  @top-right { content: none; }",
        "  @bottom-left { content: none; }",
        "  @bottom-center { content: none; }",
        "  @bottom-right { content: none; }",
        "}",
    ]

    lines.append(
        f":root {{ --page-w: {page_w}mm; --page-h: {page_h}mm; "
        f"--inner-w: {inner_w:.2f}mm; --inner-h: {inner_h:.2f}mm; }}"
    )
    from .geometry import PageGeometry, page_field_css
    from .compositions import _contrast
    geometry = PageGeometry(page_w, page_h, _parse_margins(ds.margin))
    for name, colour in (('bg', ds.palette.bg), ('panel', ds.palette.panel), ('accent', ds.palette.accent)):
        lines.append(page_field_css('field-' + name, colour, geometry))
        ink = '#FFFFFF' if _contrast('#FFFFFF', colour) >= _contrast('#000000', colour) else '#000000'
        furniture = ' '.join('@' + box + ' { color: ' + ink + '; }' for box in ('top-left','top-center','top-right','bottom-left','bottom-center','bottom-right'))
        lines.append('@page field-' + name + ' { ' + furniture + ' }')
    return "\n".join(lines)


def _css(ds: DesignSystem, scenario: Scenario, direction: ArtDirection,
         page_w: float, page_h: float, meta: Dict[str, Any],
         extra_css: str = "", stamp: bool = True) -> str:
    base, overrides, fonts, directions = _read_css()
    from .compositions import _contrast
    tokens = ds.css_vars()
    accent_ink = '#FFFFFF' if _contrast('#FFFFFF', ds.palette.accent) >= _contrast('#000000', ds.palette.accent) else '#000000'
    tokens += f'\n--accent-field-ink: {accent_ink};'
    return "\n".join([
        ":root {", tokens, "}",
        _page_rules(ds, scenario, page_w, page_h, meta, stamp),
        fonts,
        base,
        overrides,
        (ROOT / 'assets' / 'css' / 'components.css').read_text(encoding='utf-8'),
        (ROOT / 'assets' / 'css' / 'compositions.css').read_text(encoding='utf-8'),
        extra_css or "",
    ])


# ---------------------------------------------------------------------------
# Asset resolution
# ---------------------------------------------------------------------------

def _asset_identity(img: ResolvedImage) -> List[str]:
    keys = []
    for value in (img.source_title, img.source_url, img.caption):
        value = str(value or "").strip().casefold()
        if value:
            keys.append(value)
    return keys


def _resolve_assets(doc: Document, opts: RenderOptions, ds: DesignSystem,
                    avoid: Optional[set[str]] = None
                    ) -> tuple[str, str, List[ResolvedImage], set[str]]:
    """Resolve images and charts in document order, numbering figures once."""
    body = doc.body_html
    resolved: List[ResolvedImage] = []
    used = set(avoid or ())
    fig_no = 0

    items: List[Tuple[int, str, Any]] = []
    for req in doc.image_requests:
        items.append((body.find(req.slot), "image", req))
    for req in doc.chart_requests:
        items.append((body.find(req.slot), "chart", req))
    items.sort(key=lambda item: (item[0] if item[0] >= 0 else 10 ** 9))

    for _position, kind, req in items:
        if kind == "chart":
            fig_no += 1
            try:
                body = body.replace(req.slot, make_chart(req, ds, number=fig_no))
            except Exception:
                body = body.replace(req.slot, "")
            continue

        img = ResolvedImage(error="image search disabled")
        if req.kind == "search":
            if opts.images != "off":
                img = resolve_search(req.query, req.caption or req.alt, avoid=used)
        elif req.kind == "file":
            img = resolve_file(str(_abs_path(req.path, doc)), req.caption or req.alt)
        elif req.kind == "url":
            img = resolve_url(req.url, req.caption or req.alt)

        fig_no += 1
        if img.ok:
            used.update(_asset_identity(img))
            body = body.replace(req.slot, figure_html(img, req.alt, fig_no))
        else:
            body = body.replace(req.slot, figure_html(img, req.alt or req.query, fig_no))
            if req.kind == "search" and opts.images != "off":
                doc.warnings.append(f"Image '{req.query}' could not be sourced: {img.error}")
        resolved.append(img)

    return body, credits_html(resolved), resolved, used


def _resolve_cover(meta: Dict[str, Any], doc: Document, opts: RenderOptions) -> ResolvedImage:
    candidate = meta.get("cover_image") or meta.get("cover_photo") or ""
    if not candidate:
        return ResolvedImage(error="no cover image requested")
    candidate = str(candidate)
    caption = str(meta.get("cover_caption") or meta.get("title") or "Cover image")
    img = ResolvedImage()
    if candidate.startswith("search:"):
        if opts.images != "off":
            img = resolve_search(candidate[len("search:"):], caption)
    elif candidate.startswith(("http://", "https://")):
        img = resolve_url(candidate, caption)
    else:
        img = resolve_file(str(_abs_path(candidate, doc)), caption)
    return img


def _resolve_logo(meta: Dict[str, Any], doc: Document) -> str:
    logo = meta.get("logo") or ""
    if not logo:
        return ""
    img = ResolvedImage()
    logo = str(logo)
    if logo.startswith(("http://", "https://")):
        img = resolve_url(logo)
    else:
        img = resolve_file(str(_abs_path(logo, doc)))
    return img.data_uri if img.ok else ""


# ---------------------------------------------------------------------------
# HTML build
# ---------------------------------------------------------------------------

def _meta(doc: Document) -> Dict[str, Any]:
    meta = dict(doc.meta or {})
    if not meta.get("title"):
        m = re.search(r"<h1[^>]*>(.*?)</h1>", doc.body_html, flags=re.S | re.I)
        if m:
            meta["title"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        else:
            meta["title"] = (doc.source_path.stem.replace("_", " ").title()
                             if doc.source_path else "Untitled document")
    meta.setdefault("date", _today())
    meta.setdefault("lang", "en")
    return meta


def _toc_entries(doc: Document, scenario: Scenario, include: bool,
                 max_level: int = 2) -> List[Dict[str, Any]]:
    if not include:
        return []
    entries = []
    for e in doc.toc:
        if e.level > max_level:
            continue
        entries.append({"level": e.level, "text": e.text, "id": e.id, "page": None})
    return entries


def _cover_title_lines(meta: Dict[str, Any]) -> List[str]:
    supplied = meta.get("cover_title_lines")
    if isinstance(supplied, list):
        lines = [str(line).strip() for line in supplied if str(line).strip()]
        if lines:
            return lines[:3]
    if isinstance(supplied, str) and supplied.strip():
        lines = [line.strip() for line in supplied.split("|") if line.strip()]
        if lines:
            return lines[:3]

    title = str(meta.get("title") or "Untitled document").strip()
    if ":" in title:
        first, rest = title.split(":", 1)
        return [first.strip(), rest.strip()]
    words = title.split()
    if len(words) >= 5:
        pivot = max(2, len(words) // 2)
        return [" ".join(words[:pivot]), " ".join(words[pivot:])]
    return [title]


def _wrap_chapters(body: str) -> str:
    """Wrap top-level sections so art directions can compose, not just skin.

    Markdown yields a flat stream.  Direction CSS needs chapter boundaries to
    create changing colour fields, asymmetric layouts, and deliberate page
    rhythm.  Each H1 starts a chapter; IDs become stable chapter class names.
    """
    heading = re.compile(r'<h1\b[^>]*\bid="([^"]+)"[^>]*>.*?</h1>', re.S | re.I)
    matches = list(heading.finditer(body))
    if not matches:
        return body
    pieces: List[str] = []
    if matches[0].start() > 0:
        pieces.append(body[:matches[0].start()])
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        chapter_id = re.sub(r"[^a-z0-9-]+", "-", match.group(1).casefold()).strip("-")
        segment = body[match.start():end]
        pieces.append(
            f'<section class="chapter chapter--{index + 1} chapter--{chapter_id}" '
            f'data-chapter="{index + 1}">{segment}</section>'
        )
    return "".join(pieces)


def _cover_fragment(ds: DesignSystem, scenario: Scenario, meta: Dict[str, Any],
                    direction: ArtDirection, cover_image_uri: str, logo_uri: str,
                    body_classes: str) -> Optional[str]:
    default_style = "none" if scenario.cover == "none" else ds.cover_style
    style = str(meta.get("cover_style") or default_style or scenario.cover or "split")
    if style == "none" or meta.get("cover") is False:
        return None

    env = _jinja()
    tmpl = env.get_template("cover.html.j2")
    brand_mark = f'<img class="cover__logo" src="{logo_uri}" alt="logo" />' if logo_uri else ""
    return tmpl.render(
        theme=ds.id,
        scenario=scenario.id,
        direction=direction.id,
        body_classes=body_classes,
        title=meta.get("title", ""),
        title_lines=_cover_title_lines(meta),
        subtitle=meta.get("subtitle", ""),
        summary=meta.get("summary", meta.get("description", "")),
        author=meta.get("author", ""),
        org=meta.get("org", meta.get("organisation", "")),
        client=meta.get("client", ""),
        date=meta.get("date", ""),
        version=meta.get("version", ""),
        eyebrow=meta.get("eyebrow", ""),
        kicker=meta.get("kicker", meta.get("series", "")),
        confidential=meta.get("confidential", ""),
        cover_style=style,
        cover_image_uri=cover_image_uri,
        cover_fit=meta.get('_cover_fit', 'contain'),
        cover_focal=meta.get('_cover_focal', '50% 50%'),
        brand_mark=brand_mark,
        lang=meta.get("lang", "en"),
    )


def _body_fragment(ds: DesignSystem, scenario: Scenario, direction: ArtDirection,
                   meta: Dict[str, Any], body: str, credits: str,
                   toc_entries: List[Dict[str, Any]], body_classes: str) -> str:
    env = _jinja()
    tmpl = env.get_template("body.html.j2")
    return tmpl.render(
        theme=ds.id,
        scenario=scenario.id,
        direction=direction.id,
        body_classes=body_classes,
        body_html=body if meta.get('_composed') else _wrap_chapters(body),
        credits_html=credits,
        toc_entries=toc_entries,
        toc_label=meta.get("toc_label", "Contents"),
        toc_title=meta.get("toc_title", "In this document"),
        back_cover=meta.get("back_cover"),
        back_cover_image_uri=meta.get("back_cover_image_uri", ""),
    )


def _document_html(ds: DesignSystem, scenario: Scenario, direction: ArtDirection,
                   meta: Dict[str, Any], css: str, body_classes: str,
                   cover_html: str, body_html: str) -> str:
    env = _jinja()
    tmpl = env.get_template("document.html.j2")
    keywords = meta.get("keywords") or ", ".join(
        part for part in (meta.get("title"), meta.get("client"), meta.get("org"), scenario.label)
        if part
    )
    return tmpl.render(
        css=css,
        theme=ds.id,
        scenario=scenario.id,
        direction=direction.id,
        body_classes=body_classes,
        title=meta.get("title", ""),
        author=meta.get("author", ""),
        description=meta.get("description", meta.get("summary", "")),
        keywords=keywords,
        lang=meta.get("lang", "en"),
        cover_html=cover_html or "",
        body_html=body_html,
    )


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def _render_playwright(html: str, path: Path, work_dir: Path) -> None:
    if sync_playwright is None:
        raise RuntimeError("Playwright is not installed")
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--font-render-hinting=none", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1400, "height": 1800})
        page.set_content(html, wait_until="load")
        page.emulate_media(media="print")
        try:
            page.evaluate("() => document.fonts.ready.then(() => true)")
        except Exception:
            pass
        try:
            page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        page.wait_for_timeout(120)
        kwargs = dict(
            path=str(path),
            print_background=True,
            prefer_css_page_size=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        try:
            page.pdf(**kwargs, tagged=True, outline=True)
        except TypeError:
            page.pdf(**kwargs)
        browser.close()


def _render_weasyprint(html: str, path: Path, work_dir: Path, base_url: Path) -> None:
    from weasyprint import HTML  # type: ignore
    HTML(string=html, base_url=str(base_url)).write_pdf(str(path))


def _render(html: str, path: Path, opts: RenderOptions, base_url: Path) -> str:
    engine = opts.engine
    last: Optional[Exception] = None
    if engine in ("auto", "playwright"):
        try:
            _render_playwright(html, path, base_url)
            return "playwright"
        except Exception as exc:
            if engine == "playwright":
                raise
            last = exc
    if engine in ("auto", "weasyprint"):
        try:
            _render_weasyprint(html, path, opts.work_dir or base_url, base_url)
            return "weasyprint"
        except Exception as exc:
            if engine == "weasyprint":
                raise
            last = exc
    raise RuntimeError(f"no PDF engine available: {last}")


# ---------------------------------------------------------------------------
# TOC page numbers
# ---------------------------------------------------------------------------

def _scan_heading_pages(pdf_path: Path, entries: List[Dict[str, Any]],
                        toc_title: str) -> Dict[str, int]:
    if fitz is None or not entries:
        return {}
    doc = fitz.open(str(pdf_path))
    pages_text = [_normalise(p.get_text()) for p in doc]
    doc.close()

    # Skip leading TOC pages (the TOC repeats heading text).
    start = 0
    toc_norm = _normalise(toc_title)
    for i, text in enumerate(pages_text[:5]):
        if toc_norm and toc_norm in text:
            start = i + 1

    page_map: Dict[str, int] = {}
    cursor = start
    for entry in entries:
        target = _normalise(entry["text"])
        if not target:
            continue
        target = re.sub(r"^[\d.\-\u2013\u2014]+\s*", "", target)
        for i in range(cursor, len(pages_text)):
            if target and target in pages_text[i]:
                page_map[entry["id"]] = i + 1
                cursor = i
                break
    return page_map


# ---------------------------------------------------------------------------
# Finalize: metadata, language, page mode, outline
# ---------------------------------------------------------------------------

def _pdf_date() -> str:
    now = _dt.datetime.now()
    return now.strftime("D:%Y%m%d%H%M%S")


def _finalize_pdf(raw_path: Path, out: Path, meta: Dict[str, Any],
                  entries: List[Dict[str, Any]], bookmarks: bool) -> int:
    if fitz is None:
        # Last-resort copy.  Structure and metadata are preserved as Chromium
        # wrote them, but author/subject/keywords cannot be added.
        out.write_bytes(raw_path.read_bytes())
        doc = fitz.open(str(out))
        total = doc.page_count
        doc.close()
        return total

    doc = fitz.open(str(raw_path))
    total = doc.page_count
    title = str(meta.get("title", "")).strip()
    author = str(meta.get("author", "")).strip()
    subject = str(meta.get("description") or meta.get("summary") or "").strip()
    keywords = str(meta.get("keywords") or "").strip()
    if not keywords:
        keywords = ", ".join(part for part in (
            meta.get("title"), meta.get("client"), meta.get("org"),
            meta.get("scenario"),
        ) if part)

    doc.set_metadata({
        "title": title,
        "author": author,
        "subject": subject,
        "keywords": keywords,
        "creator": "PDF Studio",
        "producer": "PDF Studio (Chromium)",
        "creationDate": _pdf_date(),
        "modDate": _pdf_date(),
    })

    catalog = doc.pdf_catalog()
    lang = str(meta.get("lang") or "en")
    try:
        doc.xref_set_key(catalog, "Lang", f"({lang})")
    except Exception:
        pass

    toc: List[List[Any]] = []
    if bookmarks:
        for e in entries:
            page_no = e.get("page")
            if not page_no:
                continue
            toc.append([int(e["level"]), str(e["text"]).strip(), int(page_no)])
    try:
        if toc:
            doc.set_toc(toc)
            doc.xref_set_key(catalog, "PageMode", "/UseOutlines")
        else:
            doc.xref_set_key(catalog, "PageMode", "/UseNone")
    except Exception:
        pass

    temp = out.with_name(out.stem + ".finalizing.pdf")
    doc.save(str(temp), garbage=3, deflate=True)
    doc.close()
    os.replace(temp, out)
    return total


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def render(doc: Document, opts: RenderOptions) -> RenderResult:
    opts.output = Path(opts.output).resolve()
    from .design import resolve_design
    scenario = get_scenario(opts.scenario or str(doc.meta.get('scenario') or 'report'))
    meta = _meta(doc)
    meta['scenario'] = scenario.id
    decision = resolve_design(doc, opts)
    direction = DIRECTIONS[decision.direction_id]
    ds = decision.tokens
    meta['composition'] = decision.family_id
    meta['output_mode'] = decision.output_mode

    page = opts.page_size or str(doc.meta.get("page_size") or scenario.page)
    landscape = opts.landscape if opts.landscape is not None else bool(
        doc.meta.get("landscape", scenario.landscape)
    )
    from .geometry import resolve_geometry
    geometry = resolve_geometry(page, landscape, decision.output_mode, (meta.get('design') or {}).get('safe_mm'))
    page_w, page_h = geometry.width_mm, geometry.height_mm
    ds.margin = geometry.margin_css

    include_toc = opts.toc if opts.toc is not None else bool(
        meta.get("toc", scenario.toc)
    )
    try:
        toc_depth = int(meta.get("toc_depth", 2))
    except (TypeError, ValueError):
        toc_depth = 2
    toc_entries = _toc_entries(doc, scenario, include_toc, max_level=toc_depth)

    work = opts.work_dir or (opts.output.parent / ".pdfstudio")
    work.mkdir(parents=True, exist_ok=True)
    raw_pdf = work / "document.pdf"
    first_pdf = work / "document-pass1.pdf"

    from dataclasses import replace
    from .blocks import parse_blocks
    from .asset_render import collect_assets, render_assets, replace_slots
    from .compositions import plan_sections, render_sections, apply_asset_accent, adapt_composition
    assets = collect_assets(doc, meta, opts)
    decision = apply_asset_accent(decision, assets.layouts)
    ds = decision.tokens
    ds.margin = geometry.margin_css
    source_blocks = tuple(doc.blocks) if doc.blocks else parse_blocks(doc)
    decision = adapt_composition(decision, source_blocks, assets.layouts)
    meta['composition'] = decision.family_id
    section_layouts = plan_sections(source_blocks, decision, assets.layouts, geometry, meta)
    render_assets(doc, assets, decision, geometry, section_layouts)
    resolved_blocks = tuple(replace(b, html=replace_slots(b.html, assets.replacements)) for b in source_blocks)
    catalogue_credits = bool(section_layouts and section_layouts[-1].family_id == 'object-catalogue' and section_layouts[-1].columns == 2)
    body = render_sections(resolved_blocks, section_layouts, assets.credits if catalogue_credits else '')
    meta['_composed'] = True
    cover_asset = assets.images.get('cover', ResolvedImage())
    cover_image = cover_asset.data_uri if cover_asset.ok else ''
    if cover_image and 'cover_style' not in meta:
        meta['cover_style'] = 'object' if decision.family_id == 'object-catalogue' else 'split'
    if 'cover' in assets.layouts:
        a = assets.layouts['cover']
        meta['_cover_fit'] = 'contain' if a.role in ('object','logo','diagram') else a.fit
        meta['_cover_focal'] = f'{a.focal[0]*100:g}% {a.focal[1]*100:g}%'
    credits = '' if catalogue_credits else assets.credits
    warnings: List[str] = list(doc.warnings)
    logo = _resolve_logo(meta, doc)

    base_classes = []
    if scenario.numbered_sections:
        base_classes.append("numbered")
    base_classes.append(f"theme-{ds.id}")
    base_classes.append(f"scenario-{scenario.id}")
    base_classes.append(f"direction-{direction.id}")
    body_classes = " ".join(base_classes)

    css = _css(ds, scenario, direction, page_w, page_h, meta,
               extra_css=opts.extra_css, stamp=opts.stamp)
    cover_html = _cover_fragment(ds, scenario, meta, direction, cover_image,
                                 logo, body_classes) if opts.cover is not False else None
    body_html = _body_fragment(ds, scenario, direction, meta, body, credits,
                               toc_entries, body_classes)
    document_html = _document_html(ds, scenario, direction, meta, css,
                                   body_classes, cover_html or "", body_html)

    # ---- optional contrast probe ---------------------------------------
    contrast_report: Dict[str, Any] = {}
    if opts.contrast:
        try:
            from .contrast import probe_html, format_report as format_contrast
            report = probe_html(document_html)
            contrast_report = report.to_dict()
            if report.fix_css:
                css = css + "\n" + report.fix_css
                document_html = _document_html(ds, scenario, direction, meta, css,
                                               body_classes, cover_html or "", body_html)
            if report.issues:
                warnings.append(format_contrast(report))
        except Exception as exc:
            warnings.append(f"Contrast probe skipped: {exc}")

    # ---- pass 1 ---------------------------------------------------------
    _render(document_html, first_pdf, opts, work)

    toc_title = str(meta.get("toc_title", "In this document"))
    page_map = _scan_heading_pages(first_pdf, toc_entries, toc_title)
    if page_map:
        for entry in toc_entries:
            if entry["id"] in page_map:
                entry["page"] = page_map[entry["id"]]
        if include_toc:
            document_html = _document_html(ds, scenario, direction, meta, css,
                                           body_classes, cover_html or "", _body_fragment(
                                               ds, scenario, direction, meta, body, credits,
                                               toc_entries, body_classes))
            _render(document_html, raw_pdf, opts, work)
            page_map2 = _scan_heading_pages(raw_pdf, toc_entries, toc_title)
            if page_map2 and page_map2 != page_map:
                for entry in toc_entries:
                    if entry["id"] in page_map2:
                        entry["page"] = page_map2[entry["id"]]
                document_html = _document_html(ds, scenario, direction, meta, css,
                                               body_classes, cover_html or "", _body_fragment(
                                                   ds, scenario, direction, meta, body, credits,
                                                   toc_entries, body_classes))
                _render(document_html, raw_pdf, opts, work)
        else:
            raw_pdf = first_pdf
    else:
        raw_pdf = first_pdf
        if toc_entries and include_toc:
            warnings.append("TOC page numbers could not be detected; rendered without them.")

    # ---- finalize -------------------------------------------------------
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    total = _finalize_pdf(raw_pdf, opts.output, meta, toc_entries, opts.bookmarks)

    html_path = None
    if opts.keep_html:
        html_path = opts.output.with_suffix(".html")
        html_path.write_text(document_html, encoding="utf-8")

    # ---- QA / previews --------------------------------------------------
    previews: List[Path] = []
    report: Dict[str, Any] = {}
    try:
        from .qa import analyze
        margins = _parse_margins(ds.margin)
        expect = {
            "body_size_pt": _pt_value(ds.body_size),
            "min_font_pt": 9.0,
            "measure_ch": 68,
            "margins_mm": margins,
            "cover_pages": 1 if cover_html else 0,
            "toc_pages": 1 if include_toc and toc_entries else 0,
            "requires_credits": any(img.ok for img in assets.images.values()),
        }
        report = analyze(
            opts.output,
            preview_dir=(work / "previews") if opts.preview else None,
            max_previews=opts.preview_pages,
            expect=expect,
        )
        previews = [Path(p) for p in report.get("previews", [])]
        warnings.extend(report.get("warnings", []))
    except Exception as exc:
        warnings.append(f"QA failed: {exc}")

    import json
    from .design_qa import build_design_manifest, map_rendered_sections, check_design, text_units
    manifest = build_design_manifest(decision, geometry, section_layouts, assets.layouts, bool(opts.extra_css))
    manifest['cover_pages'] = 1 if cover_html else 0
    skip_pages = set(range(1, manifest['cover_pages'] + 1))
    if include_toc and toc_entries:
        with fitz.open(opts.output) as pdf:
            toc_index = manifest['cover_pages']
            links = pdf[toc_index].get_links() if toc_index < len(pdf) else []
            destinations = [l['page'] + 1 for l in links if l.get('kind') == 1 and l.get('page', -1) > toc_index]
            first_body = min(destinations) if destinations else toc_index + 2
            skip_pages.update(range(toc_index + 1, first_body))
    manifest['skip_pages'] = sorted(skip_pages)
    page_mapping = map_rendered_sections(opts.output, resolved_blocks, section_layouts, skip_pages, geometry.safe_mm)
    for section in manifest['sections']:
        section['pages'] = list(page_mapping.get(section['section_id'], ()))
    manifest['expected_text'] = [unit for b in resolved_blocks for unit in text_units(b.html)]
    manifest['requested'] = {k: doc.meta.get(k) for k in ('theme','composition','art_direction','output_mode') if k in doc.meta}
    manifest['requested_cli'] = {k: getattr(opts,k) for k in ('theme','composition','art_direction','output_mode') if getattr(opts,k)}
    manifest_path = opts.output.with_suffix('.design.json')
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
    design_report = check_design(opts.output, manifest)
    report['design'] = design_report
    report.setdefault('issues', []).extend(design_report['issues'])
    report.setdefault('gates', {})['design_layout'] = design_report['passed']

    return RenderResult(
        pdf_path=opts.output,
        html_path=html_path,
        pages=report.get("pages", total),
        cover_pages=1 if cover_html else 0,
        previews=previews,
        warnings=warnings,
        report=report,
        direction_id=direction.id,
        direction_label=direction.label,
        contrast_report=contrast_report,
        design_manifest=manifest,
    )


def _pt_value(value: str) -> Optional[float]:
    m = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*pt", str(value or ""))
    return float(m.group(1)) if m else None
