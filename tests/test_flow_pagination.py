import unittest
from pathlib import Path
import fitz
from pdfstudio.content import load_document
from pdfstudio.render import render, RenderOptions

class FlowTests(unittest.TestCase):
    def build(self,source):
        out=Path('out/skill-upgrade/flow-tests'); out.mkdir(parents=True,exist_ok=True)
        p=out/'input.md'; p.write_text(source,encoding='utf-8')
        return render(load_document(p),RenderOptions(out/'test.pdf',images='off',preview=False,contrast=False,keep_html=True))
    def test_short_section_not_forced_full_page(self):
        r=self.build('---\ntitle: Guide\nauthor: Test\ntheme: editorial\ncover: false\ntoc: false\n---\n# First\n\nShort paragraph.\n\n# Second\n\nAnother short paragraph.')
        with fitz.open(r.pdf_path) as pdf:
            self.assertEqual(len(pdf),1)
            self.assertIn('Second',pdf[0].get_text())
    def test_long_flow_preserves_every_block(self):
        source='---\ntitle: Guide\nauthor: Test\ntheme: editorial\ncover: false\ntoc: false\n---\n# Flow\n\n'+ '\n\n'.join(f'RECORD{i:03d}: Readable source content about evidence and delivery. It remains in order and is never hidden by an overflowing panel.' for i in range(80))
        r=self.build(source)
        with fitz.open(r.pdf_path) as pdf:
            text=''.join(p.get_text() for p in pdf)
            self.assertGreater(len(pdf),1)
            for i in range(80): self.assertIn(f'RECORD{i:03d}',text)
    def test_mixed_fields_keep_continuation_colour(self):
        source='---\ntitle: Guide\nauthor: Test\ntheme: editorial\ncover: false\ntoc: false\ndesign:\n  sections:\n    feature:\n      role: feature\n      field: accent\n---\n# Introduction {#intro}\n\nFirst paragraph.\n\n# Feature {#feature}\n\nA deliberate feature page.\n\n# Follow up {#follow}\n\nBack to ordinary flow.'
        r=self.build(source)
        with fitz.open(r.pdf_path) as pdf:
            self.assertEqual(len(pdf),3)
            self.assertIn('Feature',pdf[1].get_text())
            a=pdf[0].get_pixmap(alpha=False).pixel(3,100)
            b=pdf[1].get_pixmap(alpha=False).pixel(3,100)
            c=pdf[2].get_pixmap(alpha=False).pixel(3,100)
            self.assertNotEqual(a,b); self.assertEqual(a,c)
    def test_rendered_dom_matches_family_plan(self):
        r=self.build('---\ntitle: Review\ntheme: swiss\ncomposition: evidence-led\ncover: false\ntoc: false\n---\n# Findings\n\nA finding.\n\nAnother finding.')
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(); page=browser.new_page()
            page.goto(r.html_path.as_uri()); page.emulate_media(media='print')
            columns=page.locator('.chapter').evaluate('(el)=>getComputedStyle(el).gridTemplateColumns.split(" ").length')
            self.assertEqual(columns,2)
            browser.close()

if __name__=='__main__': unittest.main()
