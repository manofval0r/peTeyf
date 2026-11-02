# PDF Studio — Design-First PDF Generation

> **Skill version**: 2.0 (post-contrast / measurable-QA / named-page / image-review upgrade)  
> **Purpose**: Turn Markdown/JSON/HTML into art-directed, print-ready PDFs with real design systems, web-sourced credited images, generated charts, accessible tags, and a verification loop — not a printout.

---

## What it produces

A finished PDF that reads like it was composed, not dumped:

- **Cover** (named `@page cover`, zero margin, bounded photo + solid text fields, brand font, confidential badge)
- **Table of contents** with correct page numbers (two-pass scan, rebuilt if content shifts)
- **Body chapters** full-bleed, full-height, alternating colour fields, 12pt body, 68ch measure, real running header/footer at 9pt in brand font
- **Charts** with brand fonts, horizontal labels, direct value labels, legend outside plot, `Fig. N` figure numbers
- **Images** sourced, cached, embedded as base64 data URIs with attribution; no network dependency at render time
- **Credits block** automatically assembled from every embedded image
- **Back cover** using a dedicated image, never the cover photo reused
- **Tagged PDF** (`StructTreeRoot`, `MarkInfo`, `Lang`, outline, page mode) preserved via single-document Chromium → PyMuPDF finalize (`garbage=3`)

Verified result (Crocs 12-Month plan, rebuilt after upgrade): 18 pages, 8,384 chars, 8 images at 300 dpi, body 12.0pt, smallest 9pt, measure 73 chars/line, `lang=en`, tags yes, outline 10, metadata complete.

---

## Quick start

```bash
# Build with previews
python -m pdfstudio build examples/crocs-plan.md \
    --out out/crocs-plan.pdf --preview-pages 18 --keep-html

# Measure the finished PDF against declared design intent
python -m pdfstudio check out/crocs-plan.pdf --source examples/crocs-plan.md

# Build the image-candidate sheet before pinning any photograph
python -m pdfstudio images "crocs retail display" --out out/candidates.jpg

# Copy gate with locale
python -m pdfstudio copycheck examples/crocs-plan.md --locale en-GB
```

---

## The design systems (`theme`)

| Theme | Mood | Font pair | Cover style |
|---|---|---|---|
| **editorial** | Serif, print | Source Serif 4 / Source Serif 4 | split |
| **swiss** | Grid, discipline | Barlow / Barlow | split |
| **modern-saas** | Clean, indigo | Manrope / Manrope | split |
| **luxury** | Serif / gold | Fraunces / Source Serif 4 | minimal |
| **academic** | Restrained, footnotes | Source Serif 4 / Source Serif 4 | split |
| **brutalist** | Raw, mechanical | Barlow / Space Grotesk | full |
| **minimal** | Quiet, white | Space Grotesk / Source Serif 4 | none |
| **corporate** | Navy, steady | Manrope / Manrope | split |
| **warm-sage** | Earthy, calm | Manrope / Source Serif 4 | split |
| **midnight** | Dark cover, luminous | Manrope / Source Serif 4 | image |
| **vibrant** | Saturated, energetic | Space Grotesk / Source Serif 4 | split |

Themes inject tokens (`--font-body`, `--font-display`, `--ink`, `--accent`, `--measure`, `--page-margin`) into CSS; templates stay theme-agnostic.

---

## The scenarios (`scenario`)

| ID | Use for | Default theme | Cover | Layout |
|---|---|---|---|---|
| `report` | Annual / research reports | editorial | full | single |
| `marketing-plan` | Marketing / business plans | modern-saas | split | cards |
| `proposal` | Proposals / bids | luxury | minimal | single |
| `invoice` | Invoices / quotes | minimal | none | minimal |
| `whitepaper` | Whitepapers / deep reports | academic | split | single |
| `case-study` | Customer stories | modern-saas | image | cards |
| `resume` | CVs / resumes | minimal | none | single |
| `one-pager` | Decision briefs | swiss | split | two-col |
| `academic` | Essays / dissertations | academic | split | single |
| `brochure` | Brochures / campaigns | vibrant | image | cards |
| `certificate` | Certificates / awards | luxury | full | single |
| `newsletter` | Newsletters | editorial | none | two-col |
| `portfolio` | Portfolios | minimal | image | cards |
| `pitch-deck` | Pitch decks | modern-saas | split | cards |

