---
name: pdf
description: >
  Design-first PDF generation. Turns Markdown, JSON, or HTML into
  art-directed, print-ready PDFs with a real design system per document type
  (marketing plan, report, proposal, whitepaper, invoice, resume, one-pager,
  case study, brochure, academic paper, certificate, newsletter, portfolio,
  pitch deck). Includes web image sourcing with attribution, generated charts,
  metric callouts, SWOT matrices, two-pass table of contents with page numbers,
  PDF bookmarks, and a preview-based QA loop. Use this skill whenever the user
  asks for a PDF, a report, a marketing plan, a proposal, a deck, a resume, a
  certificate, a printable document, or wants a document typeset rather than
  dumped. Also trigger on "export to PDF", "make this look designed", "build a
  PDF from my notes", or any request where the deliverable is a document file.
license: MIT
compatibility: >
  Requires Python 3.10+, Playwright with Chromium, PyMuPDF, matplotlib, Pillow,
  requests, Jinja2, markdown. Optional: PyYAML, pypdf, WeasyPrint.
---

# PDF Studio

A PDF is a design artifact, not a printout of a text file. This skill produces
documents that look art-directed: a cover that earns the first page, a grid that
holds up across pages, typography with hierarchy, data shown as data, images
that support claims, and a contents page that actually helps.

**The one rule: never ship the first render.** Build, look at the page images,
fix what is wrong, rebuild. The QA loop is the skill.

---

## 1. Start here

```bash
cd <skill-dir>
python -m pdfstudio build input.md --out out/document.pdf --preview-pages 8
python -m pdfstudio check out/document.pdf --source input.md --previews out/qa
```

`build` prints a QA summary and writes PNG previews to
`out/.pdfstudio/previews/`. `check` re-measures a finished PDF against the
declared type size, measure, margins, image resolution, metadata, language, and
tagging, and exits non-zero when an error-level gate fails. Read the preview
images with the image-reading tool before you report success. If the previews
look wrong, they are wrong.

Discover what is available:

```bash
python -m pdfstudio scenarios    # 14 document types, with defaults
python -m pdfstudio themes       # 11 design systems
python -m pdfstudio designs      # which theme to use where
python -m pdfstudio inspect out/document.pdf --previews out/qa --pages 12
python -m pdfstudio images "crocs retail display" --out out/candidates.jpg
```

---

## 2. Ask before you build

If the brief leaves a real decision open, ask. Do not pad the build with
assumptions the reader will notice. If the harness exposes a question tool
(`question`, `ask_user`, `AskUserQuestion`, or similar), **call it**. Do not
print questions as prose and wait: a prose question usually stalls the task.
Offer a short multiple-choice list and let the tool add the custom answer.

Ask at most **three** questions before the first build. Prefer questions whose
answers change the design, not the wording:

| Decision | Question type | Example options |
|---|---|---|
| Purpose | Single choice | persuade / explain / report / sell / comply |
| Audience | Single choice | board / client / customer / students / public |
| Length | Single choice | 2 pages / 6-10 / 15-25 / as long as needed |
| Tone | Single choice | playful / authoritative / warm / austere / technical |
| Visual direction | Single choice | bold type / photo-led / data-led / quiet editorial / let me choose |
| Must include | Multiple choice | numbers / charts / photographs / quotes / legal copy |
| Brand | Single choice | use these colours / neutral palette / supplied assets |
| Locale | Single choice | UK English / US English / another |

Use a multi-select question for "what must be included" and a single-select
question for everything else. If the user supplied a complete brief, skip this
section and build.

---

## 3. The workflow

1. **Decide the document type.** Pick a scenario from the table in section 5.
   A scenario sets the page size, orientation, cover style, TOC, layout,
   running header/footer, and a default design system.
2. **Ask the three questions that matter** (section 2), if they are still open.
3. **Write the source.** Markdown with YAML frontmatter. Structure beats prose:
   one idea per section, tables for comparisons, charts for trends, a metric
   row for the numbers that matter.
4. **Source images deliberately.** Use `![alt](search:plain description)`.
   One or two images per document is usually right; five is a photo essay.
   Every image must support a claim in the text. Review candidates visually
   before pinning a file (section 4).
5. **Build with previews.** `--preview-pages` should cover the whole document
   for anything under 15 pages.
6. **Run `check`.** It measures real type sizes, line measure, clipping,
   orphan headings, page fill, metadata, tagging, image DPI, duplicates, and
   credits. Fix errors before you look at aesthetics.
7. **Look at every preview.** Check cover, TOC page numbers, page breaks,
   table alignment, chart legibility, contrast, orphan headings, and the back
   cover.
8. **Iterate.** Fix content or CSS, rebuild, re-check, re-look. Two passes
   minimum.
