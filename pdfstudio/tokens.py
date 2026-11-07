"""Design systems (themes) for PDF Studio.

Every theme is a complete visual language: typography pairing, palette,
spacing rhythm, rules, panel treatment, and cover mood. The renderer turns a
theme into CSS custom properties, so templates stay theme-agnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class FontPair:
    display: str
    body: str
    mono: str = "'JetBrains Mono', 'Cascadia Code', Consolas, monospace"
    # Optional web-font family names used when local fonts are installed.
    display_google: Optional[str] = None
    body_google: Optional[str] = None
    mono_google: Optional[str] = None


@dataclass
class Palette:
    bg: str
    ink: str
    muted: str
    accent: str
    accent_ink: str          # text on accent
    accent2: str
    rule: str
    panel: str
    panel_ink: str
    success: str = "#1F7A4D"
    warning: str = "#B4690E"
    danger: str = "#B42318"
    cover_bg: Optional[str] = None
    cover_ink: Optional[str] = None


@dataclass
class DesignSystem:
    id: str
    label: str
    mood: str
    fonts: FontPair
    palette: Palette
    radius: str = "10px"
    rule_width: str = "1px"
    heading_weight: str = "700"
    display_weight: str = "700"
    letter_spacing: str = "-0.01em"
    body_size: str = "10.5pt"
    line_height: str = "1.55"
    measure: str = "82ch"
    margin: str = "16mm 14mm 18mm 14mm"
    cover_align: str = "left"          # left | center
    cover_style: str = "split"         # split | full | minimal | image | type
    toc_style: str = "rule"            # rule | dots | numbered
    texture: str = "none"              # none | grain | grid | lines
    extras: Dict[str, str] = field(default_factory=dict)

    def css_vars(self) -> str:
        p = self.palette
        f = self.fonts
        lines = [
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
            f"--font-display: {f.display};",
            f"--font-body: {f.body};",
            f"--radius: {self.radius};",
            f"--rule-width: {self.rule_width};",
            f"--heading-weight: {self.heading_weight};",
            f"--display-weight: {self.display_weight};",
            f"--letter-spacing: {self.letter_spacing};",
            f"--body-size: {self.body_size};",
            f"--line-height: {self.line_height};",
            f"--measure: {self.measure};",
            f"--page-margin: {self.margin};",
            f"--cover-align: {self.cover_align};",
        ]
        for k, v in self.extras.items():
            lines.append(f"--{k}: {v};")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Palette + font building blocks
# ---------------------------------------------------------------------------

SERIF_DISPLAY = FontPair(
    display="'Playfair Display', 'Georgia', 'Cambria', serif",
    body="'Source Serif 4', 'Georgia', 'Cambria', serif",
    mono="'JetBrains Mono', 'Cascadia Code', Consolas, monospace",
    display_google="Playfair+Display",
    body_google="Source+Serif+4",
    mono_google="JetBrains+Mono",
)
SANS_DISPLAY = FontPair(
    display="'Inter Tight', 'Segoe UI', 'Arial', sans-serif",
    body="'Inter', 'Segoe UI', 'Arial', sans-serif",
    mono="'JetBrains Mono', 'Cascadia Code', Consolas, monospace",
    display_google="Inter+Tight",
    body_google="Inter",
    mono_google="JetBrains+Mono",
)
GROTESK = FontPair(
    display="'Space Grotesk', 'Segoe UI', 'Arial', sans-serif",
    body="'Inter', 'Segoe UI', 'Arial', sans-serif",
    mono="'Space Mono', 'Cascadia Code', Consolas, monospace",
    display_google="Space+Grotesk",
    body_google="Inter",
    mono_google="Space+Mono",
)
CLASSIC_SERIF = FontPair(
    display="'Georgia', 'Cambria', 'Times New Roman', serif",
    body="'Georgia', 'Cambria', 'Times New Roman', serif",
    mono="'Courier New', Consolas, monospace",
)


THEMES: Dict[str, DesignSystem] = {}


def _register(ds: DesignSystem) -> None:
    THEMES[ds.id] = ds


_register(DesignSystem(
    id="editorial",
    label="Editorial",
    mood="Warm, literary, magazine-grade",
    fonts=SERIF_DISPLAY,
    palette=Palette(
        bg="#FBF8F2", ink="#1C1A17", muted="#6B645A",
        accent="#B4552D", accent_ink="#FFFFFF", accent2="#2F5D50",
        rule="#D9D1C4", panel="#F3EDE2", panel_ink="#2A2621",
        cover_bg="#1C1A17", cover_ink="#FBF8F2",
    ),
    radius="2px", rule_width="1px", heading_weight="800",
    letter_spacing="-0.015em", body_size="10.6pt", line_height="1.58",
    cover_style="split", toc_style="dots", texture="grain",
))

_register(DesignSystem(
    id="swiss",
    label="Swiss Grid",
    mood="Precise, rational, typographic",
    fonts=SANS_DISPLAY,
    palette=Palette(
        bg="#FFFFFF", ink="#111111", muted="#666666",
        accent="#E2231A", accent_ink="#FFFFFF", accent2="#111111",
        rule="#DADADA", panel="#F4F4F4", panel_ink="#111111",
        cover_bg="#111111", cover_ink="#FFFFFF",
    ),
    radius="0px", rule_width="2px", heading_weight="800",
    letter_spacing="-0.02em", body_size="10.2pt", line_height="1.45",
    cover_style="type", toc_style="numbered", texture="grid",
))

_register(DesignSystem(
    id="modern-saas",
    label="Modern SaaS",
    mood="Clean, confident, product-led",
    fonts=SANS_DISPLAY,
    palette=Palette(
        bg="#FFFFFF", ink="#0F172A", muted="#64748B",
        accent="#4F46E5", accent_ink="#FFFFFF", accent2="#06B6D4",
        rule="#E2E8F0", panel="#F8FAFC", panel_ink="#0F172A",
        cover_bg="#0F172A", cover_ink="#F8FAFC",
    ),
    radius="14px", rule_width="1px", heading_weight="700",
    letter_spacing="-0.02em", body_size="10.4pt", line_height="1.55",
    cover_style="split", toc_style="rule", texture="none",
))

_register(DesignSystem(
    id="luxury",
    label="Luxury",
    mood="Quiet, expensive, generous whitespace",
    fonts=FontPair(
        display="'Cormorant Garamond', 'Georgia', serif",
        body="'Lato', 'Segoe UI', sans-serif",
        mono="'JetBrains Mono', Consolas, monospace",
        display_google="Cormorant+Garamond",
        body_google="Lato",
        mono_google="JetBrains+Mono",
    ),
    palette=Palette(
        bg="#F7F3EB", ink="#161310", muted="#7A7064",
        accent="#A67C2E", accent_ink="#FFFFFF", accent2="#161310",
        rule="#DCD2C0", panel="#EFE8DA", panel_ink="#2A241C",
        cover_bg="#161310", cover_ink="#F7F3EB",
    ),
    radius="0px", rule_width="1px", heading_weight="500",
    letter_spacing="0.02em", body_size="10.8pt", line_height="1.7",
    cover_style="minimal", toc_style="dots", texture="none",
))

_register(DesignSystem(
    id="academic",
    label="Academic",
    mood="Scholarly, restrained, citation-ready",
    fonts=CLASSIC_SERIF,
    palette=Palette(
        bg="#FFFFFF", ink="#1A1A1A", muted="#5C5C5C",
        accent="#1F4E79", accent_ink="#FFFFFF", accent2="#7A1F1F",
        rule="#CFCFCF", panel="#F5F6F7", panel_ink="#1A1A1A",
    ),
    radius="0px", rule_width="1px", heading_weight="700",
    letter_spacing="0", body_size="10.8pt", line_height="1.6",
    cover_style="minimal", toc_style="rule", texture="none",
))

_register(DesignSystem(
    id="brutalist",
    label="Industrial Brutalist",
    mood="Loud, mechanical, declassified blueprint",
    fonts=GROTESK,
    palette=Palette(
        bg="#F2F0EA", ink="#0A0A0A", muted="#4A4A4A",
        accent="#FFD400", accent_ink="#0A0A0A", accent2="#FF3B30",
        rule="#0A0A0A", panel="#E6E2D6", panel_ink="#0A0A0A",
        cover_bg="#0A0A0A", cover_ink="#FFD400",
    ),
    radius="0px", rule_width="3px", heading_weight="800",
    letter_spacing="-0.03em", body_size="10.4pt", line_height="1.45",
    cover_style="type", toc_style="numbered", texture="grid",
))

_register(DesignSystem(
    id="minimal",
    label="Minimal",
    mood="Monochrome, hairline, nothing extra",
    fonts=SANS_DISPLAY,
    palette=Palette(
        bg="#FFFFFF", ink="#111111", muted="#8A8A8A",
        accent="#111111", accent_ink="#FFFFFF", accent2="#555555",
        rule="#E6E6E6", panel="#FAFAFA", panel_ink="#111111",
    ),
    radius="2px", rule_width="1px", heading_weight="600",
    letter_spacing="-0.01em", body_size="10.2pt", line_height="1.5",
    cover_style="minimal", toc_style="rule", texture="none",
))

_register(DesignSystem(
    id="corporate",
    label="Corporate",
    mood="Trustworthy, structured, institutional",
    fonts=SANS_DISPLAY,
    palette=Palette(
        bg="#FFFFFF", ink="#0B1F3A", muted="#5A6B82",
        accent="#0B5FFF", accent_ink="#FFFFFF", accent2="#00857A",
        rule="#D6DEE8", panel="#F3F6FA", panel_ink="#0B1F3A",
        cover_bg="#0B1F3A", cover_ink="#FFFFFF",
    ),
    radius="6px", rule_width="1px", heading_weight="700",
    letter_spacing="-0.01em", body_size="10.4pt", line_height="1.5",
    cover_style="split", toc_style="rule", texture="none",
))

_register(DesignSystem(
    id="warm-sage",
    label="Warm Sage",
    mood="Organic, human, calm",
    fonts=FontPair(
        display="'Fraunces', 'Georgia', serif",
        body="'Nunito Sans', 'Segoe UI', sans-serif",
        mono="'JetBrains Mono', Consolas, monospace",
        display_google="Fraunces",
        body_google="Nunito+Sans",
        mono_google="JetBrains+Mono",
    ),
    palette=Palette(
        bg="#F8F6EF", ink="#22261F", muted="#6E7464",
        accent="#6B7F5B", accent_ink="#FFFFFF", accent2="#C98A5E",
        rule="#DAD8C9", panel="#EDEBDD", panel_ink="#2A2E25",
        cover_bg="#22261F", cover_ink="#F8F6EF",
    ),
    radius="10px", rule_width="1px", heading_weight="600",
    letter_spacing="-0.01em", body_size="10.5pt", line_height="1.6",
    cover_style="split", toc_style="dots", texture="grain",
))

_register(DesignSystem(
    id="midnight",
    label="Midnight",
    mood="Dark, technical, neon-accented",
    fonts=GROTESK,
    palette=Palette(
        bg="#0B1020", ink="#EAF0FF", muted="#93A0C0",
        accent="#7C9CFF", accent_ink="#0B1020", accent2="#4DE0C0",
        rule="#26304D", panel="#121A33", panel_ink="#EAF0FF",
        cover_bg="#070B16", cover_ink="#EAF0FF",
    ),
    radius="12px", rule_width="1px", heading_weight="600",
    letter_spacing="-0.01em", body_size="10.4pt", line_height="1.55",
    cover_style="split", toc_style="rule", texture="grid",
))

_register(DesignSystem(
    id="vibrant",
    label="Vibrant",
    mood="Energetic, bold, campaign-ready",
    fonts=GROTESK,
    palette=Palette(
        bg="#FFFDF7", ink="#141414", muted="#5E5E5E",
        accent="#FF4D6D", accent_ink="#FFFFFF", accent2="#00C2A8",
        rule="#EADFD2", panel="#FFF1E8", panel_ink="#141414",
        cover_bg="#FF4D6D", cover_ink="#FFFFFF",
    ),
    radius="16px", rule_width="1px", heading_weight="800",
    letter_spacing="-0.02em", body_size="10.5pt", line_height="1.5",
    cover_style="type", toc_style="numbered", texture="none",
))

_register(DesignSystem(
    id="national",
    label="National",
    mood="Authoritative, civic, green-and-navy sovereign institution",
    fonts=FontPair(
        display="'Georgia', 'Times New Roman', serif",
        body="'Segoe UI', 'Inter', 'Arial', sans-serif",
        mono="'JetBrains Mono', Consolas, monospace",
    ),
    palette=Palette(
        bg="#FFFFFF", ink="#0F2537", muted="#5A6B82",
        accent="#1B5E20", accent_ink="#FFFFFF", accent2="#D4AF37",
        rule="#D0DBE5", panel="#F4F7F6", panel_ink="#0F2537",
        success="#1B5E20", warning="#B4690E", danger="#B71C1C",
        cover_bg="#0F2537", cover_ink="#FFFFFF",
    ),
    radius="4px", rule_width="1.5px", heading_weight="700",
    display_weight="800", letter_spacing="-0.015em",
    body_size="10.2pt", line_height="1.55", measure="82ch",
    margin="16mm 14mm 18mm 14mm",
    cover_style="split", toc_style="rule", texture="none",
))



_register(DesignSystem(
    id="nordic",
    label="Nordic",
    mood="Clean, cool, airy, humanist minimalism",
    fonts=FontPair(
        display="'Inter Tight', 'Segoe UI', 'Helvetica Neue', sans-serif",
        body="'Inter', 'Segoe UI', 'Helvetica Neue', sans-serif",
        mono="'JetBrains Mono', Consolas, monospace",
    ),
    palette=Palette(
        bg="#F8FAFC", ink="#0F172A", muted="#64748B",
        accent="#0284C7", accent_ink="#FFFFFF", accent2="#0D9488",
        rule="#E2E8F0", panel="#EDF4F9", panel_ink="#0F172A",
        success="#0D9488", warning="#D97706", danger="#E11D48",
        cover_bg="#0F172A", cover_ink="#F8FAFC",
    ),
    radius="6px", rule_width="1px", heading_weight="600",
    display_weight="700", letter_spacing="-0.015em",
    body_size="10.2pt", line_height="1.55", measure="82ch",
    margin="16mm 14mm 18mm 14mm",
    cover_style="split", toc_style="rule", texture="none",
))

_register(DesignSystem(
    id="monograph",
    label="Monograph",
    mood="Scholarly, archival, authoritative university press",
    fonts=FontPair(
        display="'Playfair Display', 'Georgia', 'Baskerville', serif",
        body="'Source Serif 4', 'Georgia', 'Cambria', serif",
        mono="'JetBrains Mono', Consolas, monospace",
    ),
    palette=Palette(
        bg="#FCFBF7", ink="#1C1917", muted="#78716C",
        accent="#881337", accent_ink="#FFFFFF", accent2="#B45309",
        rule="#E7E5E4", panel="#F5F3EF", panel_ink="#1C1917",
        success="#15803D", warning="#B45309", danger="#991B1B",
        cover_bg="#1C1917", cover_ink="#FCFBF7",
    ),
    radius="0px", rule_width="1px", heading_weight="700",
    display_weight="700", letter_spacing="0em",
    body_size="10.4pt", line_height="1.6", measure="78ch",
    margin="16mm 14mm 18mm 14mm",
    cover_style="minimal", toc_style="rule", texture="none",
))

_register(DesignSystem(
    id="fintech",
    label="Fintech / Quant",
    mood="High-precision, data-dense, quantitative terminal",
    fonts=FontPair(
        display="'Space Grotesk', 'Segoe UI', sans-serif",
        body="'Inter', 'Segoe UI', 'Arial', sans-serif",
        mono="'Space Mono', 'JetBrains Mono', Consolas, monospace",
    ),
    palette=Palette(
        bg="#FFFFFF", ink="#0B0F19", muted="#475569",
        accent="#2563EB", accent_ink="#FFFFFF", accent2="#059669",
        rule="#E2E8F0", panel="#F1F5F9", panel_ink="#0B0F19",
        success="#059669", warning="#D97706", danger="#DC2626",
        cover_bg="#0B0F19", cover_ink="#FFFFFF",
    ),
    radius="4px", rule_width="1px", heading_weight="700",
    display_weight="800", letter_spacing="-0.02em",
    body_size="10pt", line_height="1.5", measure="82ch",
    margin="16mm 14mm 18mm 14mm",
    cover_style="split", toc_style="rule", texture="grid",
))

_register(DesignSystem(
    id="heritage",
    label="Heritage Dispatch",
    mood="Dignified, historic, presidential and diplomatic statecraft",
    fonts=FontPair(
        display="'Georgia', 'Times New Roman', serif",
        body="'Segoe UI', 'Inter', 'Arial', sans-serif",
        mono="'JetBrains Mono', Consolas, monospace",
    ),
    palette=Palette(
        bg="#FAFAF9", ink="#0C131F", muted="#57606A",
        accent="#7F1D1D", accent_ink="#FFFFFF", accent2="#CA8A04",
        rule="#D6D3D1", panel="#F3F2EE", panel_ink="#0C131F",
        success="#15803D", warning="#B45309", danger="#991B1B",
        cover_bg="#1E1B24", cover_ink="#FAFAF9",
    ),
    radius="2px", rule_width="1.5px", heading_weight="700",
    display_weight="800", letter_spacing="-0.01em",
    body_size="10.2pt", line_height="1.55", measure="82ch",
    margin="16mm 14mm 18mm 14mm",
    cover_style="split", toc_style="rule", texture="none",
))


def get_theme(theme_id: str) -> DesignSystem:
    """Return declared tokens; reject misspelled explicit choices."""
    if theme_id not in THEMES:
        raise ValueError(f"Unknown theme {theme_id!r}. Supported: {', '.join(THEMES)}")
    return THEMES[theme_id]


def list_themes() -> List[Dict[str, str]]:
    return [
        {"id": t.id, "label": t.label, "mood": t.mood}
        for t in THEMES.values()
    ]
