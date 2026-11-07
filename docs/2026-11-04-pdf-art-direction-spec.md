# PDF Studio: art-direction and layout overhaul

Status: **proposal for review; production implementation not started**.

## Outcome

PDF Studio has useful rendering infrastructure, but its current art-direction layer actively collapses theme choices and reuses a narrow component/layout vocabulary. The requested improvement is not another palette pack. It is a reliable design contract that makes composition respond to the subject, audience, purpose, content and reviewed assets while preserving readable, print-safe documents.

This investigation used the source in this workspace, four controlled renders and an isolated Chromium page-paint probe. It does not claim to have inspected David's historical PDFs or the implementation of every installed copy of the skill.

## Verified findings

| Problem | Evidence | Consequence |
|---|---|---|
| Explicit themes are overwritten | `pdfstudio/render.py:737–744` always invokes `infer_direction` and `apply_direction`; `pdfstudio/art_direction.py:300–319` replaces fonts, palette, radius, body size, measure and cover style | Explicit `modern-saas`, `luxury` and `warm-sage` all resolved to `technical-field`, `#10151D`, Space Grotesk display and zero radius in the controlled software brief |
| Topic detection misreads ordinary words | `pdfstudio/art_direction.py:273–297` uses substring matching; technical keywords include `ai` | Executed title-only probes classified “Retail launch”, “Chair catalogue”, “Portrait collection” and “Local repairs” as technical |
| Body backgrounds stop at page margins | `pdfstudio/render.py:200–212,280–294` declares body margins and only zeroes the cover; `assets/css/directions.css:348–363` paints inner-sized chapters | Measured body margins: top 20mm, right 18mm, bottom 22mm, left 18mm. Body edge samples were white even when the page field was dark or lavender |
| Many theme decorations do not match generated headings | `pdfstudio/render.py:478–480` wraps headings in `.chapter`; `assets/css/overrides.css` frequently selects `.content > h2` | Heading treatments advertised by themes can be bypassed; direction styles become dominant |
| Components share a narrow visual grammar | `assets/css/base.css:277–284,322–378`; `pdfstudio/content.py:270–309,332–397`; `assets/css/directions.css:807–872` | Metrics, SWOT and callouts default to panel rectangles with perimeter/edge accents. Removing borders often leaves the same panel layout |
| Asset sourcing happens after design selection | `pdfstudio/render.py:743–744,769–774`; `pdfstudio/images.py:54–69,84–104,721–747` | Actual aspect ratio, focal point, transparency and image role cannot select composition. A nominal “dominant” colour is a 1-pixel average, not a reviewed palette; alpha is flattened to white |
| Most directions are skins, not full compositions | `assets/css/directions.css:767–872`; compare the richer object-playful rules at `:284–633` | Most families vary heading sizes and fills. One direction has substantially more bespoke layouts, some keyed to English marketing section names |
| Technical QA is not design QA | `pdfstudio/qa.py:365–430,637–655` | Page-fill gates passed for all controlled cases despite large unused lower-page fields. Three technical cases also failed the existing 9pt type floor; they are not finished documents |

### Controlled evidence

- `out/design-audit/reproduce.py` generates identical body content under three explicit themes and a fourth explicit playful direction; no image searches or network assets were used.
- `out/design-audit/evidence.json` records selected tokens, page counts, edge pixels, keyword probes and existing QA results.
- `out/design-audit/baseline-comparison.png` shows the first body page of each case. The first three are nearly the same design; the playful case is structurally different but retains the white frame.
- The A4 area outside the 174mm × 255mm content rectangle is **28.86%** of the sheet. This is a geometric measurement, not an argument to eliminate readable text margins.
- Four controlled documents produced 13 pages in total. They are audit baselines, not polished deliverables. The image-related gates are not evidence of asset quality because these fixtures contain no images.

### Page-paint capability verified locally

`out/design-audit/geometry_probe.py` compares CSS `@page` background, a negative-offset fixed element and painted margin boxes. After removing a probe-only empty element, every case had exactly three nonblank pages.

The installed Chromium painted `@page` backgrounds across all eight sampled edge/corner points on body and continuation pages while keeping the text's left bound at 51pt (approximately 18mm). The negative-offset fixed layer did not paint the margins. Margin-box painting worked but showed visible seams in its preview.

