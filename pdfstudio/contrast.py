"""Text/background contrast detection and isolated fixes.

A PDF can look fine at thumbnail size while one caption sits on a busy photo
and becomes unreadable.  This module loads the *print* HTML in Chromium,
finds text that overlaps an image or a strong colour field, measures the
WCAG contrast against the pixels actually behind the glyphs, and returns a
scoped CSS fix for the offending element only.

Display type is reported, not auto-patched: moving a headline is a
composition decision.  Body copy, captions, labels, and credits can be
repaired in isolation with a solid field, which is what `fix_css` does.
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover
    sync_playwright = None


TEXT_SELECTOR = (
    "p,li,h1,h2,h3,h4,h5,h6,td,th,figcaption,blockquote,"
    ".metric__value,.metric__label,.toc__title,.toc__item a,"
    ".cover__title,.cover__subtitle,.cover__summary,.cover__meta-value,"
    ".cover__meta-label,.cover__brand,.cover__stamp,"
    ".callout__body,.callout__title,.swot__title,"
    ".figure__caption,.figure__credit,.chart figcaption"
)

MIN_RATIO = 4.5
MIN_RATIO_LARGE = 3.0
BUSY_STD = 0.105


@dataclass
class ContrastIssue:
    selector: str
    text: str
    kind: str                 # image | colour | busy
    ratio: float
    required: float
    size_pt: float
    weight: int
    display: bool
    busy: float
    severity: str             # error | warning
    fix_css: str = ""
    suggestion: str = ""


@dataclass
class ContrastReport:
    checked: int = 0
    issues: List[ContrastIssue] = field(default_factory=list)
    fix_css: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checked": self.checked,
            "issues": [asdict(i) for i in self.issues],
            "fix_css": self.fix_css,
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _parse_rgb(value: str) -> Optional[Tuple[float, float, float, float]]:
    m = re.search(r"rgba?\(([^)]+)\)", value or "")
    if not m:
        return None
    parts = [p.strip() for p in m.group(1).replace("/", ",").split(",")]
    try:
        r, g, b = (float(parts[0]), float(parts[1]), float(parts[2]))
        a = float(parts[3]) if len(parts) > 3 else 1.0
    except (ValueError, IndexError):
        return None
    return r / 255.0, g / 255.0, b / 255.0, a


def _relative_luminance(rgb: Tuple[float, float, float]) -> float:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(max(0.0, min(1.0, c))) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ratio(l1: float, l2: float) -> float:
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def _blend(fg: Tuple[float, float, float], bg: Tuple[float, float, float],
           alpha: float) -> Tuple[float, float, float]:
    return tuple(fg[i] * alpha + bg[i] * (1.0 - alpha) for i in range(3))


def _hex(rgb: Tuple[float, float, float]) -> str:
    return "#%02X%02X%02X" % tuple(round(max(0.0, min(1.0, c)) * 255) for c in rgb)


def _is_display(tag: str, selector: str, size_pt: float, weight: int) -> bool:
    if tag in ("h1", "h2", "h3") and size_pt >= 20:
        return True
    if any(key in selector for key in ("cover__title", "toc__title", "back-cover h2")):
        return True
    return size_pt >= 28


def _needs_large(size_pt: float, weight: int) -> bool:
    return size_pt >= 18.0 or (size_pt >= 14.0 and weight >= 700)


def _css_string(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _fix_for(issue: ContrastIssue, text_rgb: Tuple[float, float, float],
             bg_rgb: Tuple[float, float, float]) -> Tuple[str, str]:
    """Return (css, suggestion) for one element.

    Non-display text gets a compact solid field that is scoped to the exact
    selector and keeps the original text weight/size.  Display text is left
    alone because the right repair is a composition change.
    """
    if issue.display or "cover" in issue.selector:
        return "", (
            "Display and cover text are art-directed; adjust palette tokens or scrim, "
            "do not inject isolated solid fields onto cover pages."
        )

    # Keep the ink direction: dark text gets a light field and vice versa.
    dark_text = _relative_luminance(text_rgb) < 0.5
    if dark_text:
        bg = "rgba(255,255,255,0.92)"
        fg = _hex(bg_rgb) if _relative_luminance(bg_rgb) < 0.35 else _hex(text_rgb)
        fg = _hex(text_rgb)
    else:
        bg = "rgba(12,12,14,0.78)"
        fg = "#FFFFFF"
    css = (
        f"{issue.selector} {{\n"
        f"  background: {bg} !important;\n"
        f"  color: {fg} !important;\n"
        f"  padding: 0.18em 0.4em !important;\n"
        f"  border-radius: 2px !important;\n"
        f"  -webkit-box-decoration-break: clone;\n"
        f"  box-decoration-break: clone;\n"
        f"}}\n"
    )
    return css, "Isolated solid field applied to this element only."


# ---------------------------------------------------------------------------
# Browser probe
# ---------------------------------------------------------------------------

_JS_COLLECT = r"""
() => {
  const sel = %s;
  const parseAlpha = (c) => {
    const m = (c || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return 0;
    const p = m[1].replace('/', ',').split(',').map(Number);
    return p.length > 3 ? p[3] : 1;
  };
  const cssPath = (el) => {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    while (el && el.nodeType === 1 && el !== document.body) {
      let part = el.tagName.toLowerCase();
      const cls = (el.className || '').toString().split(/\s+/)
        .filter(c => c && !c.startsWith('direction-') && !c.startsWith('theme-') && !c.startsWith('scenario-'));
      if (cls.length) part += '.' + cls.slice(0, 3).map(c => CSS.escape(c)).join('.');
      const parent = el.parentElement;
      if (parent) {
        const sibs = [...parent.children].filter(c => c.tagName === el.tagName);
        if (sibs.length > 1) part += ':nth-of-type(' + (sibs.indexOf(el) + 1) + ')';
      }
      parts.unshift(part);
      el = parent;
    }
    return 'body > ' + parts.join(' > ');
  };
  const out = [];
  let n = 0;
  for (const el of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const text = (el.innerText || '').trim();
    if (!text) continue;
    if (el.querySelector(sel)) continue;
    const rects = [...el.getClientRects()].filter(r => r.width > 5 && r.height > 4);
    if (!rects.length) continue;
    const rr = rects[0];
    let imageBehind = false;
    let bgImageAncestor = false;
    let overlayBg = null;
    for (let p = el; p; p = p.parentElement) {
      if (getComputedStyle(p).backgroundImage !== 'none') { bgImageAncestor = true; break; }
    }
    const points = [
      [rr.left + rr.width * 0.5, rr.top + rr.height * 0.5],
      [rr.left + rr.width * 0.2, rr.top + rr.height * 0.5],
      [rr.left + rr.width * 0.8, rr.top + rr.height * 0.5],
      [rr.left + rr.width * 0.5, rr.top + rr.height * 0.25],
    ];
    for (const [x, y] of points) {
      for (const hit of document.elementsFromPoint(x, y)) {
        if (hit === el || el.contains(hit) || hit.contains(el)) continue;
        const hcs = getComputedStyle(hit);
        if (hit.tagName === 'IMG' || hcs.backgroundImage !== 'none') imageBehind = true;
        if (!overlayBg && parseAlpha(hcs.backgroundColor) > 0.2) overlayBg = hcs.backgroundColor;
      }
    }
    let bgColor = overlayBg;
    if (!bgColor) {
      for (let p = el; p; p = p.parentElement) {
        if (parseAlpha(getComputedStyle(p).backgroundColor) > 0.2) {
          bgColor = getComputedStyle(p).backgroundColor;
          break;
        }
      }
    }
    if (!bgColor) bgColor = getComputedStyle(document.body).backgroundColor || 'rgb(255,255,255)';
    let opacity = 1;
    for (let p = el; p; p = p.parentElement) opacity *= parseFloat(getComputedStyle(p).opacity || '1');
    const id = 'c' + (++n);
    el.setAttribute('data-contrast-id', id);
    out.push({
      id, selector: cssPath(el), tag: el.tagName.toLowerCase(),
      text: text.slice(0, 140), color: cs.color, opacity,
      size: parseFloat(cs.fontSize), weight: parseInt(cs.fontWeight) || 400,
      rect: {x: rr.left, y: rr.top, w: rr.width, h: rr.height},
      image: imageBehind || bgImageAncestor, bg: bgColor,
    });
  }
  return out;
}
""" % repr(TEXT_SELECTOR)


def _browser_probe(html: str, base_dir: Path) -> Tuple[List[Dict[str, Any]], List[bytes], str]:
    if sync_playwright is None:
        return [], [], "Playwright is not installed"
    if Image is None:
        return [], [], "Pillow is not installed"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--font-render-hinting=none", "--no-sandbox"])
        page = browser.new_page(viewport={"width": 1400, "height": 1800},
                                device_scale_factor=1)
        page.set_content(html, wait_until="load")
        page.emulate_media(media="print")
        try:
            page.evaluate("() => document.fonts.ready.then(() => true)")
        except Exception:
            pass
        page.wait_for_timeout(180)
        items = page.evaluate(_JS_COLLECT)
        if not items:
            browser.close()
            return [], [], ""

        # Hide glyphs, keep every background and photograph in place.
        page.add_style_tag(content=(
            "* { color: transparent !important; "
            "-webkit-text-fill-color: transparent !important; "
            "text-shadow: none !important; text-decoration-color: transparent !important; "
            "caret-color: transparent !important; }"
        ))
        page.wait_for_timeout(60)
        shots: List[bytes] = []
        for item in items:
            r = item["rect"]
            clip = {
                "x": max(0.0, r["x"]),
                "y": max(0.0, r["y"]),
                "width": max(1.0, r["w"]),
                "height": max(1.0, r["h"]),
            }
            try:
                shot = page.screenshot(clip=clip, animations="disabled", caret="hide")
            except Exception:
                shot = b""
            shots.append(shot)
        browser.close()
    return items, shots, ""


def _pixel_stats(raw: bytes) -> Optional[Dict[str, float]]:
    if not raw or Image is None:
        return None
    try:
        im = Image.open(io.BytesIO(raw)).convert("RGB")
    except Exception:
        return None
    # Downsample large regions; contrast is about the field, not every pixel.
    if im.width > 220:
        ratio = 220 / im.width
        im = im.resize((220, max(1, int(im.height * ratio))), Image.LANCZOS)
    pixels = list(im.getdata())
    if not pixels:
        return None
    lums = sorted(
        0.2126 * (r / 255.0) + 0.7152 * (g / 255.0) + 0.0722 * (b / 255.0)
        for r, g, b in pixels
    )
    n = len(lums)
    mean = sum(lums) / n
    p10 = lums[int(n * 0.10)]
    p50 = lums[int(n * 0.50)]
    p90 = lums[int(n * 0.90)]
    var = sum((x - mean) ** 2 for x in lums) / n
    return {"mean": mean, "p10": p10, "p50": p50, "p90": p90,
            "std": math.sqrt(var)}


def probe_html(html: str, base_dir: Optional[Path] = None,
               apply_fix: bool = True) -> ContrastReport:
    """Measure text contrast against the pixels behind it.

    Returns a report with issues and a scoped `fix_css` for non-display text.
    The caller appends `fix_css` to the document CSS and re-renders.
    """
    report = ContrastReport()
    if sync_playwright is None:
        report.error = "Playwright is not installed; contrast probe skipped."
        return report

    items, shots, error = _browser_probe(html, base_dir or Path.cwd())
    if error:
        report.error = error
        return report
    report.checked = len(items)

    fixes: List[str] = []
    for item, shot in zip(items, shots):
        color = _parse_rgb(item.get("color", ""))
        if not color:
            continue
        text_rgb = color[:3]
        alpha = color[3] * float(item.get("opacity") or 1.0)
        size_pt = float(item.get("size") or 12.0) * 72.0 / 96.0
        weight = int(item.get("weight") or 400)
        required = MIN_RATIO_LARGE if _needs_large(size_pt, weight) else MIN_RATIO

        stats = _pixel_stats(shot) if (item.get("image") and shot) else None
        if stats is None:
            bg = _parse_rgb(item.get("bg", "")) or (1.0, 1.0, 1.0, 1.0)
            bg_rgb = bg[:3]
            # CSS backgrounds may include alpha; blend over the paper.
            if bg[3] < 1.0:
                bg_rgb = _blend(bg_rgb, (1.0, 1.0, 1.0), bg[3])
            stats = {"mean": _relative_luminance(bg_rgb),
                     "p10": _relative_luminance(bg_rgb),
                     "p50": _relative_luminance(bg_rgb),
                     "p90": _relative_luminance(bg_rgb),
                     "std": 0.0}
            kind = "colour"
        else:
            kind = "image"

        mean_bg = stats["p50"]
        eff = _blend(text_rgb, (mean_bg, mean_bg, mean_bg), alpha)
        text_l = _relative_luminance(eff)
        ratios = [_ratio(text_l, stats[k]) for k in ("p10", "p50", "p90")]
        worst = min(ratios)
        busy = stats["std"]

        bad_ratio = worst < required
        bad_busy = kind == "image" and busy >= BUSY_STD and item.get("tag") in (
            "p", "figcaption", "li", "td", "th", "blockquote",
        )
        if not bad_ratio and not bad_busy:
            continue

        display = _is_display(item.get("tag", ""), item.get("selector", ""),
                              size_pt, weight)
        issue = ContrastIssue(
            selector=item.get("selector", ""),
            text=str(item.get("text", "")).strip()[:120],
            kind="busy" if (bad_busy and not bad_ratio) else kind,
            ratio=round(worst, 2),
            required=required,
            size_pt=round(size_pt, 1),
            weight=weight,
            display=display,
            busy=round(busy, 3),
            severity="error" if bad_ratio else "warning",
        )
        if apply_fix and (bad_ratio or bad_busy):
            bg_for_fix = (stats["p50"], stats["p50"], stats["p50"])
            issue.fix_css, issue.suggestion = _fix_for(issue, text_rgb, bg_for_fix)
            if issue.fix_css:
                fixes.append(issue.fix_css)
        elif bad_ratio:
            issue.suggestion = _fix_for(issue, text_rgb,
                                        (stats["p50"],) * 3)[1]
        report.issues.append(issue)

    report.fix_css = "\n".join(fixes)
    return report


def format_report(report: ContrastReport) -> str:
    if report.error:
        return f"[SKIP] {report.error}"
    if not report.issues:
        return f"[OK] Contrast: {report.checked} text elements checked, no clashes."
    lines = [f"[CHECK] Contrast: {report.checked} elements checked, "
             f"{len(report.issues)} issue(s), {report.fix_css.count('{')} auto-fix(es)."]
    for issue in report.issues:
        label = "DISPLAY" if issue.display else "TEXT"
        fix = "fixed" if issue.fix_css else "manual"
        lines.append(
            f"  {issue.severity.upper():7} {label:7} {issue.ratio:4.1f}:1 "
            f"(needs {issue.required:3.1f}) {issue.kind:6} {issue.selector}  "
            f"[{issue.text[:56]}] -> {fix}"
        )
    return "\n".join(lines)
