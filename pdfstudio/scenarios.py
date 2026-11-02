"""Scenario archetypes.

A scenario is the *job* of the document (a marketing plan, an invoice, a
whitepaper...). It selects a layout, a default design system, section
furniture, and content guidance. Themes control the visual language; scenarios
control the structure and the reading experience.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Scenario:
    id: str
    label: str
    description: str
    default_theme: str
    page: str = "A4"              # A4 | Letter
    landscape: bool = False
    cover: str = "split"          # split | full | minimal | image | type | none
    toc: bool = True
    numbered_sections: bool = False
    header: bool = True
    footer: bool = True
    watermark: str = ""
    layout: str = "single"        # single | sidebar | two-col | cards
    section_rule: bool = True
    best_for: List[str] = field(default_factory=list)
    structure: List[str] = field(default_factory=list)
    css_class: str = ""


SCENARIOS: Dict[str, Scenario] = {}


def _register(s: Scenario) -> None:
    s.css_class = f"scenario-{s.id}"
    SCENARIOS[s.id] = s


_register(Scenario(
    id="report",
    label="Business / Annual Report",
    description="Editorial long-form report with cover, TOC, data callouts and page furniture.",
    default_theme="editorial",
    cover="full", toc=True, numbered_sections=True, layout="single",
    best_for=["annual reports", "research findings", "board updates", "market reviews"],
    structure=["Executive summary", "Context & method", "Findings", "Data & analysis",
               "Recommendations", "Appendix"],
))

_register(Scenario(
    id="marketing-plan",
    label="Marketing Plan",
    description="Strategy document with situation analysis, SWOT, SMART objectives, strategy, action programs, budget and controls.",
    default_theme="modern-saas",
    cover="split", toc=True, numbered_sections=True, layout="cards",
    best_for=["course assignments", "campaign plans", "go-to-market plans", "brand plans"],
    structure=["Executive summary", "Current marketing situation", "SWOT & issues",
               "Objectives", "Marketing strategy", "Action programs", "Budget",
               "Controls"],
))

_register(Scenario(
    id="proposal",
    label="Client Proposal",
    description="Persuasive, generous-whitespace proposal with scope, approach, team, timeline and pricing.",
    default_theme="luxury",
    cover="minimal", toc=True, numbered_sections=False, layout="single",
    best_for=["agency proposals", "consulting bids", "partnerships", "grants"],
    structure=["Understanding", "Approach", "Scope & deliverables", "Timeline",
               "Team", "Investment", "Next steps"],
))

_register(Scenario(
    id="invoice",
    label="Invoice / Quote",
    description="Compact, tabular financial document with line items, totals and payment terms.",
    default_theme="minimal",
    page="A4", cover="none", toc=False, numbered_sections=False, layout="single",
    header=False, footer=True,
    best_for=["invoices", "quotations", "receipts", "statements"],
    structure=["From / Bill to", "Line items", "Totals", "Payment terms"],
))

_register(Scenario(
    id="whitepaper",
    label="Whitepaper",
    description="Research-heavy thought-leadership document with abstract, evidence, charts and references.",
    default_theme="academic",
    cover="full", toc=True, numbered_sections=True, layout="single",
    best_for=["technical whitepapers", "policy papers", "research briefs"],
    structure=["Abstract", "Introduction", "Background", "Method", "Findings",
               "Discussion", "References"],
))

_register(Scenario(
    id="case-study",
    label="Case Study",
    description="Narrative success story with challenge, solution, results metrics and testimonial.",
    default_theme="modern-saas",
    cover="image", toc=False, numbered_sections=False, layout="cards",
    best_for=["customer stories", "portfolio proof", "sales enablement"],
    structure=["Challenge", "Solution", "Implementation", "Results", "Testimonial"],
))

_register(Scenario(
    id="resume",
    label="Résumé / CV",
    description="Minimal, ATS-friendly one-to-two page résumé with clean hierarchy.",
    default_theme="minimal",
    page="Letter", cover="none", toc=False, numbered_sections=False, layout="single",
    header=False, footer=False,
    best_for=["résumés", "CVs", "professional profiles"],
    structure=["Profile", "Experience", "Education", "Skills", "Projects"],
))

_register(Scenario(
    id="one-pager",
    label="One-Pager / Brief",
    description="Dense single-page decision brief that fits on one page.",
    default_theme="swiss",
    page="A4", cover="none", toc=False, numbered_sections=False, layout="two-col",
    header=False, footer=False,
    best_for=["decision briefs", "executive summaries", "product one-pagers"],
    structure=["The ask", "Why now", "What we propose", "Impact", "Next step"],
))

_register(Scenario(
    id="academic",
    label="Academic Paper",
    description="Formal paper layout with abstract, numbered headings, figures and references.",
    default_theme="academic",
    page="Letter", cover="minimal", toc=True, numbered_sections=True, layout="single",
    best_for=["term papers", "journal submissions", "literature reviews"],
    structure=["Abstract", "Introduction", "Related work", "Method", "Results",
               "Discussion", "Conclusion", "References"],
))

_register(Scenario(
    id="brochure",
    label="Brochure / Collateral",
    description="Image-led marketing collateral with bold statements and feature blocks.",
    default_theme="vibrant",
    page="A4", cover="image", toc=False, numbered_sections=False, layout="cards",
    header=False, footer=True,
    best_for=["service brochures", "event programmes", "product catalogues"],
    structure=["Hook", "What we do", "Features", "Proof", "Call to action"],
))

_register(Scenario(
    id="certificate",
    label="Certificate / Award",
    description="Landscape award certificate with ornamental frame and signature block.",
    default_theme="luxury",
    page="A4", landscape=True, cover="none", toc=False,
    numbered_sections=False, layout="single", header=False, footer=False,
    best_for=["certificates", "awards", "completion records"],
    structure=["Award title", "Recipient", "Citation", "Signatures"],
))

_register(Scenario(
    id="newsletter",
    label="Newsletter",
    description="Editorial newsletter with masthead, sections and image stories.",
    default_theme="editorial",
    page="A4", cover="none", toc=False, numbered_sections=False, layout="two-col",
    header=False, footer=True,
    best_for=["internal newsletters", "community updates", "digests"],
    structure=["Masthead", "Lead story", "Briefs", "Calendar", "Footer"],
))

_register(Scenario(
    id="portfolio",
    label="Portfolio",
    description="Visual portfolio with project spreads and captions.",
    default_theme="minimal",
    page="A4", cover="image", toc=False, numbered_sections=False, layout="cards",
    header=False, footer=True,
    best_for=["design portfolios", "photography books", "project catalogues"],
    structure=["Selected work", "Project spreads", "About", "Contact"],
))

_register(Scenario(
    id="pitch-deck",
    label="Pitch Deck (print)",
    description="Landscape slide-style pages for a printed or PDF pitch deck.",
    default_theme="modern-saas",
    page="A4", landscape=True, cover="type", toc=False,
    numbered_sections=False, layout="cards",
    best_for=["investor decks", "sales decks", "keynote handouts"],
    structure=["Problem", "Solution", "Market", "Product", "Traction", "Team", "Ask"],
))


def get_scenario(scenario_id: str) -> Scenario:
    return SCENARIOS.get(scenario_id, SCENARIOS["report"])


def list_scenarios() -> List[Dict[str, object]]:
    return [
        {
            "id": s.id,
            "label": s.label,
            "description": s.description,
            "default_theme": s.default_theme,
            "best_for": s.best_for,
        }
        for s in SCENARIOS.values()
    ]
