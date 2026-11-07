# PDF Art Direction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop theme collapse and accidental white framing, then make PDF composition respond to content and reviewed assets rather than a repeated panel template.

**Architecture:** Keep the existing single-document Chromium renderer. Introduce an explainable design resolver, physical page geometry, an order-preserving block model, reviewed asset placement and six composition families; feed their manifest into render QA. Preserve the legacy HTML/Markdown/JSON and CLI paths.

**Tech Stack:** Python 3.10+, standard-library unittest/HTMLParser/dataclasses, existing Playwright Chromium, Jinja2, PyMuPDF, Pillow, matplotlib and PyYAML. No new required package or paid API.

**Spec:** `docs/2026-11-04-pdf-art-direction-spec.md`

**Status:** Review draft. No implementation tasks below have been executed. Approval of the full spec and plan is required before product-code changes. Do not replace an installed skill or commit the proposal automatically.

## Global Constraints

- Retain Python 3.10+, Chromium via Playwright, Jinja2, PyMuPDF, Pillow and matplotlib; add no required dependency or paid service.
- Keep Windows execution PowerShell-compatible; use Python UTF-8 file I/O for generated content.
- Preserve existing Markdown, JSON and HTML input paths and existing CLI theme/scenario IDs.
- Preserve one-document Chromium rendering, selectable text, `/Lang`, structure tree, metadata, bookmarks, correct two-pass TOC numbers and source credits; do not merge rasterised pages.
- Require every used text span, including captions, chart labels and running furniture, to be at least 9pt; body text must remain at or above its declared design size.
- Default print text-safe inset: top 20mm, right 18mm, bottom 22mm, left 18mm. Default digital text-safe inset: 16mm on all sides. Explicit user/brand requirements win.
- A full-page field is page paint, not a request to place prose at the physical edge. Crop and trim bleed for commercial printers are out of scope.
- No production code or installed skill copies change until the spec and plan are approved.

## Review Focus

- Explicit CLI theme + frontmatter direction + brand/custom CSS: preserve each declared lock; test in Task 1 and annotate custom CSS in Task 6.
- Letter/A5/landscape and CLI-versus-frontmatter geometry: derive dimensions consistently without A4 constants; test in Task 2.
- Long flow across mixed named page fields with headers/TOC: no blank page, colour loss or source loss; test in Tasks 2, 5 and 6.
- Transparent/missing/portrait/panoramic assets: keep alpha and approved focal bounds, or select a text fallback; test in Tasks 4 and 5.
- Legacy JSON/HTML, renamed headings and unknown markup: preserve ordering/anchors and neutral fallback; test in Tasks 3, 5 and 7.

## File map

New `pdfstudio/design.py` owns choice precedence/explanations; `geometry.py` owns physical dimensions; `blocks.py` owns structural blocks; `asset_layout.py` owns reviewed placement metadata; `compositions.py` owns family and section treatments; `design_qa.py` owns manifest-aware checks. Existing `render.py` remains orchestration, `content.py` remains source loading and block generation, `images.py` remains sourcing/encoding, and `charts.py` remains chart generation. Jinja/CSS implement family presentation, not subject classification.

Use `tests/test_*.py` and `tests/fixtures/design/` for deterministic regression fixtures. The existing `_test_named.py` and `_test_merge.py` are probes, not the new test harness. Do not bulk-refactor unrelated code.

## Stage 1 — Correctness

### Task 1: Honour explicit choices and make inference explainable

**Files:** Create `pdfstudio/design.py`, `tests/__init__.py`, `tests/test_design_selection.py`, `tests/test_cli_design.py`; modify `pdfstudio/art_direction.py:269–320`, `pdfstudio/render.py:68–98,737–744`, `pdfstudio/cli.py` build options, and ID validation in `tokens.py`/`scenarios.py`.

