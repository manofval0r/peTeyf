import unittest
from pathlib import Path
import tempfile
import fitz
from pdfstudio.content import Document
from pdfstudio.render import render, RenderOptions, _css
from pdfstudio.tokens import get_theme
from pdfstudio.art_direction import DIRECTIONS
from pdfstudio.scenarios import get_scenario

class PagePaintTests(unittest.TestCase):
    def build(self,meta,body,**options):
        folder=Path('out/skill-upgrade/paint-tests')
        folder.mkdir(parents=True,exist_ok=True)
        tmp=tempfile.TemporaryDirectory(dir=folder)
        self.addCleanup(tmp.cleanup)
        return render(Document(meta,body,[]),RenderOptions(output=Path(tmp.name)/'test.pdf',images='off',preview=False,contrast=False,**options))
    def test_field_reaches_all_sheet_edges(self):
        r=self.build({'theme':'midnight','cover':False},'<h1 id="intro">Introduction</h1><p>Readable text inside a field.</p>',cover=False)
        with fitz.open(r.pdf_path) as pdf:
            pix=pdf[0].get_pixmap(alpha=False)
            for x,y in ((3,3),(pix.width//2,3),(pix.width-4,3),(3,pix.height//2),(pix.width-4,pix.height//2),(3,pix.height-4),(pix.width//2,pix.height-4),(pix.width-4,pix.height-4)):
                self.assertTrue(all(abs(a-b)<=3 for a,b in zip(pix.pixel(x,y),(11,16,32))),pix.pixel(x,y))
    def test_continuation_keeps_field_and_safe_text(self):
        body='<h1 id="intro">Introduction</h1>'+''.join(f'<p>Record {i}: A complete readable account of delivery, decisions and evidence across the programme. Details remain in source order.</p>' for i in range(65))
        r=self.build({'theme':'midnight','cover':False,'header':False,'footer':False},body,cover=False)
        with fitz.open(r.pdf_path) as pdf:
            self.assertGreater(len(pdf),1)
            for page in pdf:
                self.assertTrue(all(abs(a-b)<=3 for a,b in zip(page.get_pixmap(alpha=False).pixel(3,100),(11,16,32))))
                for block in page.get_text('blocks'):
                    if block[6]==0:
                        self.assertGreaterEqual(block[0],18*72/25.4-1)
                        self.assertLessEqual(block[2],page.rect.width-18*72/25.4+1)
            self.assertIn('Record 64',pdf[-1].get_text())
    def test_cover_matches_each_format(self):
        for size,landscape in (('A4',False),('Letter',False),('A5',False),('A4',True)):
            r=self.build({'title':'Garden guide','author':'Test','theme':'editorial','toc':False},'<h1 id="intro">Introduction</h1><p>Keep the material readable.</p>',page_size=size,landscape=landscape,toc=False)
            with fitz.open(r.pdf_path) as pdf:
                self.assertEqual(len(pdf),2,(size,landscape,len(pdf)))
                self.assertIn('Garden',pdf[0].get_text())
                self.assertIn('Introduction',pdf[1].get_text())
    def test_furniture_floor_and_contrast(self):
        r=self.build({'title':'Garden guide','author':'Test','theme':'midnight','cover':False},'<h1 id="intro">Introduction</h1><p>Keep labels readable.</p>',cover=False)
        with fitz.open(r.pdf_path) as pdf:
            for page in pdf:
                spans=[s for b in page.get_text('dict')['blocks'] if b['type']==0 for l in b['lines'] for s in l['spans'] if s['text'].strip()]
                self.assertGreaterEqual(min(s['size'] for s in spans),8.99)
    def test_cli_page_size_beats_frontmatter(self):
        r=self.build({'theme':'editorial','cover':False,'page_size':'A5'},'<h1 id="intro">Introduction</h1><p>Text.</p>',cover=False,page_size='Letter')
        with fitz.open(r.pdf_path) as pdf:
            self.assertAlmostEqual(pdf[0].rect.width,215.9*72/25.4,delta=1)

if __name__=='__main__': unittest.main()