---

## Art directions (`art_direction`)

9 directions control cover mood + body composition: `object-playful` (Crocs), `editorial-contrast`, `quiet-luxury`, `technical-field`, `industrial-machine`, `institutional-clarity`, `organic-human`, `scholarly-book`, `essential-minimal`. Set explicitly (`art_direction: object-playful`) or inferred from topic.

---

## Source format (`.md` + frontmatter)

```yaml
---
title: "Crocs: A 12-Month Growth Plan"
subtitle: "Making comfort a repeatable ritual"
scenario: marketing-plan
theme: vibrant
art_direction: object-playful
tone: playful
author: "Brand Strategy Team"
date: "November 2026"
client: "Crocs, Inc."
org: "Crocs Growth Lab"
confidential: "Working draft"
summary: "A practical plan for turning occasional buyers into loyal members..."
cover_image: "search:commons:DFC 4366 ..."
cover_caption: "Colourful Crocs clogs decorated with charms."
toc_title: "The plan at a glance"
back_cover:
  title: "Come back for comfort."
  text: "Start with the people who already love the product..."
  contact: "Brand Strategy Team"
---
```

Content blocks (pre-processed before Markdown conversion):
- `metrics` — 3-5 numbers, delta shown
- `swot` — 2x2 matrix, not a table
- `chart bar / line / stacked / pie / donut / area` — data to PNG
- Callouts: `> [!NOTE] ...`, `> [!KEY] ...`, `> [!ACTION] ...`, `> [!WARNING] ...`
- Images: `![alt](search:description)` / `img:path` / URL / `search:commons:Exact File.jpg`
- Page breaks: `<div class="page-break"></div>` or `## Heading {.no-toc}`

---

## Image sourcing (upgraded)

Providers: Wikimedia Commons (primary, fast) → Wikipedia media (fallback) → Openverse.

- Downloads throttled at `upload.wikimedia.org` (1.5s gap) with 4 retries + backoff.
- Relevance ranking uses synonym groups (`shoe`↔`footwear`↔`clog`) and a zero-match penalty (prevents unrelated high-res photos from winning).
- `resolve_search(..., avoid=...)` prevents reusing cover photo in body.
- `contact_sheet()` produces a labelled thumbnail sheet (index / title / dims / licence) for visual verification — **look at the sheet before pinning**.
- Once pinned with `search:commons:Israel Batch 1 (640).JPG`, the exact file is locked; later searches cannot drift.

Credits block auto-assembled from all embedded images; if images present but no credits, `check` reports `missing_credits`.

---

## Chart styling (`charts.py` — rebuilt)

- Brand font (`Manrope.ttf`, `clash-grotesk-500.ttf`) loaded by explicit `FontProperties(fname=...)` — avoids "false" family-name issue on Clash Grotesk 400.
- Long category names → horizontal bars automatically.
- Direct value labels on every bar / point.
- Legend placed below plot (`bbox_to_anchor=(0.0, 1.01)`), never over data.
- Caption format: `<figcaption><span class="figure__num">Fig. 2</span> Title</figcaption>`
- No "Illustrative" in chart titles; planning-assumptions note added to source.

---

## Contrast (`contrast.py` — isolated fix)

- Playwright probe measures WCAG ratio against pixels actually behind each text element (handles photos, gradients, strong colour fields).
- **Non-display text** (body, caption, label, credit): isolated solid-field CSS (`background` + `color` + `padding`) scoped to the exact selector — only that element changes.
- **Display text** (headlines, cover title): reported, not auto-patched — fix is composition (solid field / bounded photo / crop).
- `build` applies `fix_css` automatically; `check` reports remaining clashes.

---

## Pipeline (`render.py` — single document)

1. **Cover + body in one HTML** (not merged PDFs) — preserves `StructTreeRoot`
2. Named pages: `@page cover` (zero margin, no running furniture) + `@page` (margin-box header/footer at 9pt brand font)
3. `html, body { overflow: hidden }` — restores real 12pt/48pt (fixes silent 9.4% Chromium shrink when one element overflows the page)
4. Full-bleed technique: `width: var(--page-w); margin-left: -18mm; min-height: var(--inner-h)` — tested at 48.0pt H1
5. Chapter wrapping (`_wrap_chapters`) → `.chapter` sections with `break-before: page`
6. Two-pass TOC: pass 1 renders; `fitz` scans heading pages; pass 2 injects page numbers; rebuilt if page counts shift
7. `finalize_pdf`: `fitz.set_metadata`, `set_toc`, `Lang`, `PageMode=/UseOutlines`, save `garbage=3`