**Preferred implementation:** named-page `@page` backgrounds with independently configured text-safe margins. Keep this under a Chromium render regression, including continuation pages, headers and mixed page fields. The probe establishes feasibility here; it is not a universal claim about old browsers or WeasyPrint.

## Goals and anti-goals

1. Explicit theme, brand and direction decisions must survive automatic inference.
2. Different subjects and purposes must be capable of producing different compositions, not only different colours.
3. Full-field pages must paint the physical sheet while keeping prose, captions and furniture safely inset.
4. Normal content must not be put in cards by default. Enclosures must have a reason.
5. Reviewed images and diagrams must change placement, crop and surrounding layout when their roles warrant it.
6. Every selected design must have an explanation and observable QA evidence.

Do not replace repetition with randomness. Do not force full-bleed design onto invoices, scholarly papers or home-print documents. Do not fill short pages with decoration to satisfy a numeric score. Do not invent metrics, charts, SWOTs or photographs because a template expects them. Do not build one hardcoded stylesheet per topic or silently use a paid vision model.

## Global constraints

- Retain Python 3.10+, Chromium via Playwright, Jinja2, PyMuPDF, Pillow and matplotlib; add no required dependency or paid service.
- Keep Windows execution PowerShell-compatible; use Python UTF-8 file I/O for generated content.
- Preserve existing Markdown, JSON and HTML input paths and existing CLI theme/scenario IDs.
- Preserve one-document Chromium rendering, selectable text, `/Lang`, structure tree, metadata, bookmarks, correct two-pass TOC numbers and source credits; do not merge rasterised pages.
- Require every used text span, including captions, chart labels and running furniture, to be at least 9pt; body text must remain at or above its declared design size.
- Default print text-safe inset: top 20mm, right 18mm, bottom 22mm, left 18mm. Default digital text-safe inset: 16mm on all sides. Explicit user/brand requirements win.
- A full-page field is page paint, not a request to place prose at the physical edge. Crop and trim bleed for commercial printers are out of scope.
- No production code or installed skill copies change until the spec and plan are approved.

## Design contract

### Independent layers

Separate five decisions:

1. **Scenario:** functional document requirements—paper, orientation, cover/TOC, numbering and conventions.
2. **Theme:** palette, type, rules and brand tokens.
3. **Composition family:** content/asset organisation and page rhythm.
4. **Component presentation:** the right treatment for a metric, quote, warning, comparison or timeline.
5. **Output mode:** print-safe or digital field treatment; independent of colour theme.

Keep the current art-direction IDs as compatibility aliases to composition families and suggested themes. Explicit legacy direction selection remains supported. The new default is to resolve a theme first and a composition independently. Existing `--css` remains an intentional final override, reported as custom rather than silently treated as a built-in preset.

### Precedence and explainability

- For each explicit field: CLI override → frontmatter → authored design brief → inference → scenario default.
- An explicit theme locks its palette, font families and base token values against automatic direction changes. Scenario rules may still enforce functional constraints such as orientation or no cover.
- An explicit direction sets composition. Its suggested theme applies only when no theme/brand was explicitly selected.
- Asset-based accent suggestions are opt-in. They never override brand colours or locked explicit tokens.
- Invalid explicit theme, scenario, family or direction IDs fail with supported choices; do not silently substitute something unrelated.
- Match complete Unicode word tokens or boundary-delimited phrases, not arbitrary substrings. Title/industry/purpose are stronger evidence than generic body vocabulary. Document-type labels are not subjects.
- Low-evidence or tied recommendations retain a neutral scenario-appropriate composition and explain ambiguity; dictionary order must not silently decide taste.
- Write a `design.json` manifest beside the PDF recording requested choices, effective choices, lock provenance, reasons, asset roles, section treatments and QA-relevant geometry. No data URIs or downloaded image bytes in this manifest.

### Authored brief

The agent authors a concise brief from the supplied source before rendering: subject, audience, purpose, visual argument, medium, family and why, asset roles, sections deserving feature treatment, and anti-patterns to avoid. Unknown facts stay unknown. Only ask the user about actual missing high-impact inputs; do not require a mood questionnaire when the brief is already complete.