**Interfaces:**
- Create `DesignBrief(subject: str, audience: str, purpose: str, visual_argument: str, output_mode: str = 'print', composition: str | None = None)`.
- Create `DesignDecision(theme_id: str, direction_id: str, family_id: str, tokens: DesignSystem, output_mode: str, locked_fields: tuple[str, ...], reasons: tuple[str, ...], family_locked: bool)`.
- Produce `resolve_design(doc: Document, opts: RenderOptions) -> DesignDecision` and `match_keywords(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]`.
- Add optional `composition`, `output_mode` and `art_direction` fields to `RenderOptions`; retain existing flags and legacy frontmatter aliases. Scenario/theme automatic defaults must remain distinguishable from explicit selections.

- [ ] **Step 1: Write failing selection tests.** `test_explicit_theme_survives_auto_direction` iterates modern-saas/luxury/warm-sage with a software title and asserts palette/font/radius/body-size equality to the explicitly selected theme. `test_cli_theme_beats_frontmatter_theme` asserts luxury wins over frontmatter sage. `test_explicit_direction_does_not_replace_locked_theme` asserts legacy direction chooses family but not locked tokens. `test_base_theme_not_mutated` compares the registry before/after. `test_invalid_explicit_ids_fail` checks theme/scenario/direction/family errors list supported choices.
- [ ] **Step 2: Write failing inference tests.** `test_ai_not_substring` checks retail/chair/portrait/repairs/campaign do not contribute an AI match while standalone “AI” does. `test_phrase_boundaries`, `test_case_study_label_not_subject`, `test_tied_subject_has_neutral_explanation` and `test_explicit_industry_outweighs_incidental_body_word` assert boundary matching and explained fallback. An inference rule must require subject evidence, not document-type words.
- [ ] **Step 3: Run** `python -m unittest tests.test_design_selection tests.test_cli_design -v`; expect failures exposing current overrides/misclassification or missing APIs.
- [ ] **Step 4: Implement the resolver and compatibility map.** Use CLI → frontmatter → brief → subject inference → scenario defaults per field. Theme lock prevents automatic token replacement. Infer composition independently and preserve legacy direction IDs. Use Unicode token/phrase boundaries, separate metadata from body, and explicit ambiguity fallback. Start weights at title/industry/purpose 6, other subject metadata 3, body 1; require a non-document-type match, a winning score at least 6 and lead at least 2 for subject-driven selection. Otherwise explain the scenario fallback; explicit choices bypass scoring. Suggested direction tokens apply only without explicit theme/brand locks. Add CLI integration and actionable validation; retain callable legacy helpers but remove their unconditional override from rendering.
- [ ] **Step 5: Run the selection/CLI tests and rebuild the three-theme audit fixtures.** Expect distinct effective locked theme tokens, correct labels and an explanation for each selection. Fix related default labels/copy that become unreadable under restored tokens; do not weaken the 9pt gate.
- [ ] **Step 6: Commit after task review** with message `fix: preserve explicit PDF design choices`.

### Task 2: Separate physical page paint from readable bounds

**Files:** Create `pdfstudio/geometry.py`, `tests/test_page_geometry.py`, `tests/test_page_paint.py`; modify `pdfstudio/render.py:116–137,200–294,737–754`, `assets/css/base.css:565–580`, `assets/css/directions.css:284–363,640–672,781–785,846–850`, cover/body templates and existing furniture type sizes.

**Interfaces:**
- Create `PageGeometry(width_mm: float, height_mm: float, safe_mm: tuple[float, float, float, float])` with computed `inner_width_mm` and `inner_height_mm` properties.
- Produce `resolve_geometry(page_size: str, landscape: bool, output_mode: str, safe_mm: tuple[float, float, float, float] | None = None) -> PageGeometry` and `page_field_css(name: str, colour: str, geometry: PageGeometry) -> str`.
- Consume Task 1 decision; rendering/QA must use the same geometry object.

