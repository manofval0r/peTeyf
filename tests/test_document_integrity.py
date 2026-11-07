import unittest
from pathlib import Path
import re
import fitz
from pdfstudio.content import load_document
from pdfstudio.render import render, RenderOptions

ROOT=Path(__file__).resolve().parents[1]

class IntegrityTests(unittest.TestCase):
    def build(self,name,body,meta=''):
        out=ROOT/'out'/'skill-upgrade'/'integrity-tests'/name; out.mkdir(parents=True,exist_ok=True)
        source=out/'input.md'
        source.write_text('---\ntitle: Integrity check\nauthor: PDF Studio QA\ntheme: editorial\ncomposition: editorial-narrative\nscenario: report\n'+meta+'---\n'+body,encoding='utf-8')
        return render(load_document(source),RenderOptions(out/'document.pdf',preview=False,contrast=False,images='off'))
    def test_toc_numbers_match_actual_destinations(self):
        meta='toc: true\ndesign:\n  sections:\n    light:\n      role: feature\n    water:\n      role: feature\n'
        r=self.build('toc','# Light {#light}\n\nA section about useful light.\n\n# Water {#water}\n\nA section about careful watering.',meta)
        with fitz.open(r.pdf_path) as pdf:
            links=pdf[1].get_links()
            self.assertEqual(len(links),2)
            for link in links:
                text=pdf[1].get_textbox(fitz.Rect(link['from']))
                digits=re.findall(r'\d+',text)
                self.assertTrue(digits,text)
                self.assertEqual(int(digits[-1]),link['page']+1)
                self.assertGreater(link['page'],1)
    def test_long_table_repeats_header_and_preserves_rows(self):
        rows=''.join(f'<tr><td>RECORD{i:03d}</td><td>Recorded result</td><td>Ready for review</td></tr>' for i in range(80))
        r=self.build('table','<h1 id="records">Records</h1><table><thead><tr><th>Item</th><th>Status</th><th>Outcome</th></tr></thead><tbody>'+rows+'</tbody></table>','cover: false\ntoc: false\n')
        with fitz.open(r.pdf_path) as pdf:
            text=''.join(p.get_text() for p in pdf)
            self.assertGreater(len(pdf),1)
            for i in range(80): self.assertIn(f'RECORD{i:03d}',text)
            for page in pdf:
                if 'RECORD' in page.get_text(): self.assertIn('STATUS',page.get_text().upper())
    def test_oversized_note_splits_without_losing_text(self):
        body='<h1 id="note">An extended note</h1><aside class="callout callout--note"><p class="callout__title">Delivery note</p>'+''.join(f'<p>NOTE{i:03d}: Keep the complete evidence with the decision. This paragraph must survive pagination at its declared readable size.</p>' for i in range(70))+'</aside>'
        r=self.build('note',body,'cover: false\ntoc: false\n')
        with fitz.open(r.pdf_path) as pdf:
            text=''.join(p.get_text() for p in pdf)
            self.assertGreater(len(pdf),1)
            for i in range(70): self.assertIn(f'NOTE{i:03d}',text)
            self.assertGreaterEqual(r.report['fonts']['min_used_pt'],8.99)
    def test_caption_moves_with_figure(self):
        from tests.render_design_gallery import make_assets
        make_assets(); image=(ROOT/'out'/'skill-upgrade'/'gallery-assets'/'portrait.png').as_posix()
        paragraphs='\n\n'.join('A complete explanation keeps the relevant evidence beside the claim and leaves the page readable across different formats.' for _ in range(20))
        body='# Context {#context}\n\n'+paragraphs+f'\n\n![Synthetic portrait geometry, used only for a caption-placement test.](img:{image})'
        r=self.build('caption',body,'cover: false\ntoc: false\ndesign:\n  assets:\n    "@@IMG_1@@":\n      role: photo\n      approved: true\n')
        with fitz.open(r.pdf_path) as pdf:
            placed=[p for p in pdf if any(b['type']==1 for b in p.get_text('dict')['blocks'])]
            self.assertEqual(len(placed),1)
            self.assertIn('Synthetic portrait geometry',placed[0].get_text())

if __name__=='__main__': unittest.main()
