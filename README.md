# PDF Studio

**Design-first PDF generation — Markdown / JSON / HTML → art-directed, print-ready PDF.**

> *A PDF is a design artifact, not a printout of a text file.*
> Build, look at the pages, fix what is wrong, rebuild. The QA loop *is* the skill.

---

## What it produces

A finished PDF that reads like it was composed by hand:

| Artifact | Detail |
|---|---|
| **Cover** | Named `@page cover` (zero margin), bounded photograph + solid text fields so type never collides with busy imagery |
| **TOC** | Real page numbers via a two-pass scan that rebuilds if content shifts |
| **Body chapters** | Full-bleed, full-height colour fields, 12pt body, 68ch measure, running header/footer at 9pt in brand font |
| **Charts** | Brand-font loaded, horizontal labels when long, direct value labels, legend outside plot, `Fig. N` numbering |
| **Images** | Sourced from Wikimedia Commons / Wikipedia / Openverse, throttled & retried, cached, embedded as base64 data URIs, credited automatically |
| **Credits block** | Assembled from every embedded image — no manual photo credits |
| **Back cover** | Dedicated image, never the cover photo reused |
| **Tagged PDF** | `StructTreeRoot`, `MarkInfo`, `Lang`, outline, `PageMode=/UseOutlines` — preserved via single-document Chromium → PyMuPDF finalize (`garbage=3`) |

**Verified example** (Crocs 12-Month Growth Plan, rebuilt after upgrade): 18 pages, 8,384 chars, 8 images at 300 dpi, body 12.0pt, smallest 9pt, measure 73 chars/line, `lang=en`, tags yes, outline 10, metadata complete.

---

## Quick start

```bash
# Build with previews
python -m pdfstudio build examples/crocs-plan.md \
    --out out/crocs-plan.pdf --preview-pages 18 --keep-html --strict

# Measure the finished PDF against declared design intent
python -m pdfstudio check out/crocs-plan.pdf --source examples/crocs-plan.md

# Build an image-candidate sheet before pinning any photograph
python -m pdfstudio images "crocs retail display" --out out/candidates.jpg

# Copy gate with locale enforcement
python -m pdfstudio copycheck examples/crocs-plan.md --locale en-GB
```

---

## 🎨 Design systems (themes)

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

Themes inject CSS custom properties (`--font-body`, `--font-display`, `--ink`, `--accent`, `--measure`, `--page-margin`); templates stay theme-agnostic.

---

## 📄 Scenarios

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

## 🎯 Art directions

9 directions control cover mood + body composition: `object-playful` (Crocs), `editorial-contrast`, `quiet-luxury`, `technical-field`, `industrial-machine`, `institutional-clarity`, `organic-human`, `scholarly-book`, `essential-minimal`. Set explicitly (`art_direction: object-playful`) or inferred from topic.

---

## 📝 Source format

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
cover_caption: "Colourful Crocs clogs and sandals decorated with Jibbitz charms."
toc_title: "The plan at a glance"
page_size: A4
back_cover:
  title: "Come back for comfort."
  text: "Start with the people who already love the product..."
  contact: "Brand Strategy Team"
---
```

Content blocks (pre-processed before Markdown conversion):

- **Metric row** — `Label | Value | delta`
- **SWOT** — 2×2 matrix
- **Chart** — `bar`, `line`, `stacked`, `pie`, `donut`, `area`
- **Callouts** — `> [!NOTE]`, `> [!KEY]`, `> [!ACTION]`, `> [!WARNING]`
- **Images** — `![alt](search:description)`, `img:path`, URL, or `search:commons:Exact File.jpg`
- **Page breaks** — `<div class="page-break"></div>` or `## Heading {.no-toc}`

---

## 🖼️ Image sourcing (upgraded)

- **Providers**: Wikimedia Commons (primary) → Wikipedia media → Openverse fallback
- **Throttled uploads** at `upload.wikimedia.org` (1.5s gap) with 4 retries + backoff
- **Relevance ranking** via synonym groups (`shoe`↔`footwear`↔`clog`) + zero-match penalty — unrelated high-res photos can't win
- **Dedupe** — `avoid=` prevents reusing the cover photo in the body
- **Contact sheet** — `contact_sheet()` renders thumbnails with index / title / dimensions / licence for visual verification before pinning
- **Exact pinning** — `search:commons:Israel Batch 1 (640).JPG` locks the exact file; later searches cannot drift

Every embedded image lands in an automatic credits block; missing credits trigger a QA error.

---

## 📊 Charts (`charts.py` — rebuilt)