- [ ] **Step 1: Write failing geometry tests.** `test_all_formats_and_orientations` covers A3/A4/A5/Letter/Legal/Tabloid, checking exact dimensions already registered in `render.py`, swapped in landscape. `test_mode_safe_insets` asserts print `(20,18,22,18)` and digital `(16,16,16,16)`. `test_cli_page_size_beats_frontmatter` prevents the current later metadata override. `test_invalid_safe_area_rejected` rejects negative or page-consuming margins.
- [ ] **Step 2: Write Chromium paint tests.** `test_field_reaches_all_sheet_edges` asserts eight sampled edge/corner pixels within ±3 RGB of the declared field; `test_continuation_keeps_field_and_safe_text` checks two overflowing body pages; `test_mixed_named_fields_without_blank_page` checks cover + body + feature + closing with expected text/page counts; `test_cover_matches_each_format` covers A4/Letter/A5/landscape. `test_furniture_floor_and_contrast` asserts running type at least 9pt and readable in light/dark fields. Exclude the declared furniture zone from body-bound assertions.
- [ ] **Step 3: Run** `python -m unittest tests.test_page_geometry tests.test_page_paint -v`; expect current white-edge/format/type failures.
- [ ] **Step 4: Implement geometry-driven named-page backgrounds.** The audit proved CSS `@page` background works in installed Chromium and preserves inset text. Remove the 296.6mm constant, fixed ±18mm expansions and inner-sized fake full-page paint. Use physical geometry for the cover and safe bounds for prose. Named field runs change only at deliberate boundaries; ordinary flow inherits the current named page. Preserve margin-box furniture with contrast-correct colour and at least 9pt labels. Do not use negative fixed background layers or margin-box painting with visible seams.
- [ ] **Step 5: Run the geometry/paint suites and current audit builds.** Inspect cover/body/continuation PNGs and measured text. Confirm no lost TOC links/tags and no global shrink. If an older fallback engine cannot provide full fields, return an explicit unsupported-treatment warning instead of claiming success.
- [ ] **Step 6: Commit after task review** with message `fix: paint PDF page fields without sacrificing safe margins`.

## Stage 2 — Real composition

### Task 3: Preserve semantic blocks and remove the obligatory card baseline

**Files:** Create `pdfstudio/blocks.py`, `tests/test_content_blocks.py`, `tests/test_component_presentations.py`; modify `pdfstudio/content.py:204–233,270–309,332–397,714–end`, `assets/css/base.css:277–378`, `assets/css/overrides.css`, and chapter heading selectors.

**Interfaces:**
- Create `ContentBlock(id: str, kind: str, html: str, section_id: str, request_slot: str | None = None, presentation: str | None = None)`.
- Add `Document.blocks: list[ContentBlock]` with an empty default.
- Produce `parse_blocks(doc: Document) -> tuple[ContentBlock, ...]` and `present_block(block: ContentBlock, variant: str) -> str`. Variants: metrics `open|ruled|table`; SWOT `matrix|statements`; callouts `open|rail|alert`; figures/charts retain intrinsic classes. Unknown markup uses `flow`.

- [ ] **Step 1: Write failing block tests.** `test_block_order_and_slots_preserved`, `test_json_and_html_keep_anchors`, `test_unknown_html_is_opaque_flow`, `test_renamed_heading_keeps_stable_role`, `test_empty_source_has_no_fabricated_components` assert source order, request IDs, anchors, unchanged unknown markup and no invented metrics/SWOT. Use existing source loaders, not a separate new input path.
- [ ] **Step 2: Write failing presentation tests.** `test_open_metrics_have_no_card_perimeter`, `test_warning_keeps_readable_semantic_label`, `test_swot_only_when_supplied`, `test_theme_heading_selector_matches_chapter_h2` and `test_one_component_not_all_boxed` assert actual computed print styles in Chromium. Quote/insight/warning cannot all resolve to the same enclosure style. Preserve deliberately framed certificates.
- [ ] **Step 3: Run** `python -m unittest tests.test_content_blocks tests.test_component_presentations -v`; expect missing block API and inherited-card/selector failures.
- [ ] **Step 4: Implement the order-preserving model using existing HTML classes/slots and standard-library HTMLParser.** Retain `body_html` for backwards compatibility; unknown HTML stays opaque. Add presentation modifiers without rebuilding prose into panels. Make open metrics and notes the baseline, keep explicit alerts and certificate framing, and align theme heading selectors with `.chapter` wrappers. Remove only obsolete presentation rules; maintain list/table/anchor integrity.
- [ ] **Step 5: Run both suites plus Tasks 1–2 suites.** Render metrics/SWOT/long-note fixtures in light/dark themes and confirm readable labels at 9pt or above. Existing sources must still load without new metadata.
- [ ] **Step 6: Commit after task review** with message `feat: add semantic PDF component presentations`.

