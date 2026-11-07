"""Data-visualisation helpers.

Charts are rendered with matplotlib using the active design system's palette
and the document's brand fonts, then embedded as PNG data URIs.  The goal is a
chart that reads like part of the document, not a default matplotlib figure:
horizontal labels when categories are long, direct value labels instead of a
second guess at the axis, and a legend outside the plot area.
"""

from __future__ import annotations

import base64
import io
import math
import re
import textwrap
from pathlib import Path
from typing import List, Optional, Sequence

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    from matplotlib.font_manager import FontProperties, findfont
    from matplotlib.colors import to_rgb
except Exception:  # pragma: no cover
    plt = None
    FontProperties = None  # type: ignore

from .content import ChartRequest
from .tokens import DesignSystem


FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def _wrap_labels(labels: List[str], width: int = 18) -> List[str]:
    """Wrap long category labels so axis text does not collide."""
    out = []
    for label in labels:
        text = str(label)
        out.append(textwrap.fill(text, width) if len(text) > width else text)
    return out


def _palette_colors(ds: DesignSystem) -> List[str]:
    p = ds.palette
    colors = [p.accent, p.accent2, p.ink, p.muted, p.success, p.warning, p.danger]
    seen, out = set(), []
    for c in colors:
        if c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def _font(name: str, size: float):
    """Resolve an effective CSS font stack locally; never fetch web fonts.

    Explicit TTF paths bypass broken family name tables (e.g. Clash Grotesk).
    WOFF2 is not supported by matplotlib: use the next installed family or the
    declared generic serif/sans/mono fallback instead of a fixed brand font.
    """
    if FontProperties is None:
        return None
    size = max(9.0, size)
    families = [family.strip().strip("'\"") for family in name.split(",")]
    generic = {"serif": "DejaVu Serif", "sans-serif": "DejaVu Sans", "monospace": "DejaVu Sans Mono"}
    paths = sorted([*FONT_DIR.glob("*.ttf"), *FONT_DIR.glob("*.otf")])
    for family in families:
        direct = FONT_DIR / family
        if direct.is_file() and direct.suffix.lower() in (".ttf", ".otf"):
            return FontProperties(fname=str(direct), size=size)
        key = re.sub(r"[^a-z0-9]", "", family.casefold())
        for path in paths:
            stem = re.sub(r"[^a-z0-9]", "", path.stem.casefold())
            if stem == key or stem.startswith(key) and stem[len(key):].isdigit():
                return FontProperties(fname=str(path), size=size)
        resolved_family = generic.get(family.casefold(), family)
        try:
            path = findfont(FontProperties(family=[resolved_family]), fallback_to_default=False)
            return FontProperties(fname=path, size=size)
        except ValueError:
            continue
    return FontProperties(family="DejaVu Sans", size=size)


def _label_colour(fill: str) -> str:
    """Choose black/white by WCAG relative-luminance contrast."""
    rgb = to_rgb(fill)
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
    luminance = sum(a * b for a, b in zip(linear, (0.2126, 0.7152, 0.0722)))
    return "#000000" if (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) else "#FFFFFF"


def _fmt(value: float) -> str:
    if abs(value) >= 1000:
        return f"{value:,.0f}"
    if abs(value - round(value)) < 0.05:
        return f"{value:.0f}"
    return f"{value:g}"


def _caption(req: ChartRequest, number: int, kind: str) -> str:
    title = req.title or kind.title()
    num = f'<span class="figure__num">Fig. {number}</span> ' if number else ""
    return (
        f'<figcaption>{num}<span class="figure__caption">{title}</span></figcaption>'
    )


def _fallback(req: ChartRequest, number: int = 0) -> str:
    rows = []
    header = "".join(f"<th>{c}</th>" for c in req.series_names) if req.series_names else ""
    for idx, label in enumerate(req.labels):
        cells = "".join(
            f"<td>{series[idx] if idx < len(series) else ''}</td>" for series in req.series
        )
        rows.append(f"<tr><th>{label}</th>{cells}</tr>")
    return (
        f'<figure class="chart chart--fallback"><table><thead><tr><th></th>{header}</tr></thead>'
        f"<tbody>{''.join(rows)}</tbody></table>{_caption(req, number, 'table')}</figure>"
    )


