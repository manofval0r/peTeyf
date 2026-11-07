# PDF Studio 2

Design-first PDF generation from Markdown, JSON or trusted HTML. The skill and its Python engine choose typography, composition and reviewed asset placement separately; they do not treat every topic as the same card template.

## What changed

- Explicit theme and brand tokens survive automatic direction selection.
- Subject matching uses word/phrase boundaries and explained neutral fallback.
- Six body-composition families: editorial narrative, evidence-led, object catalogue, photo essay, technical reference and institutional paper.
- Page paint reaches the physical sheet without placing prose at the edges. Print and digital text-safe insets are independent of colour.
- Normal sections flow; only explicitly authored opening/feature/closing sections become staged pages.
- Metrics, specifications, quotes, notes and warnings use different semantic presentations, not a shared perimeter card.
- Reviewed image roles, proportions, transparency and approved crops influence placement. Alpha is preserved; optional missing images are omitted with a warning.
- Charts use effective theme fonts or an explained local fallback, the actual column width and 9pt+ labels. Impossible chart geometry falls back to a readable data table.
- A sibling `.design.json` records selected IDs, locks, reasons, geometry, roles and measured page assignments. `check` consumes it automatically.

## Use the skill

Read `SKILL.md` first. Its workflow requires a design brief, asset review, a build/check loop and inspection of final page previews.

```powershell
python -m pdfstudio themes
python -m pdfstudio compositions
python -m pdfstudio build input.md --out out/document.pdf --preview-pages 20 --keep-html --strict
python -m pdfstudio check out/document.pdf --source input.md
```

The source controls the built-in design:

```yaml
---
title: "Courtyard gardens"
author: "Your name"
scenario: brochure
theme: editorial
composition: photo-essay
output_mode: digital
design:
  subject: courtyard gardening
  audience: home gardeners
  purpose: explain
  assets:
    '@@IMG_1@@':
      role: photo
      fit: contain
      approved: true
  sections:
    planting:
      role: feature
      field: panel
---
```

Write `# Planting {#planting}` to keep an explicit stable heading ID. Image slots are `@@IMG_1@@`, `@@IMG_2@@`, etc. in source order; cover and closing image requests use `cover` and `back_cover`. Role metadata is validated against actual requests before downloading.

An approved crop `[x0,y0,x1,y1]` and focal `[x,y]` use normalised source coordinates. A crop is applied only with `approved: true`; analysis does not alter the original encoded asset. Optional `derive_accent: true` requires approval and cannot override locked palette/brand choices.

## Built-in layers

| Layer | Responsibility |
|---|---|
| Scenario | Functional conventions, physical format, cover/TOC and numbering |
| Theme | Palette, font families, base type and brand tokens |
| Composition | Content and asset organisation across body pages |
| Component | Open metrics, ruled comparisons, specifications, quotes and alerts |
| Medium | Text-safe bounds and physical page fields |

Default print insets are 20/18/22/18mm top/right/bottom/left; digital uses 16mm. `design.safe_mm` can explicitly override these. These bounds do not create a white frame: page fields paint independently. Commercial printer crop/trim bleed is outside this release.

All 11 existing theme IDs and 14 scenario IDs remain available. Legacy art-direction IDs map to composition aliases. `--css` is still an explicit custom-brand escape hatch, but is not the default workflow or a valid way to claim a skill-only demonstration.

## Verification

```powershell
python tests/run_checks.py --log out/skill-upgrade/full-suite.log
python -m tests.render_design_gallery --out out/design-gallery
```

The deterministic gallery uses the same locked Swiss theme across six subjects, with locally generated assets and clearly labelled synthetic data. Both colour and grayscale comparisons are written. These fixtures test composition, not real-world facts or image-search quality.

Checks cover choice precedence, keyword boundaries, format geometry, real Chromium page-edge paint and continuation, content order/anchors, open component styles, alpha/crop/reference handling, final chart dimensions/fonts, mixed page fields, meaningful source-content presence and legacy loader paths.

Technical QA retains selectable text, `/Lang`, tags, metadata, outlines, two-pass TOC and the 9pt floor. Design QA samples declared page fields, uses character ink/advance boxes for text-safe checks, and reports sparse ordinary flow separately from intentional feature treatments. Images still need visual relevance/crop review; raster chart labels are checked at generation/final width rather than pretending they are extractable PDF text. A successful geometry check does not prove aesthetic excellence.

## Architecture

- `design.py`: selection, locks, explanations and compatibility aliases.
- `geometry.py`: physical formats and independent safe bounds.
- `blocks.py`: order-preserving semantic blocks and opaque HTML fallback.
- `asset_layout.py` / `asset_render.py`: approved roles/crops and pre-layout resolution.
- `compositions.py` / templates / CSS: six reusable body grammars.
- `render.py`: one-document Chromium orchestration and finalisation.
- `qa.py` / `design_qa.py` / `contrast.py`: measured output checks.

The document is rendered as one Chromium PDF and finalised with PyMuPDF; pages are not rasterised or merged. WeasyPrint remains a compatibility fallback but does not establish equivalent full-field behaviour on untested versions.

## Installation

Existing dependencies are in `requirements.txt`: Python 3.10+, Playwright/Chromium, PyMuPDF, matplotlib, Pillow, requests, Jinja2, Markdown and PyYAML. No required package or paid service was added. Nested YAML design metadata needs PyYAML; it is never silently flattened.

To install this skill in another assistant, place the package contents together in its user-skill directory. `SKILL.md` and `pdfstudio/` must be from the same version. Updating only the instructions does not update the engine. Keep output files outside the installed package when generating a user deliverable.

MIT-licensed. Network-sourced images retain their own source licences and attribution requirements.