### Task 4: Make reviewed assets and chart geometry available to layout

**Files:** Create `pdfstudio/asset_layout.py`, `tests/test_asset_layout.py`, `tests/test_chart_design.py`, deterministic generated asset fixtures; modify `pdfstudio/images.py:54–134,226–273,597–627,721–747`, `pdfstudio/charts.py:100–end`, and asset orchestration in `render.py:769–778`.

**Interfaces:**
- Create `AssetSpec(role: str = 'photo', fit: str = 'contain', focal: tuple[float, float] = (0.5,0.5), crop: tuple[float,float,float,float] | None = None, approved: bool = False, derive_accent: bool = False)`.
- Create `AssetLayout(slot: str, role: str, width_px: int, height_px: int, aspect: float, has_alpha: bool, fit: str, focal: tuple[float,float], crop: tuple[float,float,float,float] | None, approved: bool, accent: str | None = None)`. Optional accent is a reviewed/opt-in quantised colour suggestion, not the current 1-pixel average; no automatic brand override.
- Produce `suggest_asset_accent(image: ResolvedImage, spec: AssetSpec) -> str | None` only when `approved` and `derive_accent` are true; use Pillow quantisation, discard transparent/background-dominated bins, and return no suggestion when no usable bin remains.
- Produce `analyse_asset(slot: str, image: ResolvedImage, spec: AssetSpec) -> AssetLayout`, `read_asset_specs(meta: dict) -> dict[str, AssetSpec]` and `validate_asset_specs(doc: Document, specs: dict[str,AssetSpec]) -> None`. The validator checks existing request slots and reserved cover/back-cover references before download. `AssetLayout.aspect` is the approved crop's effective aspect, computed from original pixel dimensions and crop rectangle, not always the full source aspect.
- Extend `ResolvedImage` with `has_alpha` and `media_type`, retaining all source/licence fields. Keep `make_chart(req: ChartRequest, ds: DesignSystem, number: int = 0, width: float = 7.4, height: float = 3.4) -> str` compatible; call it with layout-derived inches instead of its default width.

- [ ] **Step 1: Write failing asset tests.** `test_object_alpha_survives_decode_encode`, `test_portrait_and_panorama_report_intrinsics`, `test_focal_point_validated`, `test_crop_rectangle_validated_and_focal_inside`, `test_accent_suggestion_requires_review_and_opt_in`, `test_zero_subject_match_not_auto_selected`, `test_diagram_role_not_photo_filtered`, `test_missing_hero_warns_without_publish_placeholder`, `test_nested_asset_metadata_not_silently_lost`, `test_credits_survive_role_reassignment`. Generate transparent PNG, portrait, panorama and diagram locally; mock downloads and candidate lists.
- [ ] **Step 2: Write failing chart tests.** `test_chart_fonts_follow_effective_theme`, `test_layout_width_passed_to_chart`, `test_labels_remain_9pt_at_final_width`, `test_stacked_labels_choose_contrast` and `test_long_category_labels_do_not_overlap` check font choices/render settings and final displayed size. Rasterised chart text requires layout-aware effective-size calculation and preview verification, not just PyMuPDF span checks.
- [ ] **Step 3: Run** `python -m unittest tests.test_asset_layout tests.test_chart_design -v`; expect alpha loss, fixed-font/size and metadata failures.
- [ ] **Step 4: Implement role-aware processing and placement data.** Preserve alpha formats for objects/logos; keep photo JPEG handling. Enforce role-specific filters and minimum required-subject matching. Use reviewed metadata, not fictional semantic vision. Validate crop/focal rectangles and request references against the spec before rendering; preserve approved crops in placement metadata. Missing optional hero selects no decorative placeholder. Resolve images before final composition; defer chart raster generation until its width is known. Use effective design font families and contrast-aware labels; labels never use the current 8pt small-font setting. Existing credited asset identity/dedup rules remain intact.
- [ ] **Step 5: Run tests plus earlier suites.** Preview the transparent object on a nonwhite field, portrait/panorama and light-palette stacked chart; validate licence/caption persistence. Do not require network access for tests.
- [ ] **Step 6: Commit after task review** with message `feat: expose reviewed asset roles to PDF layout`.

