"""Measurable quality assurance for generated PDFs.

`analyze()` opens the finished PDF and checks the things that make a document
feel designed rather than dumped:

* real type sizes (the declared body size, and a hard floor for every label)
* line measure (characters per line in body paragraphs)
* text clipped by the page edge, and content that overflows the page
* headings stranded at the foot of a page
* pages that are suspiciously empty
* metadata, document language, tagging, and the outline
* image resolution, displayed size, and accidental duplicates
* an image-credit block when photographs are present

It also renders page previews to PNG so the agent can *look* at the result.
Every finding is a structured issue, so the CLI can fail strictly and a caller
can fix one element at a time instead of guessing.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence, Tuple

try:
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None


# Pages we consider suspiciously empty if they carry less than this much text.
MIN_CHARS = 40
MIN_WORDS = 60

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "page"


def _issue(code: str, severity: str, message: str,
           page: Optional[int] = None, **extra: Any) -> Dict[str, Any]:
    item: Dict[str, Any] = {"code": code, "severity": severity, "message": message}
    if page is not None:
        item["page"] = page
    item.update(extra)
    return item


def _words(text: str) -> int:
    return len(re.findall(r"[^\s]+", text or ""))


def _round(value: float, digits: int = 1) -> float:
    return round(float(value), digits)


def _dominant_size(spans: Sequence[Dict[str, Any]]) -> float:
    """Character-weighted dominant font size in a set of spans."""
    weights: Dict[float, int] = {}
    for span in spans:
        text = str(span.get("text") or "")
        count = len(text.strip())
        if not count:
            continue
        size = round(float(span.get("size") or 0.0), 1)
        if size <= 0:
            continue
        weights[size] = weights.get(size, 0) + count
    if not weights:
        return 0.0
    return max(weights.items(), key=lambda kv: kv[1])[0]


def _page_spans(page: "fitz.Page") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    try:
        data = page.get_text("dict")
    except Exception:
        return out
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text") or "")
                if not text.strip():
                    continue
                out.append({
                    "text": text,
                    "size": float(span.get("size") or 0.0),
                    "font": str(span.get("font") or ""),
                    "bbox": tuple(span.get("bbox") or (0, 0, 0, 0)),
                })
    return out


def _lines(page: "fitz.Page") -> List[Dict[str, Any]]:
    """Reconstruct visual lines with their dominant size and text."""
    out: List[Dict[str, Any]] = []
    try:
        data = page.get_text("dict")
    except Exception:
        return out
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = [
                span for span in line.get("spans", [])
                if str(span.get("text") or "").strip()
            ]
            if not spans:
                continue
            text = "".join(str(span.get("text") or "") for span in spans).strip()
            bbox = line.get("bbox") or (0, 0, 0, 0)
            out.append({
                "text": text,
                "size": _dominant_size(spans),
                "bbox": tuple(bbox),
                "chars": len(re.sub(r"\s+", " ", text)),
            })
    return out


def _image_inventory(doc: "fitz.Document") -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (image entries, duplicate pairs).

    Resolution is measured as effective DPI: pixel width divided by the
    displayed width in inches.  A 3000px photograph displayed at 40mm is
    sharp; the same photograph displayed across a full page may not be.
    """
    entries: List[Dict[str, Any]] = []
    by_hash: Dict[str, List[Dict[str, Any]]] = {}
    seen_xref: Dict[int, Dict[str, Any]] = {}

    for page_index, page in enumerate(doc):
        try:
            images = page.get_images(full=True)
        except Exception:
            continue
        for item in images:
            xref = int(item[0])
            if xref in seen_xref:
                seen_xref[xref].setdefault("pages", []).append(page_index + 1)
                continue
            width = int(item[2] or 0)
            height = int(item[3] or 0)
            try:
                rects = page.get_image_rects(xref)
            except Exception:
                rects = []
            rect = rects[0] if rects else None
            displayed_w_mm = (rect.width / 72.0 * 25.4) if rect else 0.0
            displayed_h_mm = (rect.height / 72.0 * 25.4) if rect else 0.0
            dpi_x = (width / (rect.width / 72.0)) if rect and rect.width else 0.0
            dpi_y = (height / (rect.height / 72.0)) if rect and rect.height else 0.0
            effective_dpi = min(dpi_x, dpi_y) if dpi_x and dpi_y else 0.0

            digest = ""
            try:
                raw = doc.extract_image(xref)
                digest = hashlib.md5(raw.get("image", b"")).hexdigest()
            except Exception:
                digest = ""

            entry = {
                "xref": xref,
                "page": page_index + 1,
                "pages": [page_index + 1],
                "width_px": width,
                "height_px": height,
                "displayed_mm": (_round(displayed_w_mm), _round(displayed_h_mm)),
                "effective_dpi": _round(effective_dpi),
                "hash": digest,
            }
            entries.append(entry)
            seen_xref[xref] = entry
            if digest:
                by_hash.setdefault(digest, []).append(entry)

    duplicates: List[Dict[str, Any]] = []
    for digest, group in by_hash.items():
        if len(group) < 2:
            continue
        duplicates.append({
            "hash": digest,
            "pages": sorted({page for entry in group for page in entry.get("pages", [])}),
            "count": len(group),
        })
    return entries, duplicates