def make_chart(req: ChartRequest, ds: DesignSystem, number: int = 0,
               width: float = 7.4, height: float = 3.4) -> str:
    """Render at the final layout width/height in inches, never shrink text.

    The returned raster is exactly width*200 by height*200 pixels and declares
    its physical width. Callers must pass the available column width; if geometry
    cannot fit readable labels, a selectable-text table is returned instead.
    """
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0 for v in (width, height)):
        raise ValueError("chart width and height must be positive finite inches")
    if plt is None or not req.labels or not req.series:
        return _fallback(req, number)

    colors = _palette_colors(ds)
    p = ds.palette
    body_font = _font(ds.fonts.body, 9.5)
    small_font = _font(ds.fonts.body, 9.5)
    display_font = _font(ds.fonts.display, 9.5)

    rcParams["axes.edgecolor"] = p.rule
    rcParams["axes.labelcolor"] = p.muted
    rcParams["xtick.color"] = p.muted
    rcParams["ytick.color"] = p.muted
    rcParams["text.color"] = p.ink
    rcParams["figure.facecolor"] = "none"
    rcParams["axes.facecolor"] = "none"

    fig, ax = plt.subplots(figsize=(width, height), dpi=200)
    fig.patch.set_alpha(0)
    ax.set_facecolor("none")

    n = max(1, len(req.labels))
    x = list(range(n))
    kind = (req.kind or "bar").lower()
    labels = [str(label) for label in req.labels]
    multiple = len(req.series) > 1

    # A long category name on a vertical axis forces a neck bend.  Turn the
    # chart on its side so every label reads horizontally.
    if kind in ("bar", "column") and max((len(label) for label in labels), default=0) > 13:
        kind = "hbar"

    label_width = max(10, min(30, int(width * 0.44 * 72 / (9.5 * 0.52))))
    if kind in ("hbar", "horizontal"):
        rows = sum(len(label.splitlines()) for label in _wrap_labels(labels, label_width))
        required_pt = rows * 9.5 * 1.25 + n * 6 + (40 if multiple else 24)
        if required_pt > height * 72 or width < 2.5:
            plt.close(fig)
            return _fallback(req, number)

    try:
        if kind in ("bar", "column"):
            nseries = max(1, len(req.series))
            group_w = 0.8 / nseries
            for si, series in enumerate(req.series):
                offsets = [xi - 0.4 + group_w * (si + 0.5) for xi in x]
                bars = ax.bar(
                    offsets, series, width=group_w * 0.78,
                    color=colors[si % len(colors)],
                    label=req.series_names[si] if si < len(req.series_names) else None,
                    zorder=3,
                )
                for bar, value in zip(bars, series):
                    ax.text(
                        bar.get_x() + bar.get_width() / 2, bar.get_height(),
                        _fmt(value), ha="center", va="bottom",
                        fontproperties=display_font, color=p.ink, zorder=4,
                    )
            ax.set_xticks(x)
            ax.set_xticklabels(_wrap_labels(labels, 13))
        elif kind in ("hbar", "horizontal"):
            nseries = max(1, len(req.series))
            group_h = 0.8 / nseries
            for si, series in enumerate(req.series):
                offsets = [xi - 0.4 + group_h * (si + 0.5) for xi in x]
                bars = ax.barh(
                    offsets, series, height=group_h * 0.78,
                    color=colors[si % len(colors)],
                    label=req.series_names[si] if si < len(req.series_names) else None,
                    zorder=3,
                )
                for bar, value in zip(bars, series):
                    ax.text(
                        bar.get_width(), bar.get_y() + bar.get_height() / 2,
                        "  " + _fmt(value), ha="left", va="center",
                        fontproperties=display_font, color=p.ink, zorder=4,
                    )
            ax.set_yticks(x)
            ax.set_yticklabels(_wrap_labels(labels, label_width))
            ax.invert_yaxis()
        elif kind in ("line", "area"):
            for si, series in enumerate(req.series):
                ax.plot(
                    x, series, color=colors[si % len(colors)], linewidth=3.0,
                    marker="o", markersize=5.5, zorder=3,
                    label=req.series_names[si] if si < len(req.series_names) else None,
                )
                if kind == "area":
                    ax.fill_between(x, series, color=colors[si % len(colors)], alpha=0.14)
                if series:
                    ax.text(
                        x[-1], series[-1], _fmt(series[-1]),
                        ha="left", va="center", fontproperties=display_font,
                        color=colors[si % len(colors)], zorder=4,
                    )
            ax.set_xticks(x)
            ax.set_xticklabels(_wrap_labels(labels, 13))
            ax.margins(x=0.08)
        elif kind in ("stacked", "stackedbar"):
            bottom = [0.0] * n
            for si, series in enumerate(req.series):
                vals = [series[i] if i < len(series) else 0.0 for i in range(n)]
                ax.bar(
                    x, vals, bottom=bottom, width=0.62,
                    color=colors[si % len(colors)], zorder=3,
                    label=req.series_names[si] if si < len(req.series_names) else None,
                )
                for xi, val, base in zip(x, vals, bottom):
                    if val > 0:
                        ax.text(
                            xi, base + val / 2, _fmt(val), ha="center", va="center",
                            fontproperties=small_font, color=_label_colour(colors[si % len(colors)]), zorder=4,
                        )
                bottom = [bottom[i] + vals[i] for i in range(n)]
            ax.set_xticks(x)
            ax.set_xticklabels(_wrap_labels(labels, 13))
        elif kind in ("pie", "donut"):
            series = req.series[0]
            pie_labels = labels[:len(series)]
            wedgeprops = {"width": 0.42} if kind == "donut" else {}
            wedges, category_text, value_text = ax.pie(
                series, labels=_wrap_labels(pie_labels, 16),
                colors=[colors[i % len(colors)] for i in range(len(series))],
                autopct="%1.0f%%", startangle=90,
                wedgeprops=wedgeprops, pctdistance=0.78,
                textprops={"color": p.ink, "fontsize": 9.5},
            )
            for wedge, text in zip(wedges, value_text):
                text.set_color(_label_colour(wedge.get_facecolor()))
            ax.axis("equal")
        else:
            for si, series in enumerate(req.series):
                ax.plot(x, series, color=colors[si % len(colors)], linewidth=2.4, zorder=3)
            ax.set_xticks(x)
            ax.set_xticklabels(_wrap_labels(labels, 13))
    except Exception:
        plt.close(fig)
        return _fallback(req, number)

    # Quiet axes: data gets the contrast, furniture recedes.
    if kind not in ("pie", "donut"):
        if kind in ("hbar", "horizontal"):
            ax.xaxis.grid(True, color=p.rule, linewidth=0.45, alpha=0.45, zorder=0)
        else:
            ax.yaxis.grid(True, color=p.rule, linewidth=0.45, alpha=0.45, zorder=0)
        ax.set_axisbelow(True)
        for spine in ("top", "right", "left", "bottom"):
            ax.spines[spine].set_visible(False)
        ax.tick_params(axis="both", length=0, pad=7)
        if kind in ("hbar", "horizontal"):
            ax.margins(x=0.22, y=0.08)
        else:
            ax.margins(y=0.18)

    # Brand font on every tick and pie label.
    for label in ax.get_xticklabels() + ax.get_yticklabels() + [ax.xaxis.get_offset_text(), ax.yaxis.get_offset_text()]:
        label.set_fontproperties(body_font)
    if kind in ("pie", "donut"):
        for text in ax.texts:
            text.set_fontproperties(small_font)

    # Legend outside the plot so it never covers data.
    if multiple and kind not in ("pie", "donut"):
        legend = ax.legend(
            frameon=False, ncol=min(3, len(req.series)),
            loc="lower left", bbox_to_anchor=(0.0, 1.01),
        )
        for text in legend.get_texts():
            text.set_fontproperties(small_font)

    fig.tight_layout(pad=0.8)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    categories = ax.get_yticklabels() if kind in ("hbar", "horizontal") else ax.get_xticklabels()
    if kind in ("pie", "donut"):
        categories = category_text
    boxes = [label.get_window_extent(renderer) for label in categories if label.get_visible() and label.get_text()]
    overlap = any(box.overlaps(other) for i, box in enumerate(boxes) for other in boxes[i + 1:])
    xlow, xhigh = sorted(ax.get_xlim())
    ylow, yhigh = sorted(ax.get_ylim())
    # Tick Text objects outside view limits exist but matplotlib does not paint
    # them. Only actual in-range labels participate in the canvas bounds gate.
    xticks = [text for text in ax.get_xticklabels() if xlow <= text.get_position()[0] <= xhigh]
    yticks = [text for text in ax.get_yticklabels() if ylow <= text.get_position()[1] <= yhigh]
    text_artists = [*xticks, *yticks, *ax.texts, ax.xaxis.get_offset_text(), ax.yaxis.get_offset_text()]
    if ax.get_legend() is not None:
        text_artists.extend(ax.get_legend().get_texts())
    text_boxes = [text.get_window_extent(renderer) for text in text_artists if text.get_visible() and text.get_text()]
    outside = any(box.x0 < -0.5 or box.y0 < -0.5 or box.x1 > fig.bbox.width + 0.5 or box.y1 > fig.bbox.height + 0.5 for box in text_boxes)
    if overlap or outside:
        plt.close(fig)
        return _fallback(req, number)
    buf = io.BytesIO()
    # Tight bounding boxes change the physical scale when the img fills a
    # column. Preserve the exact requested canvas and 9pt+ final-size labels.
    fig.savefig(buf, format="png", transparent=True)
    plt.close(fig)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    alt = req.title or f"{kind} chart"
    return (
        f'<figure class="chart"><img src="data:image/png;base64,{data}" '
        f'style="width:{width:g}in;max-width:100%;height:auto" '
        f'alt="{alt}" />{_caption(req, number, kind)}</figure>'
    )