### Task 5: Implement six genuinely different composition families

**Files:** Create `pdfstudio/compositions.py`, `pdfstudio/templates/compositions/section.html.j2`, `assets/css/compositions.css`, `tests/test_compositions.py`, `tests/test_flow_pagination.py`; modify `render.py:446–482,737–end`, body/cover templates and `directions.css` to retire conflicting legacy field/card rules.

**Interfaces:**
- Create `SectionLayout(section_id: str, family_id: str, treatment: str, columns: int, field: str | None, presentations: dict[str,str], asset_slots: tuple[str,...])`; treatments `flow|opening|feature|closing`.
- Produce `plan_sections(blocks: tuple[ContentBlock,...], decision: DesignDecision, assets: dict[str,AssetLayout], geometry: PageGeometry, meta: dict) -> tuple[SectionLayout,...]`, `render_sections(blocks: tuple[ContentBlock,...], layouts: tuple[SectionLayout,...]) -> str`, and `composition_signature(layouts: tuple[SectionLayout,...]) -> tuple[tuple,...]`.
- Produce `apply_asset_accent(decision: DesignDecision, assets: dict[str,AssetLayout]) -> DesignDecision`; adopt the first approved opt-in suggestion in source order only if palette/accent is not explicitly locked, and reject a suggestion that fails text contrast. Otherwise retain the original decision with an explanation.
- Structural signatures include treatment, columns, component variants and asset roles/placement—not source titles, colour values or IDs. Validate `design.sections` role/field enums and references against parsed explicit heading IDs; role defaults to `flow`.

- [ ] **Step 1: Write failing family tests.** `test_six_families_have_distinct_body_signatures` uses one locked Swiss theme with editorial/evidence/object/photo/technical/institutional fixtures and expects six structural signatures. `test_explicit_family_not_changed_by_photo`, `test_asset_aspect_changes_photo_placement`, `test_object_uses_contain_stage`, `test_photo_crop_preserves_approved_source_rectangle`, `test_asset_accent_never_overrides_locked_theme`, `test_invalid_section_reference_rejected`, `test_diagram_selects_labelled_reference_placement` and `test_no_image_has_text_fallback` assert actual body structure and placement.
- [ ] **Step 2: Write failing flow tests.** `test_short_section_not_forced_full_page`, `test_long_flow_preserves_every_block`, `test_caption_moves_with_figure`, `test_long_table_repeats_header`, `test_oversized_callout_split_or_compact_not_clipped`, `test_role_independent_of_english_heading`, `test_rendered_dom_matches_family_plan`, `test_mixed_fields_keep_continuation_colour` and `test_reflow_keeps_final_toc_numbers` cover authored roles, continuation, large blocks and pagination. Explicit feature pages may be sparse; unmarked prose is normal flow.
- [ ] **Step 3: Run** `python -m unittest tests.test_compositions tests.test_flow_pagination -v`; expect current shared grammar/forced-height failures.
- [ ] **Step 4: Implement the six spec families.** Family grammar must change body placement as well as cover. Use existing renderer/templates plus section roles and approved asset data; no topic-name CSS or nth-child colour cycles. Keep auto-layout deterministic and family locks intact. Compute chart width from the section's column geometry. Apply named fields at intentional boundaries and normal flow elsewhere. Disable legacy overrides that conflict with the new section treatment; do not stack more increasingly specific CSS on them.
- [ ] **Step 5: Run the family/flow suites and prior suites.** Produce colour and grayscale contact sheets. Visually verify that structural differences remain visible without palette differences; inspect every page, not just covers. Correct overflow/content loss rather than hiding it or shrinking the document.
- [ ] **Step 6: Commit after task review** with message `feat: add content-led PDF composition families`.

