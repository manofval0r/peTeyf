"""Topic-aware art direction for PDF Studio.

Themes are broad visual systems.  Art directions are the stronger editorial
decision: how the subject behaves on the page, which type voice it uses, and
which compositional device carries the document.  A direction can be selected
explicitly in frontmatter or inferred from the document's subject.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import re
from typing import Dict, Iterable, Tuple

from .tokens import DesignSystem, FontPair, Palette


@dataclass(frozen=True)
class ArtDirection:
    id: str
    label: str
    concept: str
    tone: str
    fonts: FontPair
    palette: Palette
    cover_style: str
    radius: str
    heading_weight: str
    display_weight: str
    letter_spacing: str
    body_size: str
    line_height: str
    measure: str = "72ch"
    keywords: Tuple[str, ...] = ()
    scenarios: Tuple[str, ...] = ()

    def css_vars(self) -> str:
        p = self.palette
        return "\n".join([
            f"--bg: {p.bg};",
            f"--ink: {p.ink};",
            f"--muted: {p.muted};",
            f"--accent: {p.accent};",
            f"--accent-ink: {p.accent_ink};",
            f"--accent-2: {p.accent2};",
            f"--rule: {p.rule};",
            f"--panel: {p.panel};",
            f"--panel-ink: {p.panel_ink};",
            f"--success: {p.success};",
            f"--warning: {p.warning};",
            f"--danger: {p.danger};",
            f"--cover-bg: {p.cover_bg or p.bg};",
            f"--cover-ink: {p.cover_ink or p.ink};",
            f"--font-display: {self.fonts.display};",
            f"--font-body: {self.fonts.body};",
            f"--radius: {self.radius};",
            f"--heading-weight: {self.heading_weight};",
            f"--display-weight: {self.display_weight};",
            f"--letter-spacing: {self.letter_spacing};",
            f"--body-size: {self.body_size};",
            f"--line-height: {self.line_height};",
            f"--measure: {self.measure};",
        ])


CLASH = FontPair(
    display="'Clash Grotesk', 'Arial Black', sans-serif",
    body="'Clash Grotesk', 'Segoe UI', sans-serif",
    mono="'Clash Grotesk', 'Segoe UI', sans-serif",
)
FRAUNCES_SERIF = FontPair(
    display="'Fraunces', Georgia, serif",
    body="'Source Serif 4', Georgia, serif",
    mono="'Source Serif 4', Georgia, serif",
)
FRAUNCES_SANS = FontPair(
    display="'Fraunces', Georgia, serif",
    body="'Manrope', 'Segoe UI', sans-serif",
    mono="'Manrope', 'Segoe UI', sans-serif",
)
SPACE = FontPair(
    display="'Space Grotesk', 'Segoe UI', sans-serif",
    body="'Manrope', 'Segoe UI', sans-serif",
    mono="'Space Grotesk', 'Segoe UI', sans-serif",
)
BARLOW = FontPair(
    display="'Barlow Condensed', 'Arial Narrow', sans-serif",
    body="'Manrope', 'Segoe UI', sans-serif",
    mono="'Barlow Condensed', 'Arial Narrow', sans-serif",
)
MANROPE = FontPair(
    display="'Manrope', 'Segoe UI', sans-serif",
    body="'Manrope', 'Segoe UI', sans-serif",
    mono="'Manrope', 'Segoe UI', sans-serif",
)
SOURCE_SERIF = FontPair(
    display="'Source Serif 4', Georgia, serif",
    body="'Source Serif 4', Georgia, serif",
    mono="'Source Serif 4', Georgia, serif",
)


DIRECTIONS: Dict[str, ArtDirection] = {
    "object-playful": ArtDirection(
        id="object-playful",
        label="The object, large",
        concept="The subject's physical object is cropped beyond the page edge and becomes the layout.",
        tone="playful",
        fonts=CLASH,
        palette=Palette(
            bg="#C3CBE5", ink="#141414", muted="#4A5068",
            accent="#0F5257", accent_ink="#FFFFFF", accent2="#E56B4E",
            rule="#AAB4D4", panel="#EFD3DA", panel_ink="#141414",
            success="#0F6B50", warning="#965400", danger="#9B2D30",
            cover_bg="#C3CBE5", cover_ink="#141414",
        ),
        cover_style="object", radius="0px", heading_weight="500",
        display_weight="400", letter_spacing="-0.035em",
        body_size="12pt", line_height="1.45", measure="68ch",
        keywords=(
            "crocs", "clog", "jibbitz", "toy", "playful", "kids", "game",
            "candy", "snack", "streetwear", "colorful", "colourful", "fun",
        ),
        scenarios=("marketing-plan", "brochure", "case-study"),
    ),
    "editorial-contrast": ArtDirection(
        id="editorial-contrast", label="Editorial contrast",
        concept="Large display typography and one dominant image carry a magazine-like argument.",
        tone="editorial", fonts=FRAUNCES_SERIF,
        palette=Palette(
            bg="#F7F4EE", ink="#171714", muted="#655F56",
            accent="#B23A2B", accent_ink="#FFFFFF", accent2="#2D5B4A",
            rule="#CFC8BC", panel="#E9E3D8", panel_ink="#171714",
            cover_bg="#171714", cover_ink="#F7F4EE",
        ),
        cover_style="full", radius="0px", heading_weight="600",
        display_weight="600", letter_spacing="-0.03em",
        body_size="11.5pt", line_height="1.58",
        keywords=("magazine", "culture", "arts", "history", "editorial", "journal", "annual report"),
        scenarios=("report", "newsletter", "whitepaper"),
    ),
    "quiet-luxury": ArtDirection(
        id="quiet-luxury", label="Quiet luxury",
        concept="A restrained typographic field gives one photograph and a few facts room to feel expensive.",
        tone="luxury", fonts=FRAUNCES_SANS,
        palette=Palette(
            bg="#F1EFEA", ink="#151514", muted="#6C675F",
            accent="#4C4437", accent_ink="#FFFFFF", accent2="#80735E",
            rule="#C8C2B8", panel="#E4E0D8", panel_ink="#151514",
            cover_bg="#151514", cover_ink="#F1EFEA",
        ),
        cover_style="minimal", radius="0px", heading_weight="500",
        display_weight="400", letter_spacing="-0.025em",
        body_size="11.5pt", line_height="1.62",
        keywords=("luxury", "jewelry", "jewellery", "hotel", "fashion house", "beauty", "premium", "wine"),
        scenarios=("proposal", "portfolio", "certificate"),
    ),
    "technical-field": ArtDirection(
        id="technical-field", label="Technical field",
        concept="Dense information sits inside a dark, high-contrast technical field with one luminous accent.",
        tone="technical", fonts=SPACE,
        palette=Palette(
            bg="#10151D", ink="#F0F3F6", muted="#A8B0BB",
            accent="#68E0C1", accent_ink="#10151D", accent2="#7FA8FF",
            rule="#39414C", panel="#1A222D", panel_ink="#F0F3F6",
            success="#68E0C1", warning="#F4C95D", danger="#FF7A7A",
            cover_bg="#10151D", cover_ink="#F0F3F6",
        ),
        cover_style="type", radius="0px", heading_weight="600",
        display_weight="500", letter_spacing="-0.035em",
        body_size="11.25pt", line_height="1.5",
        keywords=("software", "saas", "ai", "data", "cyber", "developer", "cloud", "technology", "technical"),
        scenarios=("whitepaper", "pitch-deck", "case-study"),
    ),
    "industrial-machine": ArtDirection(
        id="industrial-machine", label="Industrial machine",
        concept="Condensed type, hard fields, and oversized specifications borrow their rhythm from machinery.",
        tone="industrial", fonts=BARLOW,
        palette=Palette(
            bg="#E5E1D6", ink="#10100F", muted="#53504A",
            accent="#F2C500", accent_ink="#10100F", accent2="#C43C2F",
            rule="#8E897E", panel="#D3CFC4", panel_ink="#10100F",
            cover_bg="#10100F", cover_ink="#F2C500",
        ),
        cover_style="type", radius="0px", heading_weight="600",
        display_weight="600", letter_spacing="-0.025em",
        body_size="11.25pt", line_height="1.43",
        keywords=("machine", "mechanic", "mechanical", "manufacturing", "factory", "automotive", "construction", "engineering"),
        scenarios=("report", "proposal", "brochure"),
    ),
    "institutional-clear": ArtDirection(
        id="institutional-clear", label="Institutional clarity",
        concept="A disciplined hierarchy makes consequential financial and board information easy to scan.",
        tone="corporate", fonts=MANROPE,
        palette=Palette(
            bg="#FFFFFF", ink="#10253F", muted="#596B7F",
            accent="#005A5A", accent_ink="#FFFFFF", accent2="#A23B35",
            rule="#C8D1DB", panel="#EEF2F5", panel_ink="#10253F",
            cover_bg="#10253F", cover_ink="#FFFFFF",
        ),
        cover_style="split", radius="0px", heading_weight="700",
        display_weight="700", letter_spacing="-0.025em",
        body_size="11.25pt", line_height="1.5",
        keywords=("bank", "finance", "financial", "insurance", "board", "governance", "investment", "corporate"),
        scenarios=("report", "proposal", "invoice"),
    ),
    "organic-human": ArtDirection(
        id="organic-human", label="Organic human",
        concept="Natural tone fields and generous serif type keep complex human topics calm and grounded.",
        tone="warm", fonts=FRAUNCES_SANS,
        palette=Palette(
            bg="#EEF0E7", ink="#22271F", muted="#646B5F",
            accent="#4C6A52", accent_ink="#FFFFFF", accent2="#A75D46",
            rule="#BEC5B6", panel="#DCE2D5", panel_ink="#22271F",
            cover_bg="#26352A", cover_ink="#EEF0E7",
        ),
        cover_style="split", radius="0px", heading_weight="600",
        display_weight="600", letter_spacing="-0.025em",
        body_size="11.5pt", line_height="1.58",
        keywords=("sustainability", "wellness", "health", "nature", "organic", "food", "community", "climate"),
        scenarios=("report", "brochure", "newsletter"),
    ),
    "scholarly-book": ArtDirection(
        id="scholarly-book", label="Scholarly book",
        concept="Book typography and deliberate page rhythm put comprehension ahead of decoration.",
        tone="academic", fonts=SOURCE_SERIF,
        palette=Palette(
            bg="#FFFFFF", ink="#191919", muted="#5E5E5E",
            accent="#173B63", accent_ink="#FFFFFF", accent2="#7B2D2D",
            rule="#C8C8C8", panel="#F1F3F5", panel_ink="#191919",
            cover_bg="#173B63", cover_ink="#FFFFFF",
        ),
        cover_style="minimal", radius="0px", heading_weight="600",
        display_weight="600", letter_spacing="-0.015em",
        body_size="11.5pt", line_height="1.62",
        keywords=("research", "academic", "university", "thesis", "study", "policy", "science"),
        scenarios=("academic", "whitepaper"),
    ),
    "essential-minimal": ArtDirection(
        id="essential-minimal", label="Essential minimal",
        concept="Strict spacing, one type family, and full-ink text keep short documents efficient and exact.",
        tone="minimal", fonts=MANROPE,
        palette=Palette(
            bg="#FFFFFF", ink="#111111", muted="#626262",
            accent="#111111", accent_ink="#FFFFFF", accent2="#5A5A5A",
            rule="#CFCFCF", panel="#F1F1F1", panel_ink="#111111",
            cover_bg="#111111", cover_ink="#FFFFFF",
        ),
        cover_style="minimal", radius="0px", heading_weight="600",
        display_weight="600", letter_spacing="-0.025em",
        body_size="11pt", line_height="1.5",
        keywords=("resume", "cv", "invoice", "brief", "minimal", "architecture"),
        scenarios=("resume", "invoice", "one-pager"),
    ),
}


THEME_DEFAULTS = {
    "editorial": "editorial-contrast", "swiss": "essential-minimal",
    "modern-saas": "technical-field", "luxury": "quiet-luxury",
    "academic": "scholarly-book", "brutalist": "industrial-machine",
    "minimal": "essential-minimal", "corporate": "institutional-clear",
    "warm-sage": "organic-human", "midnight": "technical-field",
    "vibrant": "object-playful", "national": "institutional-clear",
}


def _tokens(text: str) -> Iterable[str]:
    return re.findall(r"[a-z0-9][a-z0-9-]+", text.casefold())


def infer_direction(meta: dict, scenario_id: str, body_html: str, theme_id: str) -> ArtDirection:
    # Compatibility API; the engine resolves tokens separately from composition.
    from .design import recommend_direction
    return recommend_direction(meta, scenario_id, body_html, theme_id)[0]


def apply_direction(base: DesignSystem, direction: ArtDirection) -> DesignSystem:
    """Return a theme clone whose render tokens follow the selected direction."""
    ds = deepcopy(base)
    ds.fonts = direction.fonts
    ds.palette = direction.palette
    ds.radius = direction.radius
    ds.heading_weight = direction.heading_weight
    ds.display_weight = direction.display_weight
    ds.letter_spacing = direction.letter_spacing
    ds.body_size = direction.body_size
    ds.line_height = direction.line_height
    ds.measure = direction.measure
    ds.cover_style = direction.cover_style
    ds.extras = dict(ds.extras)
    ds.extras.update({
        "field-1": direction.palette.bg,
        "field-2": direction.palette.panel,
        "field-3": direction.palette.accent2,
        "direction-id": f"'{direction.id}'",
    })
    return ds


def list_directions() -> list[dict[str, str]]:
    return [
        {"id": d.id, "label": d.label, "tone": d.tone, "concept": d.concept}
        for d in DIRECTIONS.values()
    ]
