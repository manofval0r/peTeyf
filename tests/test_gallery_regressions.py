import unittest
from pathlib import Path
import fitz
from pdfstudio.content import Document, ChartRequest
from pdfstudio.render import RenderOptions, render, _css
from pdfstudio.tokens import get_theme
from pdfstudio.scenarios import get_scenario
from pdfstudio.art_direction import DIRECTIONS
from pdfstudio.design_qa import check_design

class GalleryRegressionTests(unittest.TestCase):
    def build(self,doc,name):
        folder=Path('out/skill-upgrade/gallery-regressions')/name; folder.mkdir(parents=True,exist_ok=True)
        return render(doc,RenderOptions(folder/'document.pdf',preview=False,contrast=False,images='off',cover=False,toc=False))
    def test_display_heading_inside_safe_area_uses_ink_bounds(self):
        r=self.build(Document({'theme':'swiss','title':'Test','author':'Test'},'<h1 id="intro">A display heading</h1><p>A readable paragraph underneath the heading.</p>',[]),'heading')
        self.assertTrue(r.report['design']['passed'],r.report['design']['issues'])
    def test_reordered_inline_text_is_not_missing(self):
        body='<h1 id="intro">A decision</h1><div class="metrics"><div class="metric"><span class="metric__label">Baseline measure</span><span class="metric__value">120</span><span class="metric__delta">Synthetic observation</span></div></div>'
        r=self.build(Document({'theme':'swiss','title':'Test','author':'Test'},body,[]),'inline')
        self.assertFalse(any(i['code']=='missing_content' for i in r.report['design']['issues']))
    def test_generated_chart_needs_no_photo_credits(self):
        doc=Document({'theme':'swiss','title':'Test','author':'Test'},'<h1 id="intro">A comparison</h1>@@CHART_1@@',[],chart_requests=[ChartRequest('@@CHART_1@@','bar','Synthetic comparison',['A','B'],[[2,3]])])
        r=self.build(doc,'chart')
        self.assertFalse(any(i['code']=='missing_credits' for i in r.report['issues']))
    def test_pseudo_numbers_have_9pt_floor(self):
        r=self.build(Document({'theme':'swiss','scenario':'academic','title':'Test','author':'Test'},'<h1 id="intro">Abstract</h1><p>Enough introductory text for the page.</p><h2 id="method">Method</h2><p>A readable method.</p>',[]),'numbers')
        with fitz.open(r.pdf_path) as pdf:
            sizes=[s['size'] for p in pdf for b in p.get_text('dict')['blocks'] if b['type']==0 for l in b['lines'] for s in l['spans'] if s['text'].strip()]
            self.assertGreaterEqual(min(sizes),8.99)
    def test_portrait_uses_available_safe_height(self):
        from playwright.sync_api import sync_playwright
        css=_css(get_theme('swiss'),get_scenario('brochure'),DIRECTIONS['editorial-contrast'],210,297,{},stamp=False)
        html='<main class="content"><section class="chapter family--photo-essay columns--2"><div class="block--figure"><figure class="figure"><img width="1000" height="1600" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7" /></figure></div></section></main>'
        with sync_playwright() as pw:
            b=pw.chromium.launch(); page=b.new_page(); page.set_content('<style>'+css+'</style>'+html)
            height=page.locator('img').evaluate('(el)=>parseFloat(getComputedStyle(el).maxHeight)')
            self.assertGreater(height,300); b.close()

class SpillTests(unittest.TestCase):
    def build_fixture(self,name):
        from tests.render_design_gallery import ROOT, make_assets
        from pdfstudio.content import load_document
        make_assets()
        out=ROOT/'out'/'skill-upgrade'/'spill-tests'/name
        out.mkdir(parents=True,exist_ok=True)
        return render(load_document(ROOT/'tests'/'fixtures'/'design'/f'{name}.md'),RenderOptions(out/'document.pdf',images='off',preview=False,contrast=False))
    def test_compact_comparison_has_no_two_line_spill(self):
        r=self.build_fixture('evidence')
        self.assertGreaterEqual(r.report['images'],1)
        self.assertEqual(r.pages,2)
    def test_catalogue_has_no_credits_only_spill(self):
        r=self.build_fixture('object')
        self.assertGreaterEqual(r.report['images'],1)
        self.assertEqual(r.pages,2)

if __name__=='__main__': unittest.main()
