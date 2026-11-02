# PDF Studio

Design-first PDF generation: Markdown/JSON/HTML → art-directed, print-ready PDF.

```bash
python -m pdfstudio build examples/marketing-plan.md --out out.pdf --preview-pages 12
```

- 14 scenarios (report, marketing-plan, proposal, invoice, whitepaper, case-study, resume, one-pager, academic, brochure, certificate, newsletter, portfolio, pitch-deck)
- 11 design systems (editorial, swiss, modern-saas, luxury, academic, brutalist, minimal, corporate, warm-sage, midnight, vibrant)
- Web image sourcing with attribution (Wikimedia + Wikipedia primary; Openverse fallback)
- Metrics / SWOT / chart blocks (pre-processed before Markdown conversion)
- Two-pass TOC with actual page numbers; header/footer/page-stamp via PyMuPDF
- QA via PNG previews + structural inspection

Install: see `install.ps1`. Dependencies listed in `requirements.txt`.
