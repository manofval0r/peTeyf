"""Command-line interface for PDF Studio.

Usage:
    python -m pdfstudio build input.md --scenario marketing-plan --theme modern-saas
    python -m pdfstudio check output.pdf --source input.md
    python -m pdfstudio images "crocs retail display" --out review.jpg
    python -m pdfstudio themes
    python -m pdfstudio scenarios
    python -m pdfstudio inspect output.pdf
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from .art_direction import DIRECTIONS, apply_direction, infer_direction, list_directions
from .content import load_document
from .design import FAMILIES, resolve_design
from .copyedit import audit_copy, errors as copy_errors, format_issues
from .qa import analyze, format_report, has_errors as qa_has_errors
from .render import RenderOptions, render
from .scenarios import SCENARIOS, get_scenario, list_scenarios
from .tokens import THEMES, get_theme, list_themes


def _print_err(message: str) -> None:
    print(message, file=sys.stderr)


def cmd_build(args: argparse.Namespace) -> int:
    src = Path(args.input)
    if not src.exists():
        _print_err(f"Input not found: {src}")
        return 2

    if args.out:
        out = Path(args.out)
    else:
        out = src.with_name(f"{src.stem}.pdf")

    doc = load_document(src)
    if args.title:
        doc.meta["title"] = args.title
    if args.art_direction:
        doc.meta["art_direction"] = args.art_direction

    source_text = src.read_text(encoding="utf-8", errors="replace")
    copy_issues = audit_copy(source_text)
    if copy_issues and args.copy_policy != "off":
        print("Copy check\n")
        print(format_issues(copy_issues))
        print()
    if args.copy_policy == "strict" and copy_errors(copy_issues):
        _print_err("Build stopped: fix copy errors or use --copy-policy warn/off.")
        return 2

    extra_css = ""
    for css_path in args.css or []:
        p = Path(css_path)
        if not p.exists():
            _print_err(f"CSS not found: {p}")
            return 2
        extra_css += "\n" + p.read_text(encoding="utf-8")

    scenario_id = args.scenario or str(doc.meta.get("scenario") or "report")
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario_id!r}. Supported: {', '.join(SCENARIOS)}")

    opts = RenderOptions(
        output=out,
        scenario=scenario_id,
        theme=args.theme,
        composition=args.composition,
        output_mode=args.output_mode,
        art_direction=args.art_direction,
        page_size=args.page_size,
        landscape=args.landscape,
        toc=args.toc,
        cover=args.cover,
        engine=args.engine,
        images=args.images,
        preview=not args.no_preview,
        preview_pages=args.preview_pages,
        stamp=not args.no_stamp,
        bookmarks=not args.no_bookmarks,
        keep_html=args.keep_html,
        extra_css=extra_css,
        contrast=not args.no_contrast,
    )

    scenario = get_scenario(scenario_id)
    decision = resolve_design(doc, opts)
    theme = decision.tokens
    print(f"Building '{doc.meta.get('title') or src.stem}'")
    print(f"  scenario : {scenario.id} ({scenario.label})")
    print(f"  design   : {theme.id} ({theme.label})")
    print(f"  output   : {out}")

    result = render(doc, opts)
    print(f"  direction: {result.direction_id} ({result.direction_label})")
    print()
    print(format_report(result.report or {"pages": result.pages}))
    if result.previews:
        print("\nPreviews:")
        for p in result.previews:
            print(f"  {p}")
    for warning in result.warnings:
        print(f"  ! {warning}")
    if result.html_path:
        print(f"\nHTML kept at {result.html_path}")
    if args.strict and qa_has_errors(result.report or {}):
        _print_err("\nBuild finished, but strict QA found errors.")
        return 1
    return 0


def cmd_themes(_args: argparse.Namespace) -> int:
    print("Design systems\n")
    current_family = None
    for t in list_themes():
        print(f"  {t['id']:<14} {t['label']:<22} {t['mood']}")
    print("\nUse with --theme <id>. Scenarios pick a sensible default.")
    return 0


def cmd_scenarios(_args: argparse.Namespace) -> int:
    print("Scenarios\n")
    for s in list_scenarios():
        print(f"  {s['id']:<15} {s['label']}")
        print(f"  {'':<15} default theme: {s['default_theme']}")
        print(f"  {'':<15} {s['description']}")
        if s["best_for"]:
            print(f"  {'':<15} best for: {', '.join(s['best_for'])}")
        print()
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    report = analyze(args.pdf, preview_dir=args.previews,
                     max_previews=args.pages or 6)
    print(format_report(report))
    if args.json:
        print(json.dumps(report, indent=2))
    if report.get("previews"):
        print("\nPreviews:")
        for p in report["previews"]:
            print(f"  {p}")
    return 0


def cmd_designs(_args: argparse.Namespace) -> int:
    """Print themes and the stronger topic-aware art directions."""
    print("Themes\n")
    for theme_id, theme in THEMES.items():
        matches = [s.id for s in SCENARIOS.values() if s.default_theme == theme_id]
        print(f"{theme_id:<14} {theme.label:<22} e.g. {', '.join(matches) or '-'}")
    print("\nArt directions\n")
    for direction in list_directions():
        print(f"{direction['id']:<22} {direction['label']:<24} {direction['tone']}")
    return 0


def cmd_compositions(_args: argparse.Namespace) -> int:
    from .compositions import GRAMMAR
    print('Content/asset compositions (independent of theme)\n')
    for family, variants in GRAMMAR.items():
        print(f"{family:<24} metrics={variants['metrics']}; headings={variants['heading']}")
    return 0


def cmd_directions(_args: argparse.Namespace) -> int:
    print("Topic-aware art directions\n")
    for direction in list_directions():
        print(f"  {direction['id']:<22} {direction['label']}")
        print(f"  {'':<22} {direction['concept']}")
    print("\nSet explicitly with --art-direction <id> or frontmatter art_direction.")
    return 0


def cmd_copycheck(args: argparse.Namespace) -> int:
    path = Path(args.input)
    if not path.exists():
        _print_err(f"Input not found: {path}")
        return 2
    issues = audit_copy(
        path.read_text(encoding="utf-8", errors="replace"),
        locale=args.locale,
    )
    if not issues:
        print("[OK] Copy check passed: no em dashes, emoji, placeholder data, "
              "mixed spelling, mixed units, or stock AI phrases.")
        return 0
    print(format_issues(issues))
    return 2 if copy_errors(issues) else 0


def _pt_value(value: str) -> float | None:
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)\s*pt", str(value or ""))
    return float(match.group(1)) if match else None


def _expect_from_source(source: Path) -> dict:
    """Recover the declared body size and measure from the source document."""
    doc = load_document(source)
    scenario_id = str(doc.meta.get("scenario") or "report")
    if scenario_id not in SCENARIOS:
        raise ValueError(f"Unknown scenario {scenario_id!r}. Supported: {', '.join(SCENARIOS)}")
    scenario = get_scenario(scenario_id)
    theme = get_theme(str(doc.meta.get("theme") or scenario.default_theme))
    ds = resolve_design(doc, RenderOptions(output=source.with_suffix('.pdf'))).tokens
    from .geometry import resolve_geometry
    mode = resolve_design(doc, RenderOptions(output=source.with_suffix('.pdf'))).output_mode
    ds.margin = resolve_geometry(str(doc.meta.get('page_size') or scenario.page), bool(doc.meta.get('landscape', scenario.landscape)), mode, (doc.meta.get('design') or {}).get('safe_mm')).margin_css
    margins = tuple(float(v) for v in re.findall(r"(\d+(?:\.\d+)?)\s*mm", ds.margin))
    if len(margins) == 3:
        margins = (margins[0], margins[1], margins[2], margins[1])
    elif len(margins) == 2:
        margins = (margins[0], margins[1], margins[0], margins[1])
    elif len(margins) == 1:
        margins = margins * 4
    elif len(margins) != 4:
        margins = (20.0, 18.0, 22.0, 18.0)
    return {
        "body_size_pt": _pt_value(ds.body_size),
        "min_font_pt": 9.0,
        "measure_ch": _float_value(ds.measure, 68.0),
        "margins_mm": margins,
        "requires_credits": bool(doc.image_requests or doc.meta.get('cover_image') or doc.meta.get('back_cover_image')),
        "cover_pages": 0 if doc.meta.get("cover") is False or scenario.cover == 'none' else 1,
    }


def _float_value(value: str, fallback: float) -> float:
    match = re.match(r"\s*(-?\d+(?:\.\d+)?)", str(value or ""))
    return float(match.group(1)) if match else fallback


def cmd_check(args: argparse.Namespace) -> int:
    pdf = Path(args.pdf)
    if not pdf.exists():
        _print_err(f"PDF not found: {pdf}")
        return 2

    expect: dict = {}
    if args.source:
        source = Path(args.source)
        if not source.exists():
            _print_err(f"Source not found: {source}")
            return 2
        try:
            expect.update(_expect_from_source(source))
        except Exception as exc:
            _print_err(f"Could not read design intent from {source}: {exc}")
    if args.body_size:
        expect["body_size_pt"] = args.body_size
    if args.min_font:
        expect["min_font_pt"] = args.min_font
    if args.measure:
        expect["measure_ch"] = args.measure
    if args.cover_pages is not None:
        expect["cover_pages"] = args.cover_pages

    report = analyze(
        pdf,
        preview_dir=args.previews,
        max_previews=args.pages or 6,
        expect=expect,
    )
    from .design_qa import check_design
    manifest_path = Path(args.design_manifest) if getattr(args, 'design_manifest', None) else pdf.with_suffix('.design.json')
    if manifest_path.is_file():
        design_report = check_design(pdf, json.loads(manifest_path.read_text(encoding='utf-8')))
        report['design'] = design_report
        report.setdefault('issues', []).extend(design_report['issues'])
        report.setdefault('gates', {})['design_layout'] = design_report['passed']
    else:
        report.setdefault('warnings', []).append('No design manifest: technical checks only, not a design-layout pass.')
    print(format_report(report))
    if args.json:
        print(json.dumps(report, indent=2, default=str))
    if report.get("previews"):
        print("\nPreviews:")
        for path in report["previews"]:
            print(f"  {path}")
    return 1 if qa_has_errors(report) else 0


def cmd_images(args: argparse.Namespace) -> int:
    from .images import contact_sheet

    try:
        sheet, items = contact_sheet(
            args.query, args.out, count=args.count, columns=args.columns,
        )
    except Exception as exc:
        _print_err(f"Image review failed: {exc}")
        return 2

    print(f"Candidate sheet: {sheet}")
    print("Look at the sheet before choosing. A title match is not a visual match.\n")
    for index, item in enumerate(items):
        title = str(item.get("title") or "")
        print(
            f"  {index:>2}  {item.get('width')}x{item.get('height')}  "
            f"{item.get('license') or '-'}  {title}"
        )
    print("\nPin a verified file in the source with:")
    print("  ![caption](search:commons:Exact File Name.jpg)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pdfstudio",
        description="Design-first PDF generation: Markdown/JSON/HTML to art-directed PDF.",
    )
    sub = parser.add_subparsers(dest="command")

    p_build = sub.add_parser("build", help="Build a PDF from a Markdown/JSON/HTML file")
    p_build.add_argument("input", help="Source file (.md, .json, .html)")
    p_build.add_argument("-o", "--out", help="Output PDF path")
    p_build.add_argument("-s", "--scenario", default=None,
                         choices=sorted(SCENARIOS),
                         help="Document scenario (default: frontmatter or report)")
    p_build.add_argument("-t", "--theme", choices=sorted(THEMES),
                         help="Design system (defaults to the scenario's)")
    p_build.add_argument("--art-direction", choices=sorted(DIRECTIONS),
                         help="Explicit art direction (otherwise inferred from topic)")
    p_build.add_argument('--composition', choices=FAMILIES, help='Content/asset composition, independent of theme')
    p_build.add_argument('--output-mode', choices=['print','digital'], help='Text-safe page treatment')
    p_build.add_argument("--copy-policy", default="strict",
                         choices=["strict", "warn", "off"],
                         help="Copy quality gate (default: strict)")
    p_build.add_argument("--title", help="Override the document title")
    p_build.add_argument("--page-size", dest="page_size",
                         choices=["A3", "A4", "A5", "Letter", "Legal", "Tabloid"])
    p_build.add_argument("--landscape", dest="landscape", action="store_true",
                         default=None, help="Force landscape")
    p_build.add_argument("--portrait", dest="landscape", action="store_false",
                         help="Force portrait")
    p_build.add_argument("--toc", dest="toc", action="store_true", default=None,
                         help="Force a table of contents")
    p_build.add_argument("--no-toc", dest="toc", action="store_false",
                         help="Disable the table of contents")
    p_build.add_argument("--cover", dest="cover", action="store_true", default=None,
                         help="Force a cover page")
    p_build.add_argument("--no-cover", dest="cover", action="store_false",
                         help="Disable the cover page")
    p_build.add_argument("--engine", default="auto",
                         choices=["auto", "playwright", "weasyprint"],
                         help="PDF rendering engine")
    p_build.add_argument("--images", default="auto", choices=["auto", "off"],
                         help="Search the web for images (auto) or skip them (off)")
    p_build.add_argument("--preview-pages", dest="preview_pages", type=int,
                         default=6, help="How many page previews to render")
    p_build.add_argument("--no-preview", dest="no_preview", action="store_true",
                         help="Skip QA previews")
    p_build.add_argument("--no-stamp", dest="no_stamp", action="store_true",
                         help="Skip headers, footers and page numbers")
    p_build.add_argument("--no-bookmarks", dest="no_bookmarks", action="store_true",
                         help="Skip PDF outline generation")
    p_build.add_argument("--keep-html", dest="keep_html", action="store_true",
                         help="Write the intermediate HTML next to the PDF")
    p_build.add_argument("--no-contrast", dest="no_contrast", action="store_true",
                         help="Skip the text/background contrast probe")
    p_build.add_argument("--strict", action="store_true",
                         help="Exit non-zero when measurable QA gates fail")
    p_build.add_argument("--css", dest="css", action="append", metavar="FILE",
                         help="Extra CSS file for this document (repeatable)")
    p_build.set_defaults(func=cmd_build)

    p_check = sub.add_parser("check", help="Measure a finished PDF against the design gates")
    p_check.add_argument("pdf", help="Path to the PDF")
    p_check.add_argument("--source", help="Source document, to recover declared type sizes")
    p_check.add_argument("--body-size", dest="body_size", type=float,
                         help="Expected body size in pt")
    p_check.add_argument("--min-font", dest="min_font", type=float, default=9.0,
                         help="Minimum allowed text size in pt (default: 9)")
    p_check.add_argument("--measure", type=float, help="Target line measure in characters")
    p_check.add_argument("--cover-pages", dest="cover_pages", type=int, default=None,
                         help="Leading pages to exclude from body checks")
    p_check.add_argument("--previews", help="Directory for PNG previews")
    p_check.add_argument("--pages", type=int, default=6, help="Preview page count")
    p_check.add_argument('--design-manifest', help='Design intent JSON; defaults to the PDF sibling .design.json')
    p_check.add_argument("--json", action="store_true", help="Also print JSON")
    p_check.set_defaults(func=cmd_check)

    p_images = sub.add_parser("images", help="Build a candidate contact sheet for visual review")
    p_images.add_argument("query", help="Image search query")
    p_images.add_argument("--out", default="image-candidates.jpg",
                          help="Where to write the contact sheet")
    p_images.add_argument("--count", type=int, default=12, help="Candidate count")
    p_images.add_argument("--columns", type=int, default=4, help="Sheet columns")
    p_images.set_defaults(func=cmd_images)

    p_themes = sub.add_parser("themes", help="List design systems")
    p_themes.set_defaults(func=cmd_themes)

    p_scen = sub.add_parser("scenarios", help="List document scenarios")
    p_scen.set_defaults(func=cmd_scenarios)

    p_inspect = sub.add_parser("inspect", help="Analyse an existing PDF")
    p_inspect.add_argument("pdf", help="Path to the PDF")
    p_inspect.add_argument("--previews", help="Directory for PNG previews")
    p_inspect.add_argument("--pages", type=int, default=6, help="Preview page count")
    p_inspect.add_argument("--json", action="store_true", help="Also print JSON")
    p_inspect.set_defaults(func=cmd_inspect)

    p_designs = sub.add_parser("designs", help="Map themes to scenarios")
    p_designs.set_defaults(func=cmd_designs)

    p_compositions = sub.add_parser('compositions', help='List content/asset composition families')
    p_compositions.set_defaults(func=cmd_compositions)
    p_directions = sub.add_parser("directions", help="List legacy direction aliases")
    p_directions.set_defaults(func=cmd_directions)

    p_copy = sub.add_parser("copycheck", help="Check prose for em dashes, emoji and AI tells")
    p_copy.add_argument("input", help="Source file to check")
    p_copy.add_argument("--locale", choices=["en-GB", "en-US"],
                        help="Enforce one spelling locale")
    p_copy.set_defaults(func=cmd_copycheck)

    return parser


def main(argv: list[str] | None = None) -> int:
    # Source titles/credits can be Unicode even on a legacy Windows console.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