def _structure(doc: "fitz.Document") -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "has_lang": False,
        "lang": "",
        "struct_tree": False,
        "marked": False,
        "marked_suspects": False,
        "page_mode": "",
        "outline_entries": 0,
    }
    try:
        catalog = doc.pdf_catalog()
    except Exception:
        catalog = 0
    if catalog:
        try:
            kind, value = doc.xref_get_key(catalog, "Lang")
            if kind not in ("null", "none") and value:
                info["has_lang"] = True
                info["lang"] = value.strip("()")
        except Exception:
            pass
        for key, flag in (("StructTreeRoot", "struct_tree"), ("MarkInfo", "marked")):
            try:
                kind, value = doc.xref_get_key(catalog, key)
                if kind not in ("null", "none"):
                    info[flag] = True
                    if key == "MarkInfo" and "Suspects true" in value:
                        info["marked_suspects"] = True
            except Exception:
                pass
        try:
            kind, value = doc.xref_get_key(catalog, "PageMode")
            info["page_mode"] = value if kind not in ("null", "none") else ""
        except Exception:
            pass
    try:
        info["outline_entries"] = len(doc.get_toc() or [])
    except Exception:
        pass
    return info


def analyze(
    pdf_path: str | Path,
    preview_dir: Optional[str | Path] = None,
    max_previews: int = 6,
    preview_dpi: int = 110,
    expect: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Inspect a PDF and optionally render PNG previews.

    ``expect`` carries the design intent measured from the source:
    ``body_size_pt``, ``min_font_pt``, ``measure_ch``, ``margins_mm``,
    ``cover_pages``, and ``toc_pages``.

    Returns a report with legacy keys (pages, text_chars, images, warnings,
    previews, per_page) plus ``issues``, ``gates``, ``fonts``, ``structure``,
    and ``image_details``.  ``warnings`` is the human-readable summary of every
    error and warning, so existing callers keep working.
    """
    expect = expect or {}
    pdf_path = Path(pdf_path)
    report: Dict[str, Any] = {
        "path": str(pdf_path),
        "pages": 0,
        "size_bytes": pdf_path.stat().st_size if pdf_path.exists() else 0,
        "text_chars": 0,
        "images": 0,
        "empty_pages": [],
        "has_text_layer": False,
        "page_sizes": [],
        "previews": [],
        "warnings": [],
        "issues": [],
        "per_page": [],
        "fonts": {},
        "structure": {},
        "image_details": [],
        "duplicate_images": [],
        "gates": {},
    }
    if not pdf_path.exists():
        report["warnings"].append(f"PDF not found: {pdf_path}")
        report["issues"].append(_issue("missing", "error", f"PDF not found: {pdf_path}"))
        return report

    if fitz is None:
        report["warnings"].append(
            "PyMuPDF (fitz) is not installed; skipping structural QA."
        )
        report["issues"].append(_issue(
            "no_pymupdf", "error", "PyMuPDF is not installed; structural QA cannot run."
        ))
        return report

    cover_pages = int(expect.get("cover_pages", 1) or 0)
    min_font = float(expect.get("min_font_pt", 9.0) or 9.0)
    body_expect = float(expect.get("body_size_pt", 0) or 0)
    measure_expect = float(expect.get("measure_ch", 0) or 0)
    margins = expect.get("margins_mm") or (20.0, 18.0, 22.0, 18.0)
    try:
        margin_top, margin_right, margin_bottom, margin_left = [float(v) for v in margins]
    except Exception:
        margin_top, margin_right, margin_bottom, margin_left = 20.0, 18.0, 22.0, 18.0

    doc = fitz.open(str(pdf_path))
    report["pages"] = doc.page_count
    report["meta"] = dict(doc.metadata or {})
    report["structure"] = _structure(doc)

    out_dir = Path(preview_dir) if preview_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    total_chars = 0
    body_chars = 0
    body_sizes: List[float] = []
    line_lengths: List[int] = []
    size_counts: Dict[float, int] = {}
    size_fonts: Dict[float, set] = {}
    size_samples: Dict[float, List[Tuple[int, str]]] = {}
    issue_pages: List[Dict[str, Any]] = []

    for index, page in enumerate(doc):
        text = page.get_text() or ""
        chars = len(re.sub(r"\s+", "", text))
        words = _words(text)
        total_chars += chars
        try:
            image_count = len(page.get_images(full=True))
        except Exception:
            image_count = 0
        rect = page.rect
        size = (round(rect.width, 1), round(rect.height, 1))

        spans = _page_spans(page)
        lines = _lines(page)
        dominant = _dominant_size(spans)
        page_issues: List[Dict[str, Any]] = []

        # ---- type sizes ------------------------------------------------
        samples: List[Tuple[int, str]] = []
        for span in spans:
            size_pt = round(float(span["size"]), 1)
            if size_pt <= 0:
                continue
            size_counts[size_pt] = size_counts.get(size_pt, 0) + len(span["text"].strip())
            size_fonts.setdefault(size_pt, set()).add(span["font"])
            bucket = size_samples.setdefault(size_pt, [])
            if len(bucket) < 4:
                bucket.append((index + 1, span["text"].strip()[:60]))
            if size_pt < min_font - 0.25 and len(span["text"].strip()) > 2:
                samples.append((index + 1, span["text"].strip()[:50]))

        if samples:
            sizes = sorted({round(float(s), 1) for s in
                            (span["size"] for span in spans
                             if float(span["size"]) < min_font - 0.25)})
            page_issues.append(_issue(
                "font_floor", "error",
                f"Text below {min_font:g}pt on page {index + 1} "
                f"(sizes: {', '.join(f'{s:g}' for s in sizes)}; "
                f"e.g. '{samples[0][1]}').",
                page=index + 1, sizes=sizes,
            ))

        # ---- measure: body lines only ----------------------------------
        if index >= cover_pages and dominant > 0:
            for line in lines:
                if abs(line["size"] - dominant) <= 1.0 and line["chars"] >= 32:
                    line_lengths.append(line["chars"])

        # ---- edge clipping / overflow ----------------------------------
        if index >= cover_pages:
            for span in spans:
                x0, y0, x1, y1 = span["bbox"]
                label = span["text"].strip()[:40]
                if len(label) < 4:
                    continue
                if x1 > rect.width - 0.3 or x0 < 0.3:
                    page_issues.append(_issue(
                        "edge_clip", "error",
                        f"Text touches the page edge on page {index + 1}: '{label}'.",
                        page=index + 1,
                    ))
                    break
                if y1 > rect.height - 0.3 or y0 < 0.3:
                    page_issues.append(_issue(
                        "edge_clip", "error",
                        f"Text touches the page edge on page {index + 1}: '{label}'.",
                        page=index + 1,
                    ))
                    break

        # ---- heading stranded at the foot of a page --------------------
        if index >= cover_pages and lines:
            heading_lines = [line for line in lines if line["size"] >= dominant + 4.0]
            if heading_lines:
                last = max(heading_lines, key=lambda line: line["bbox"][3])
                after = [
                    line for line in lines
                    if line["bbox"][1] >= last["bbox"][3] - 0.5
                    and abs(line["size"] - dominant) <= 1.0
                ]
                after_words = sum(_words(line["text"]) for line in after)
                if last["bbox"][3] > page.rect.height * 0.74 and after_words < 25:
                    page_issues.append(_issue(
                        "heading_orphan", "warning",
                        f"Heading '{last['text'][:50]}' is stranded at the "
                        f"bottom of page {index + 1}.",
                        page=index + 1,
                    ))

        # ---- page fill -------------------------------------------------
        content_bbox = None
        if spans:
            xs0 = min(span["bbox"][0] for span in spans)
            ys0 = min(span["bbox"][1] for span in spans)
            xs1 = max(span["bbox"][2] for span in spans)
            ys1 = max(span["bbox"][3] for span in spans)
            content_bbox = (round(xs0, 1), round(ys0, 1), round(xs1, 1), round(ys1, 1))
        inner_h = max(1.0, rect.height - (margin_top + margin_bottom) / 25.4 * 72.0)
        fill = 0.0
        if spans:
            fill = max(0.0, (ys1 - ys0) / inner_h)

        entry = {
            "page": index + 1,
            "chars": chars,
            "words": words,
            "images": image_count,
            "size": size,
            "dominant_pt": dominant,
            "fill": _round(fill, 2),
            "content_bbox": content_bbox,
            "issues": [issue["code"] for issue in page_issues],
        }
        report["per_page"].append(entry)
        issue_pages.append(entry)
        if index == 0:
            report["page_sizes"].append(size)

        if chars < MIN_CHARS and image_count == 0 and index > 0:
            report["empty_pages"].append(index + 1)
            page_issues.append(_issue(
                "empty_page", "error",
                f"Page {index + 1} has almost no text and no image.",
                page=index + 1,
            ))

        if index >= cover_pages and index + 1 < doc.page_count:
            if words < MIN_WORDS and words > 0 and fill < 0.46 and image_count == 0:
                page_issues.append(_issue(
                    "sparse_page", "warning",
                    f"Page {index + 1} is only {int(fill * 100)}% full "
                    f"({words} words). It reads as a spill page.",
                    page=index + 1,
                ))

        if index >= cover_pages and chars > 0:
            body_chars += chars
            body_sizes.append(dominant)

        report["issues"].extend(page_issues)

        if out_dir and index < max_previews:
            png = out_dir / f"{index + 1:02d}-{_slug(pdf_path.stem)}.png"
            try:
                pix = page.get_pixmap(dpi=preview_dpi, alpha=False)
                pix.save(str(png))
                report["previews"].append(str(png))
            except Exception as exc:  # pragma: no cover
                report["warnings"].append(f"preview failed on page {index + 1}: {exc}")

    # ---- images -------------------------------------------------------
    image_entries, duplicates = _image_inventory(doc)
    report["image_details"] = image_entries
    report["duplicate_images"] = duplicates
    report["images"] = len({entry["xref"] for entry in image_entries})

    for entry in image_entries:
        dpi = entry.get("effective_dpi") or 0
        if dpi and dpi < 150 and entry.get("width_px", 0) >= 200:
            report["issues"].append(_issue(
                "image_dpi", "warning",
                f"Image on page {entry['page']} resolves to {dpi:g} dpi "
                f"at {entry['displayed_mm'][0]:g}x{entry['displayed_mm'][1]:g}mm "
                f"(target 150+).",
                page=entry["page"], dpi=dpi,
            ))
        if entry.get("width_px", 0) and entry["width_px"] < 500:
            report["issues"].append(_issue(
                "image_small", "warning",
                f"Image on page {entry['page']} is only "
                f"{entry['width_px']}x{entry['height_px']}px.",
                page=entry["page"],
            ))

    for duplicate in duplicates:
        report["issues"].append(_issue(
            "duplicate_image", "warning",
            f"The same image appears {duplicate['count']} times "
            f"(pages {', '.join(str(p) for p in duplicate['pages'])}).",
            pages=duplicate["pages"],
        ))

    # ---- credits ------------------------------------------------------
    all_text = " ".join((page.get_text() or "") for page in doc)
    has_credits = bool(re.search(r"\b(image credits|photo credits|credits)\b", all_text, re.I))
    if image_entries and not has_credits:
        report["issues"].append(_issue(
            "missing_credits", "error",
            "Images are present but there is no credits block.",
        ))

    # ---- metadata and accessibility ----------------------------------
    meta = report["meta"]
    for key, label, severity in (
        ("title", "title", "error"),
        ("author", "author", "error"),
        ("subject", "subject", "warning"),
        ("keywords", "keywords", "warning"),
    ):
        if not str(meta.get(key) or "").strip():
            report["issues"].append(_issue(
                "metadata", severity, f"PDF metadata is missing the {label}."
            ))
    structure = report["structure"]
    if not structure.get("has_lang"):
        report["issues"].append(_issue(
            "no_lang", "error", "The PDF catalog has no /Lang value."
        ))
    if not structure.get("struct_tree"):
        report["issues"].append(_issue(
            "no_tags", "error", "The PDF has no structure tree (not tagged)."
        ))
    if not structure.get("marked"):
        report["issues"].append(_issue(
            "not_marked", "warning", "The PDF catalog has no /MarkInfo dictionary."
        ))
    if structure.get("outline_entries", 0) < 2:
        report["issues"].append(_issue(
            "no_outline", "warning", "The PDF outline is empty or has one entry."
        ))
    if structure.get("page_mode") and structure["page_mode"] != "/UseOutlines":
        report["issues"].append(_issue(
            "page_mode", "info",
            f"PageMode is {structure['page_mode']}, not /UseOutlines.",
        ))

    doc.close()

    # ---- type scale summary ------------------------------------------
    report["fonts"] = {
        "sizes": [
            {
                "pt": size,
                "chars": count,
                "fonts": sorted(font for font in size_fonts.get(size, set()) if font),
                "samples": size_samples.get(size, []),
            }
            for size, count in sorted(size_counts.items(), reverse=True)
        ],
        "body_pt": _round(median(body_sizes), 2) if body_sizes else 0.0,
        "min_used_pt": _round(min(size_counts), 1) if size_counts else 0.0,
        "line_chars": _round(median(line_lengths), 1) if line_lengths else 0.0,
    }

    body_pt = report["fonts"]["body_pt"]
    min_used = report["fonts"]["min_used_pt"]
    line_chars = report["fonts"]["line_chars"]

    if body_expect and body_pt and abs(body_pt - body_expect) > 0.6:
        report["issues"].append(_issue(
            "body_size", "error",
            f"Body text measures {body_pt:g}pt; the design declares "
            f"{body_expect:g}pt. Chromium may be scaling the document.",
            measured=body_pt, expected=body_expect,
        ))
    if min_used and min_used < min_font - 0.25:
        report["issues"].append(_issue(
            "min_font", "error",
            f"Smallest text is {min_used:g}pt; the floor is {min_font:g}pt.",
            measured=min_used, expected=min_font,
        ))
    if measure_expect and line_chars:
        low = max(34.0, measure_expect - 24.0)
        high = measure_expect + 24.0
        if line_chars < low or line_chars > high:
            report["issues"].append(_issue(
                "measure", "warning",
                f"Body lines average {line_chars:g} characters; the target "
                f"measure is {measure_expect:g}ch ({low:g}-{high:g}).",
                measured=line_chars, expected=measure_expect,
            ))

    # ---- legacy summary + warnings -----------------------------------
    report["text_chars"] = total_chars
    report["body_text_chars"] = body_chars
    report["has_text_layer"] = total_chars > 200
    report["average_body_chars"] = (
        round(body_chars / max(1, len(report["per_page"]) - cover_pages))
        if report["per_page"] else 0
    )
    if report["page_sizes"]:
        w, h = report["page_sizes"][0]
        report["orientation"] = "landscape" if w > h else "portrait"

    if not report["has_text_layer"]:
        report["issues"].append(_issue(
            "no_text", "error",
            "Very little extractable text: the PDF may be image-only or a font failed.",
        ))
    if report["empty_pages"]:
        pages = ", ".join(str(p) for p in report["empty_pages"][:8])
        report["issues"].append(_issue(
            "empty_pages", "error", f"Possibly empty pages: {pages}."
        ))
    if report["pages"] > 2 and report["images"] == 0 and body_chars < 400:
        report["issues"].append(_issue(
            "sparse_document", "error",
            "Sparse document: no images and little text. Check the source content.",
        ))

    report["gates"] = _gate_summary(report, cover_pages)
    report["issues"].sort(key=lambda item: (
        SEVERITY_ORDER.get(item.get("severity", "info"), 3),
        item.get("page") or 0,
        item.get("code", ""),
    ))
    report["warnings"] = [
        f"{issue['severity'].upper()}: {issue['message']}"
        for issue in report["issues"]
        if issue.get("severity") in ("error", "warning")
    ]
    return report


def _gate_summary(report: Dict[str, Any], cover_pages: int) -> Dict[str, bool]:
    """Boolean view of the measurable gates, for quick JSON consumption."""
    issues = report.get("issues", [])
    codes = {issue.get("code") for issue in issues if issue.get("severity") == "error"}
    warn_codes = {issue.get("code") for issue in issues if issue.get("severity") == "warning"}
    return {
        "type_floor": not ({"font_floor", "min_font", "body_size"} & codes),
        "measure": "measure" not in warn_codes,
        "no_clipping": "edge_clip" not in codes,
        "no_orphan_headings": "heading_orphan" not in warn_codes,
        "page_fill": not ({"empty_page", "sparse_document"} & codes),
        "metadata": "metadata" not in codes,
        "language": "no_lang" not in codes,
        "tagged": "no_tags" not in codes,
        "outline": "no_outline" not in warn_codes,
        "image_resolution": "image_dpi" not in warn_codes,
        "no_duplicate_images": "duplicate_image" not in warn_codes,
        "credits": "missing_credits" not in codes,
    }


def has_errors(report: Dict[str, Any]) -> bool:
    return any(issue.get("severity") == "error" for issue in report.get("issues", []))


def format_report(report: Dict[str, Any]) -> str:
    """Human-readable, one-screen summary with the failing gates named."""
    lines: List[str] = []
    errors = [i for i in report.get("issues", []) if i.get("severity") == "error"]
    warnings = [i for i in report.get("issues", []) if i.get("severity") == "warning"]
    status = "OK" if not errors and not warnings else ("FAIL" if errors else "CHECK")
    lines.append(
        f"[{status}] {report.get('pages', 0)} pages | "
        f"{report.get('text_chars', 0):,} chars | "
        f"{report.get('images', 0)} images | "
        f"{report.get('size_bytes', 0) / 1024:.0f} KB"
    )
    if report.get("page_sizes"):
        w, h = report["page_sizes"][0]
        lines.append(
            f"Page size: {w} x {h} pt ({report.get('orientation', '')})"
        )
    fonts = report.get("fonts") or {}
    if fonts:
        lines.append(
            f"Type: body {fonts.get('body_pt', 0):g}pt | "
            f"smallest {fonts.get('min_used_pt', 0):g}pt | "
            f"measure {fonts.get('line_chars', 0):g} chars/line"
        )
    structure = report.get("structure") or {}
    if structure:
        lines.append(
            "Metadata: "
            f"lang={structure.get('lang') or 'missing'} | "
            f"tags={'yes' if structure.get('struct_tree') else 'no'} | "
            f"outline={structure.get('outline_entries', 0)}"
        )
    gates = report.get("gates") or {}
    failed = [name for name, ok in gates.items() if not ok]
    if gates:
        lines.append(
            "Gates: " + ("all pass" if not failed else "fail: " + ", ".join(failed))
        )
    if report.get("previews"):
        lines.append(f"Previews: {len(report['previews'])} PNG(s)")
    for issue in errors[:12]:
        lines.append(f"  x {issue['message']}")
    for issue in warnings[:8]:
        lines.append(f"  ! {issue['message']}")
    if len(errors) > 12:
        lines.append(f"  ... {len(errors) - 12} more errors")
    return "\n".join(lines)