Optional frontmatter extends the existing format with `composition`, `output_mode` and a `design` mapping. `design.assets` keys reference existing image request slots or the reserved `cover`/`back_cover` requests; values describe role, approved crop, focal point, fit and whether a derived accent is permitted. An approved crop is a normalised `(x0,y0,x1,y1)` source rectangle with `0 <= x0 < x1 <= 1` and `0 <= y0 < y1 <= 1`; no crop means the full source. The focal point must lie inside it. `design.sections` keys are explicit stable heading IDs, not translated heading text; each value has `role: flow|opening|feature|closing` and an optional `field: bg|panel|accent`. A renamed heading retains its authored ID. Unknown slot/heading references and invalid enums fail validation rather than silently applying to another section. Explicit metadata validates before downloading/rendering. When nested YAML is supplied without PyYAML available, report the required parser rather than silently dropping the mapping; PyYAML is already a listed dependency.

## Six composition families

These are a proposed first release, not six fixed page sequences. Reuse a family when purpose warrants it; adapt within it by content roles and assets.

| Family | Visual argument and placement | Component grammar | Appropriate examples |
|---|---|---|---|
| `editorial-narrative` | Strong lead, controlled reading column, selected pull quotes and occasional full-width evidence | Open metrics, typographic quotes, quiet table rules | Story-led case study, public report, cultural essay |
| `evidence-led` | Findings organised around comparisons; chart/table width comes from available columns; compact claim/evidence relationships | Ruled number strips, comparison rows, chart annotations | Board brief, financial review, measurement report |
| `object-catalogue` | Reviewed product/object on a stage; alpha preserved; specifications beside or below the asset; crop does not damage the object | Open specifications and labels; optional single field highlight | Product catalogue, furniture collection, retail proposal |
| `photo-essay` | Approved photos set page hierarchy; panoramic versus portrait images yield different placements; text stays off unsafe image regions | Captions and image sequences; minimal enclosures | Travel, food, architecture, documentary or hospitality brochure |
| `technical-reference` | Numbered systems, diagrams, specifications and tasks; dense but legible; white/light by default unless dark is explicitly selected | Specification rows, diagram legends, compact semantic notes | Engineering handbook, software architecture, operations reference |
| `institutional-paper` | Conventional hierarchy and evidence; abstracts, references and restrained prose; scenario-specific academic/board conventions | Minimal notes, simple tables, no obligatory metric row | Research paper, policy paper, institutional proposal |

Each family must implement structural distinctions on body pages as well as its cover. A change of palette alone cannot pass acceptance. Do not assume “software” requires a dark SaaS page or “wellness” requires sage cards.

## Content and component model

Add a lightweight, order-preserving block model without discarding the existing HTML path. Recognise headings, paragraphs, lists, metrics, SWOT, callouts, tables, figures and charts; retain unknown/trusted HTML as an opaque block with neutral flow treatment. Preserve anchors, source order, accessibility and existing request slots.

- Default metrics: an open typography-led row, not a perimeter card. Offer ruled and compact-table variants where evidence-led/technical content needs them.
- SWOT: render only when present; support a ruled matrix or grouped statements. It is not the mandatory middle of every plan.
- Quotes: typographic pull quotes where warranted, not generic callout cards.
- Notes/actions: open text or a quiet rail; warnings retain a readable semantic label/icon and appropriate contrast, but do not make every insight look like an alert.
- Boxes: reserved for genuinely bounded items, alerts or explicitly requested brand treatments. Avoid thin perimeter + thick accent edge as the shared baseline.
- Flow sections paginate normally. Only explicitly authored feature/opening/closing sections become staged pages. Remove unconditional full-height chapter treatment from ordinary content.
- Feature treatment is keyed by section role/stable ID. Renaming “Executive summary” to “Overview” or translating it must not silently remove composition.

## Asset-directed composition

Continue contact-sheet review and exact-source pinning. This engine must not claim automatic semantic vision from filenames, dimensions or colour statistics.

