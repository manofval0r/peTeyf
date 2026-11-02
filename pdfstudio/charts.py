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
import textwrap
from pathlib import Path
from typing import List, Optional, Sequence

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import rcParams
    from matplotlib.font_manager import FontProperties
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
    """Load a bundled TTF explicitly.

    The Clash Grotesk 400 name table reports the family as "false", so asking
    matplotlib for the family name is unreliable.  An explicit file path works
    for every bundled font.
    """
    if FontProperties is None:
        return None
    path = FONT_DIR / name
    if path.exists():
        return FontProperties(fname=str(path), size=size)
    return FontProperties(family="DejaVu Sans", size=size)


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
    if plt is None or not req.labels or not req.series:
        return _fallback(req, number)

    colors = _palette_colors(ds)
    p = ds.palette
    body_font = _font("Manrope.ttf", 9.5)
    small_font = _font("Manrope.ttf", 8.0)
    display_font = _font("clash-grotesk-500.ttf", 9.5)

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
            ax.set_yticklabels(_wrap_labels(labels, 30))
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
                            fontproperties=small_font, color="#FFFFFF", zorder=4,
                        )
                bottom = [bottom[i] + vals[i] for i in range(n)]
            ax.set_xticks(x)
            ax.set_xticklabels(_wrap_labels(labels, 13))
        elif kind in ("pie", "donut"):
            series = req.series[0]
            pie_labels = labels[:len(series)]
            wedgeprops = {"width": 0.42} if kind == "donut" else {}
            ax.pie(
                series, labels=_wrap_labels(pie_labels, 16),
                colors=colors[:len(series)], autopct="%1.0f%%", startangle=90,
                wedgeprops=wedgeprops, pctdistance=0.78,
                textprops={"color": p.ink, "fontsize": 9},
            )
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

    # Brand font on every tick and pie label.
    for label in ax.get_xticklabels() + ax.get_yticklabels():
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

    fig.tight_layout(pad=0.6)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", transparent=True, bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    alt = req.title or f"{kind} chart"
    return (
        f'<figure class="chart"><img src="data:image/png;base64,{data}" '
        f'alt="{alt}" />{_caption(req, number, kind)}</figure>'
    )