---

## QA (`qa.py` — measurable gates)

`analyze()` measures, not guesses. Structured `issues` + `gates` (boolean) + legacy `warnings`. Call with `expect={...}` from source.

| Gate | Check | Fail if |
|---|---|---|
| `type_floor` | Font size ≥ floor (9pt) | Any text below floor |
| `measure` | Line length inside target ±24ch | Lines too long / short |
| `no_clipping` | No text at page edge | `edge_clip` issue |
| `no_orphan_headings` | Heading not stranded at page foot | `heading_orphan` |
| `page_fill` | No empty / half-empty pages | `empty_page` / `sparse_page` |
| `metadata` | Title/author/subject/keywords present | `metadata` |
| `language` | `/Lang` set | `no_lang` |
| `tagged` | `StructTreeRoot` present | `no_tags` |
| `outline` | TOC entries ≥ 2 | `no_outline` |
| `image_resolution` | Effective DPI ≥ 150 | `image_dpi` |
| `no_duplicate_images` | No identical hashes on different pages | `duplicate_image` |
| `credits` | Credits block when images present | `missing_credits` |

Also reported: body size vs declared (`body_size`), smallest used (`min_font`), image count / dimensions / displayed size, page fill %, orientation.

Previews rendered to PNG (`max_previews`, `preview_dpi`); inspect with the image-reading tool.

---

## CLI reference

```bash
# Build
python -m pdfstudio build input.md [-o out.pdf] [-s SCENARIO] [-t THEME]
    [--art-direction D] [--copy-policy strict|warn|off] [--title T]
    [--page-size A4|Letter...] [--landscape|--portrait]
    [--toc|--no-toc] [--cover|--no-cover] [--engine auto|playwright|weasyprint]
    [--images auto|off] [--preview-pages N] [--no-preview] [--no-stamp]
    [--no-bookmarks] [--keep-html] [--no-contrast] [--strict] [--css FILE...]

# Measure finished PDF
python -m pdfstudio check out.pdf [--source input.md]
    [--body-size PT] [--min-font PT] [--measure CH] [--cover-pages N]
    [--previews DIR] [--pages N] [--json]

# Image review (visual selection before pinning)
python -m pdfstudio images "query" [--out sheet.jpg] [--count 12] [--columns 4]

# Copy quality
python -m pdfstudio copycheck input.md [--locale en-GB|en-US]

# Discovery
python -m pdfstudio scenarios | themes | designs | directions
python -m pdfstudio inspect file.pdf [--previews DIR] [--pages N] [--json]
```

---

## Verification commands (run after every build)

```bash
python -m pdfstudio build examples/crocs-plan.md --out out/crocs-plan.pdf --preview-pages 18
python -m pdfstudio check out/crocs-plan.pdf --source examples/crocs-plan.md
python -m pdfstudio copycheck examples/crocs-plan.md --locale en-GB
# Look at out/.pdfstudio/previews/*.png before reporting done
```

---

## Design-taste rules enforced

- No generic template output; cover earns the first page, not just a title over a photo.
- Typography: display weight 400/600, letter-spacing `-0.05em`, body measure `68ch`, line-height `1.45`.
- Colour: palette from theme, not random; accent used for badges / page numbers / rules.
- No em dashes in content or filenames; no emoji; no replacement characters.
- Numbers in charts / metrics, not hidden in prose.
- Every image credited; every figure numbered; every page has a purpose.

---

## Dependencies

Python 3.10+, Playwright with Chromium, PyMuPDF (`fitz`), matplotlib, Pillow, requests, Jinja2, markdown. Optional: WeasyPrint (if Chromium unavailable — expect weaker layout), PyYAML.

Fonts bundled in `assets/fonts/` (Clash Grotesk, Manrope, Fraunces, Source Serif 4, Space Grotesk, Barlow) so charts and margin boxes load the real font, not Helvetica fallback.

---

## License

MIT. Skill is standalone; it produces the PDF, it does not claim the content.