Capture intrinsic dimensions, aspect ratio and alpha with Pillow; add reviewed role (`photo`, `object`, `diagram`, `logo`), focal point in normalised coordinates, `contain`/`cover` fit, caption, provenance and approval status. Preserve transparent PNG/WebP data for object/logo assets. Do not flatten alpha to white or turn a cutout into a photographic rectangle.

Resolve assets before final composition selection; generate charts after the effective tokens and available block width are known. A portrait asset can select an image/text split, a panorama a spanning band, a transparent object a contained stage, and a diagram a labelled technical figure. Roles must actually affect layout, not merely add metadata.

Photograph filters apply only to photo searches. Reviewed local diagrams and extreme-ratio illustrations remain valid for their roles. Reject zero required-subject matches rather than selecting the first downloadable result. If a hero cannot be sourced, omit it and use the family's text-led fallback with a warning; do not publish a decorative “Image unavailable” box as a finished page. Preserve credits when assets move between cover/body/back cover.

## Page geometry and pagination

Introduce a page-geometry value object computed from the chosen physical format, orientation and output mode. All CSS page dimensions, safe insets and field layouts derive from it. Remove the A4-only 296.6mm cover wrapper and fixed ±18mm “bleed” assumptions; a tested small rounding tolerance may be derived consistently from page height when Chromium requires it.

Use named pages for uniform field runs and authored feature pages. Paint fields in `@page` while preserving safe margins and contrast-correct page furniture. Assign a new named page only at intentional page boundaries. Continued flow must inherit the same field. Where imagery is involved, use bounded in-page images in this release rather than promising arbitrary photographic bleed across automatically fragmented pages.

Keep readable prose measure, widows/orphans, repeating table headers and captions attached to figures. Oversized blocks should choose a compact presentation or split only on semantic boundaries; never shrink the entire document or rely on `overflow: hidden` to conceal loss.

## QA and acceptance

Keep the existing technical gates and fix their current type-floor regressions. Add layout/asset-specific checks based on the design manifest and actual PDF geometry:

- Full-field pages have the declared colour at sampled edges/corners, allowing a small raster colour tolerance. Print-safe pages preserve their intentional outer field.
- Text spans lie inside the declared safe area, apart from explicitly declared display art; furniture stays in its declared zone.
- No unintended empty pages, cropped text, missing blocks, orphaned headings, detached captions or near-empty spill pages. Short authored feature/closing pages can be intentional; report the reason.
- Asset crop/fit honours approved bounds/focal point, transparency survives, and captions/credits match placed assets.
- Chart labels use effective theme fonts, available column width and contrast-aware label colours; every label remains at least 9pt.
- Component presentation and structural signatures match the requested family. Grayscale previews must reveal real layout differences; pixel differences caused only by palette do not establish diversity.

Maintain a six-subject fixture gallery under a single locked theme, plus the three-theme/same-subject regression. Include long prose, sparse sections, long tables, oversized SWOT/callouts, portrait/panorama/transparent assets and missing assets. Use deterministic local assets and synthetic labelled data; network availability must not decide test outcomes. Automated geometry checks complement, not replace, reviewed page previews.

Definition of done: the controlled theme overwrite and white-frame regressions no longer reproduce; all six families demonstrate different content/asset organisation; technical gates pass; every page of the final fixture gallery is visually reviewed; installed-skill routing is verified only after explicit sync approval. “Best PDF skill” is not a measurable acceptance claim.

## Delivery stages and review focus

1. **Repair correctness:** selection precedence, token matching/explainability, live heading selectors, physical-page paint and type-floor failures.
2. **Repair design:** semantic block presentations, six compositions, reviewed asset roles and layout-aware charts.
3. **Keep it repaired:** fixture gallery, geometry/manifest checks and skill workflow updates.

Review focus: theme/brand combinations; landscape/Letter/A5 geometry; multi-page field continuation with headers; asset absence/transparency/crop; legacy JSON/HTML/custom CSS. These must be tests, not promises.

Deliverables for implementation are the engine changes, named regression tests, design manifest, fixture gallery and updated workspace skill instructions. Today’s deliverables are this proposal, its implementation plan and the reproducible audit bundle. No new public site, external publication, automatic install, runtime skill replacement or commit is authorised by this investigation.