9. **Report the result.** Give the absolute path, the page count, and one line
   on what the document contains, plus the measured result.

If the user gives you a topic rather than a file, write the content first. A
beautiful PDF of thin content is still a thin document.

---

## 4. Source format

### Frontmatter

```yaml
---
title: "Brew & Bloom"
subtitle: "A 12-Month Marketing Plan"
author: "Your Name"
org: "Northfield Business School"
client: "Brew & Bloom Ltd."
date: "November 2026"
version: "1.0"
eyebrow: "Marketing Plan"        # small label above the title on the cover
kicker: "Strategic Marketing Planning"
summary: "One sentence that sells the document."
theme: modern-saas               # design system id
scenario: marketing-plan         # document type id
confidential: "Confidential"     # optional cover badge
website: "brewandbloom.example"
toc_title: "Contents"
toc_depth: 2                     # 1-3 heading levels in the TOC
page_size: A4                    # A3 A4 A5 Letter Legal Tabloid
landscape: false
back_cover:
  title: "Ready to brew something bigger?"
  text: "A short closing paragraph."
  contact: "hello@example.com"
---
```

Scenario and theme can also be set on the command line with `-s` and `-t`.
Command-line values win. If frontmatter is absent the document still builds with
sensible defaults.

### Content blocks

These are extracted before Markdown conversion, so they render reliably.

**Metric row** - 3 to 5 numbers, no more. `Label | Value | delta`

````markdown
```metrics
Monthly recurring revenue | £18,400 | target
Active subscribers | 640 | target
Churn (monthly) | 4.2% | -1.8pts
```
````

**SWOT** - renders as a 2x2 matrix, not a table.

````markdown
```swot
Strengths | Roastery ownership; Repeat footfall; Origin story
Weaknesses | Low awareness; No email list; Single-product site
Opportunities | Subscription growth; Corporate gifting; Office wholesale
Threats | Price cuts; Bean volatility; Delivery costs
```
````

**Charts** - `line`, `bar`, `stacked`, `pie`, `donut`, `area`.

````markdown
```chart bar
title: Budget allocation by channel (£000s)
Email & CRM | 6
Content & photography | 5
Paid social | 9
```
````

Add a header row to name series (needed for stacked charts):

````markdown
```chart stacked
title: Subscriber growth by segment
Quarter | Local | Gift | Remote
Q1 | 40 | 25 | 15
Q2 | 95 | 60 | 55
```
````

Charts are generated with matplotlib in the document's palette. Never put a
chart's numbers only in prose - if the reader should compare values, chart them.

**Callouts** - five types, each with a distinct colour and weight.

```markdown
> [!KEY] The one-sentence strategy
> Sell the habit, not the bag.

> [!INSIGHT] What the data says
> ...
> [!ACTION] Owner and date
> ...
> [!WARNING] Trigger for a rethink
> ...
> [!NOTE] Sidebar
> ...
```

**Images**

```markdown
![Speciality coffee being poured](search:speciality coffee pour over cafe)
![Our roastery](img:assets/photos/roastery.jpg)
![A specific photograph](https://example.com/photo.jpg)
```

Search queries should describe the *photograph*, not the concept: "coffee
roastery interior" finds better images than "authenticity". Sourced images are
licensed, credited, cached, and embedded, and a credit block is added
automatically at the end of the document.

**Review images before you pin them.** A title match is not a visual match.
Build a contact sheet, look at it, then pin the exact file:

```bash
python -m pdfstudio images "crocs retail display" --out out/candidates.jpg
```

The sheet prints an index, title, dimensions, and licence under each thumbnail.
When you have chosen, pin the exact Commons filename so a later search cannot
drift to a different photograph:

```markdown
![Purple Crocs retail display](search:commons:Israel Batch 1 (640).JPG)
```

Rules that prevent the usual image failures:

- Review the sheet at full size. Check the subject, not just the filename.
- Do not reuse one photograph for the cover and the back cover.
- Do not use a photograph whose caption promises something it does not show.
- Every image needs a caption that says what the reader is looking at.
- Add `cover_image` and `cover_caption` in frontmatter for the cover; the body
  search will not reuse it.

**Page control** - `<div class="page-break"></div>`, or `## Heading {.no-toc}`
to keep a heading out of the contents page.

---

## 5. Scenarios