## Stage 3 — Prevent recurrence

### Task 6: Emit a design manifest and check the actual layout

**Files:** Create `pdfstudio/design_qa.py`, `tests/test_design_qa.py`; modify `render.py:858–end`, `qa.py`/`cli.py` check/report integration, and contrast orchestration where page fields affect sampled colour.

**Interfaces:**
- Produce `build_design_manifest(decision: DesignDecision, geometry: PageGeometry, layouts: tuple[SectionLayout,...], assets: dict[str,AssetLayout], custom_css: bool) -> dict`, `map_rendered_sections(pdf_path: Path, blocks: tuple[ContentBlock,...], layouts: tuple[SectionLayout,...]) -> dict[str,tuple[int,...]]` and `check_design(pdf_path: Path, manifest: dict) -> dict`. Mapping uses final PDF destinations where available, then ordered heading/body-text matches with furniture excluded. Repeated headings are resolved in source order; ambiguous/unmappable boundaries produce an explicit design-check failure, never a fabricated page range.
- JSON contains schema version 1, requested/effective IDs, locks, reasons, geometry, declared field runs, expected block IDs, component variants, placed asset metadata and custom-CSS provenance; no image data URI, raw bytes or secrets.
- Add `RenderResult.design_manifest: dict` and write `<pdf-stem>.design.json` next to the PDF. Attach results under existing QA `design` without removing its established keys. `check --design-manifest PATH` loads it explicitly.

- [ ] **Step 1: Write failing manifest tests.** `test_manifest_explains_theme_and_family`, `test_manifest_has_no_embedded_asset_bytes`, `test_custom_css_reported`, `test_manifest_round_trip`, `test_missing_manifest_does_not_invent_design_pass` assert explainability and backwards compatibility.
- [ ] **Step 2: Write failing measured-layout tests.** `test_white_frame_detected_for_full_field`, `test_safe_inset_violation_detected`, `test_missing_block_detected_even_if_clipped`, `test_repeated_heading_page_mapping_uses_source_order`, `test_ambiguous_mapping_cannot_claim_design_pass`, `test_intentional_feature_sparse_is_reported_not_rejected`, `test_near_empty_spill_warned`, `test_actual_type_floor_still_enforced`, `test_credits_and_crop_match_placement` use small deterministic PDFs and manifests. Text/figure occupancy excludes backgrounds and furniture; below 35% of safe area is advisory for unmarked flow, never a mandate to add filler.
- [ ] **Step 3: Run** `python -m unittest tests.test_design_qa -v`; expect missing manifest and missing geometry-specific checks.
- [ ] **Step 4: Implement manifest emission and actual PDF checks.** Derive field-page mapping from rendered anchors/page assignments, not assumed one-section-per-page. Check raster field samples and text-safe boxes, retain tagged/text/TOC checks, account for real page furniture and declared feature exceptions. Compare source block presence against extracted output; preserve honest warnings for raster chart-size checks requiring visual confirmation. Unknown custom CSS may change presentation but cannot silently disable clipping/type/metadata errors.
- [ ] **Step 5: Run the suite and strict-render the six-family gallery.** Expect no technical error gates. Review the manifest and measured warnings; all accepted design exceptions must name the page/role and reason. Do not claim that a structural signature proves aesthetic excellence.
- [ ] **Step 6: Commit after task review** with message `feat: verify PDF design intent against rendered pages`.