- Brand font loaded via explicit `FontProperties(fname=...)` — avoids Clash Grotesk 400's "false" family-name bug
- **Horizontal bars** auto-applied when category labels exceed 13 characters
- **Direct value labels** on every bar / point
- **Legend** placed below plot (`bbox_to_anchor=(0.0, 1.01)`), never over data
- **Figure captions**: `<span class="figure__num">Fig. N</span> Title`
- No "Illustrative" in chart titles; one planning-assumptions note added

---

## 🔍 Contrast (`contrast.py` — isolated fix)

Chromium probe measures WCAG ratio against the **actual pixels behind each glyph**:

- **Non-display text** (body, caption, label, credit): isolated solid-field CSS scoped to the exact selector — only that element changes
- **Display text** (headlines, cover title): reported, not auto-patched — composition change required (solid field / bounded photo / crop)

`build` applies `fix_css` automatically; `check` reports remaining clashes.

---

## 🔧 Pipeline (`render.py` — single document)

1. **Cover + body in one HTML** (not merged PDFs) — preserves `StructTreeRoot`
2. **Named pages**: `@page cover` (zero margin, no running furniture) + `@page` (margin-box header/footer at 9pt brand font)
3. **`html, body { overflow: hidden }`** — restores real 12pt / 48pt sizes (fixes silent 9.4% Chromium shrink when one element overflows the page)
4. **Full-bleed**: `width: var(--page-w); margin-left: -18mm; min-height: var(--inner-h)` — tested at 48.0pt H1
5. **Chapter wrapping** → `.chapter` sections with `break-before: page`
6. **Two-pass TOC**: pass 1 renders; `fitz` scans heading pages; pass 2 injects page numbers; rebuilds if page counts shift
7. **Finalize**: `fitz.set_metadata`, `set_toc`, `Lang`, `PageMode=/UseOutlines`, save `garbage=3`

---

## 🧪 Measurable QA gates (`qa.py`)

`analyze()` measures, does not guess. Structured `issues` + boolean `gates`:

| Gate | Fail condition |
|---|---|
| **type_floor** | Any text below declared size (default 9pt floor) |
| **measure** | Body line length outside target ±24ch |
| **no_clipping** | Text touches page edge |
| **no_orphan_headings** | Heading stranded at page foot |
| **page_fill** | Empty / half-empty spill pages |
| **metadata** | Missing title / author / subject / keywords |
| **language** | `/Lang` not set |
| **tagged** | `StructTreeRoot` missing |
| **outline** | TOC entries < 2 |
| **image_resolution** | Effective DPI < 150 |
| **no_duplicate_images** | Identical image hash on multiple pages |
| **credits** | Images present but no credits block |

`check` aggregates into a human-readable report; `--strict` exits non-zero on error-level failures.

---

## 🖥️ CLI reference

```bash
# Build
python -m pdfstudio build INPUT [-o OUT] [-s SCENARIO] [-t THEME]
    [--art-direction D] [--copy-policy strict|warn|off] [--title T]
    [--page-size SIZE] [--landscape|--portrait]
    [--toc|--no-toc] [--cover|--no-cover]
    [--engine auto|playwright|weasyprint] [--images auto|off]
    [--preview-pages N] [--no-preview] [--no-stamp] [--no-bookmarks]
    [--keep-html] [--no-contrast] [--strict] [--css FILE...]

# Measure finished PDF
python -m pdfstudio check FILE.pdf [--source INPUT.md]
    [--body-size PT] [--min-font PT] [--measure CH] [--cover-pages N]
    [--previews DIR] [--pages N] [--json]

# Image review (visual selection before pinning)
python -m pdfstudio images "query" [--out SHEET.jpg] [--count N] [--columns N]

# Copy quality
python -m pdfstudio copycheck INPUT.md [--locale en-GB|en-US]

# Discovery
python -m pdfstudio scenarios | themes | designs | directions
python -m pdfstudio inspect FILE.pdf [--previews DIR] [--pages N] [--json]
```

---

## ✅ Verification loop (mandatory)

```bash
python -m pdfstudio build doc.md --out out/doc.pdf --preview-pages 12 --strict
python -m pdfstudio check out/doc.pdf --source doc.md
python -m pdfstudio copycheck doc.md --locale en-GB
# Inspect out/.pdfstudio/previews/*.png after the final build
```

**Never ship the first render.** Rebuild until previews pass all gates.

---

## 📦 Dependencies

Python 3.10+, Playwright + Chromium, PyMuPDF (`fitz`), matplotlib, Pillow, requests, Jinja2, markdown. Fonts bundled in `assets/fonts/` (Clash Grotesk, Manrope, Fraunces, Source Serif 4, Space Grotesk, Barlow) so charts and margin boxes render with exact typefaces — no Helvetica fallback.

---

## 📜 License

MIT.

---

*PDF Studio: build once, look at the pixels, fix what's wrong, rebuild.*