| id | Use for | Default design | Pages / layout |
|---|---|---|---|
| `report` | Annual reports, research reports | Editorial | A4, full cover, TOC |
| `marketing-plan` | Marketing and business plans | Modern SaaS | A4, split cover, TOC, cards |
| `proposal` | Client proposals, bids | Luxury | A4, minimal cover, TOC |
| `invoice` | Invoices, quotes, receipts | Minimal | A4, no cover, footer only |
| `whitepaper` | Technical and thought-leadership papers | Academic | A4, full cover, TOC |
| `case-study` | Customer stories, results write-ups | Modern SaaS | A4, image cover |
| `resume` | Resumes and CVs | Minimal | Letter, no cover/header/footer |
| `one-pager` | Decision briefs, product one-pagers | Swiss Grid | A4, two columns |
| `academic` | Essays, dissertations, papers | Academic | Letter, TOC |
| `brochure` | Service brochures, programmes | Vibrant | A4, image cover, cards |
| `certificate` | Certificates and awards | Luxury | A4 landscape, framed |
| `newsletter` | Internal and community newsletters | Editorial | A4, two columns |
| `portfolio` | Design and photography portfolios | Minimal | A4, image cover, cards |
| `pitch-deck` | Slide-style decks | Modern SaaS | A4 landscape, cards |

## 6. Design systems

| id | Mood | Good for |
|---|---|---|
| `editorial` | Serif, generous, print | Reports, newsletters, long reads |
| `swiss` | Grid, Helvetica discipline | One-pagers, data-heavy briefs |
| `modern-saas` | Clean, indigo accent, cards | Plans, case studies, decks |
| `luxury` | High-contrast serif, gold, cream | Proposals, certificates |
| `academic` | Restrained, footnote-friendly | Papers, whitepapers |
| `brutalist` | Raw type, harsh rules | Manifestos, culture decks |
| `minimal` | Quiet, lots of white | Resumes, portfolios |
| `corporate` | Navy, steady, conservative | Board papers, finance |
| `warm-sage` | Earthy, calm, human | Sustainability, wellness |
| `midnight` | Dark cover, luminous accents | Launch decks, tech |
| `vibrant` | Saturated, energetic | Brochures, campaigns |

A theme changes tokens: palette, fonts, spacing scale, radius, rules, cover
treatment, and chart colours. Changing one thing changes the whole document.

---

## 7. Making it specific to the document

Generic output is the failure mode. Do these before building:

- **Write a real title.** "Q3 Marketing Plan: Brew & Bloom" beats "Marketing Plan".
- **Choose the theme for the audience.** A bank proposal is not `vibrant`.
- **Use the metrics block once**, near the top, with the numbers the reader came for.
- **Use exactly one chart type per idea.** Do not put three bar charts in a row.
- **Break the grid once.** A full-width image or a pull quote stops a document
  from reading as a template.
- **Write the back cover.** It is the last thing read and the easiest page to forget.

For per-document design changes, drop a CSS file next to the source and pass
`--css custom.css` (see section 9) or edit `assets/css/overrides.css` for a
reusable change. Add a `body[data-scenario="..."]` selector to scope it.

---

## 8. QA loop (mandatory)

```bash
python -m pdfstudio build doc.md --out out/doc.pdf --preview-pages 12
python -m pdfstudio check out/doc.pdf --source doc.md --previews out/qa
python -m pdfstudio copycheck doc.md --locale en-GB
```

`check` measures the finished PDF. It fails on:

- body text smaller than the size the design declares
- any text below 9pt
- body lines far outside the declared measure (default 68 characters)
- text clipped by the page edge
- headings stranded at the foot of a page
- empty or half-empty spill pages
- missing title, author, subject, keywords, `/Lang`, structure tree, or outline
- images below 150 effective dpi, tiny images, and duplicate photographs
- photographs without a credits block

Then inspect `out/qa/*.png` (or `out/.pdfstudio/previews/*.png`). Checklist:

- Cover: title fits, no text over a busy photograph, metadata aligned.
- Contents: page numbers present and correct, depth sensible, no orphan entries.
- Body: no heading stranded at the bottom of a page, no table split mid-row,
  no figure separated from its caption.
- Charts: labels legible and horizontal, values labelled directly, legend clear
  of the plot, figure numbers in document order.
- Images: relevant to the caption, not stretched, credits present, no duplicate.
- Contrast: every caption and label readable against what is behind it.
- Back cover: present, not an empty page, not the cover photograph again.
- Last page: not a nearly-empty page caused by a trailing element.

### Contrast

The build runs a Chromium probe that finds text over images and strong colour
fields, measures WCAG contrast against the pixels actually behind the glyphs,
and appends a scoped CSS fix for non-display text. Display type is reported, not
patched: move the headline or give it a solid field, do not shrink it.

If `check` or the build reports a contrast issue:

1. Read the selector and the text in the report.
2. For body copy, captions, labels, and credits, let the scoped fix apply and
   rebuild. Confirm the same selector is no longer listed.
3. For a headline or cover title, change the composition: a solid text column,
   a bounded photograph, or a different crop. Never simply add a dark panel
   behind display type.
4. Re-run the build and `check`. A fix that changes page flow may create a new
   overlap; re-probe rather than assuming.

### Verify the render, not the source