### Task 7: Ship a representative gallery and a skill workflow that uses it

**Files:** Create `tests/fixtures/design/*.md`, local assets, `tests/test_design_gallery.py`, `tests/render_design_gallery.py`; modify workspace `SKILL.md:79–101,123–147,274–319,327–374,435–end`, `README.md` and examples only where old defaults/claims conflict with the implemented design contract.

**Interfaces:**
- Produce `render_gallery(output_dir: Path) -> dict[str,Path]` in `tests/render_design_gallery.py`; callable as `python -m tests.render_design_gallery --out out/design-gallery`.
- Six fixtures: cultural case study, financial review, object catalogue, travel/photo essay, technical reference and institutional research. All are labelled synthetic, under one locked theme; use no real financial/brand claims or live searches.

- [ ] **Step 1: Write the failing gallery test.** `test_gallery_uses_locked_theme_with_six_body_grammars` asserts one effective theme and six body signatures; `test_legacy_marketing_certificate_json_html_still_build` includes existing examples and legacy loaders. `test_all_final_gallery_pages_have_review_previews` checks cover/body/continuations/closing page coverage. `test_optional_assets_do_not_create_dead_slots` exercises the text fallback.
- [ ] **Step 2: Run** `python -m unittest tests.test_design_gallery -v`; expect missing fixtures/runner or unmet compatibility checks.
- [ ] **Step 3: Add fixtures and update the skill workflow.** Require a compact design brief and explainable composition selection, contact-sheet asset approval, scoped role-based layout, final geometry/type checks and inspection of every final page. Replace “metrics near the top, break the grid once, write the back cover” as universal prescriptions with purpose-dependent decisions. Explain theme versus composition, precedence, medium, role metadata and fallbacks. Include varied examples, not a single Modern-SaaS marketing default. Documentation must describe implemented behaviour, not aspirational capabilities.
- [ ] **Step 4: Run** `python -m unittest discover -s tests -p 'test_*.py' -v` and `python -m tests.render_design_gallery --out out/design-gallery`. Inspect every final preview and the grayscale comparison. Re-run after corrections; preserve both final QA reports and reviewed preview list. The supplied audit baselines must now demonstrate corrected precedence and physical page paint.
- [ ] **Step 5: Verify installation routing without overwriting it.** The skill tool in the investigation returned `C:\Users\HomePC\.codex\skills\peTeyF\SKILL.md`, while this workspace contains the engine source. Inspect/sync external installed copies only after explicit user approval and allowed path access. Built-in runtime copies are never patched directly. Check the actual engine root/version used by the next skill call; do not equate changing workspace `SKILL.md` with deploying the engine.
- [ ] **Step 6: Whole-branch review, then commit approved changes** with message `docs: make PDF art direction reviewable and testable`. Deliver the updated skill/package, gallery previews/PDFs and final measured QA. No public deployment is needed.

## Execution and acceptance handoff

Tasks are serial where they share render/content/CSS ownership. A fresh implementer/reviewer per task is recommended because restored theme tokens, page geometry and asset placement interact; do not run overlapping writers on `render.py` or shared styles. Research or read-only validation may run in parallel.

Self-review: all spec requirements map to Tasks 1–7; signatures/types are defined before consumption; five Review Focus conditions have named tests; no required new package is assumed. Crop/reference validation, actual rendered-family checks and ambiguous page mapping have explicit contracts/tests. The plan is a staged overhaul, not a one-line skill patch or a promise that a palette catalogue produces good design.

Independent proposal review was attempted but produced no findings: the configured provider was token-rate-limited and the alternate provider had insufficient balance. This handoff is locally self-reviewed, **not independently verified**. Obtain independent proposal review before implementation when that route is available; do not treat a failed reviewer run as approval.

No execution method has been selected yet. Review the spec and plan first. Implementation can then be approved using native execution with final independent review, or task-by-task subagent implementation with review gates. Do not turn this handoff into automatic implementation.
