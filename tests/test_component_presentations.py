import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from pdfstudio.content import Document
from pdfstudio.render import _css
from pdfstudio.tokens import get_theme
from pdfstudio.scenarios import get_scenario
from pdfstudio.art_direction import DIRECTIONS
try:
    from pdfstudio.blocks import ContentBlock, present_block
except ImportError:
    ContentBlock=present_block=None

class ComponentTests(unittest.TestCase):
    def styles(self,html,selector):
        css=_css(get_theme('editorial'),get_scenario('report'),DIRECTIONS['editorial-contrast'],210,297,{},stamp=False)
        with sync_playwright() as pw:
            browser=pw.chromium.launch(); page=browser.new_page()
            page.set_content('<html><style>'+css+'</style><body class="doc" data-theme="editorial"><main class="content">'+html+'</main></body></html>')
            page.emulate_media(media='print')
            result=page.locator(selector).evaluate('(el)=>{const s=getComputedStyle(el);return {border:s.borderTopWidth,background:s.backgroundColor,font:s.fontSize};}')
            browser.close(); return result
    def test_open_metrics_have_no_card_perimeter(self):
        self.assertIsNotNone(ContentBlock,'Presentation model missing')
        h=present_block(ContentBlock('b','metrics','<div class="metrics"><div class="metric">25</div></div>','s'),'open')
        s=self.styles(h,'.metric'); self.assertEqual(s['border'],'0px'); self.assertEqual(s['background'],'rgba(0, 0, 0, 0)')
    def test_warning_keeps_readable_semantic_label(self):
        self.assertIsNotNone(ContentBlock,'Presentation model missing')
        h=present_block(ContentBlock('b','callout','<aside class="callout callout--warning"><strong>Warning</strong><p>A risk.</p></aside>','s'),'alert')
        self.assertIn('Warning',h); self.assertIn('variant--alert',h)
    def test_theme_heading_selector_matches_chapter_h2(self):
        h='<section class="chapter"><h2>Heading</h2></section>'
        # Editorial h2 must get the same defined size inside the chapter.
        self.assertEqual(self.styles(h,'h2')['font'],self.styles('<h2>Heading</h2>','h2')['font'])
    def test_swot_only_when_supplied(self):
        self.assertNotIn('swot',Document({},'<p>No matrix needed.</p>',[]).body_html)

if __name__=='__main__': unittest.main()