```bash
python -m pdfstudio check out/doc.pdf --source doc.md --json > out/qa.json
```

Read `fonts.body_pt`, `fonts.min_used_pt`, `fonts.line_chars`, `structure.lang`,
`structure.struct_tree`, `structure.outline_entries`, `gates`, and
`image_details`. If body text is smaller than declared, look for an element
wider than the page: Chromium scales the whole document down to fit one
overflowing box. Fix the box, not the font.

When something is wrong, fix the cause, not the symptom: adjust content length,
move a block, tune one CSS rule, then rebuild. Rebuilding is fast.

---

## 9. CLI reference

```
python -m pdfstudio build INPUT [-o OUT] [-s SCENARIO] [-t THEME]
    [--art-direction DIRECTION] [--copy-policy strict|warn|off]
    [--title TITLE] [--page-size SIZE] [--landscape|--portrait]
    [--toc|--no-toc] [--cover|--no-cover]
    [--engine auto|playwright|weasyprint]
    [--images auto|off]
    [--preview-pages N] [--no-preview]
    [--no-stamp] [--no-bookmarks] [--keep-html]
    [--no-contrast] [--strict] [--css FILE ...]

python -m pdfstudio check FILE.pdf [--source SOURCE.md]
    [--body-size PT] [--min-font PT] [--measure CH]
    [--cover-pages N] [--previews DIR] [--pages N] [--json]

python -m pdfstudio images "query" [--out SHEET.jpg]
    [--count N] [--columns N]

python -m pdfstudio copycheck FILE.md [--locale en-GB|en-US]
python -m pdfstudio themes | scenarios | designs | directions
python -m pdfstudio inspect FILE.pdf [--previews DIR] [--pages N] [--json]
```

Useful flags:

- `--strict` makes `build` exit non-zero when the measured QA gates fail.
- `--no-contrast` skips the contrast probe for a deliberately low-contrast
  display composition. Do not use it to hide a body-copy problem.
- `--keep-html` writes the intermediate HTML next to the PDF. Use it when a CSS
  change needs live iteration.
- `--images off` for offline builds, certificates, and invoices.
- `--engine weasyprint` only if Chromium is unavailable; expect weaker layout.

---

## 10. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Body text is ~9% smaller than declared | One element is wider than the page, so Chromium scales the document | Find the overflowing box, constrain it (`max-width`, `min-width: 0`), keep `overflow: hidden` on `html, body` |
| Content overflows into the margin band | Element taller than the page area | Shorten the block, or reduce its font size via a scoped CSS rule |
| Text is unreadable over a photo | No solid field behind the words | Move the text, bound the photo, or use the scoped contrast fix for body copy |
| Image placeholder says "Image unavailable" | Search returned nothing usable | Use a simpler, more literal query; or supply `img:` / a direct URL |
| Sourced photo is irrelevant | The query was abstract, or ranking rewarded size | Review the contact sheet and pin `search:commons:<exact file>` |
| Chart labels overlap | Long category names | The renderer switches to horizontal bars past 13 characters; shorten labels or use fewer series |
| TOC page numbers wrong | Content shifted between passes | Rebuild; the two-pass scan re-reads the final PDF |
| Page number duplicated in the TOC | Heading text repeated on another page | Make the heading unique, or set `toc_depth: 1` |
| Blank page at the end | Trailing break or margin collapse | Remove the trailing blank line or `page-break` |
| Table split badly | More than 9 rows | Expected: long tables split with repeating headers, or shorten |
| Metadata is empty | A merge or export path dropped it | Finalize with PyMuPDF `set_metadata` and save with `garbage=3`; do not merge PDFs with pypdf |
| PDF is not tagged | A merge or intermediate save dropped `StructTreeRoot` | Render cover and body as one Chromium document; avoid merging |
| Font missing / fallback | Custom font not installed | Use theme fonts, or embed via `@font-face` in a custom CSS file |

---

## 11. Definition of done

- [ ] The PDF opens and every page has a purpose.
- [ ] The cover names the document and the reader, not just the topic.
- [ ] Contents page numbers are correct, or there is deliberately no TOC.
- [ ] Numbers appear as metrics or charts, not only in sentences.
- [ ] Images are relevant, credited, and not stretched.
- [ ] No blank, stranded, or half-empty pages.
- [ ] Headers, footers, and page numbers are consistent.
- [ ] Previews were inspected after the final build.
- [ ] `check` reports body type at the declared size, text at or above 9pt,
      and a line measure inside the target range.
- [ ] `check` reports `/Lang`, a structure tree, and an outline.
- [ ] Contrast was probed after the final build and every issue is fixed or
      deliberately accepted.

Deliver with the absolute output path and a short statement of page count,
contents, and the measured result. Do not claim the document is finished before
looking at it.
