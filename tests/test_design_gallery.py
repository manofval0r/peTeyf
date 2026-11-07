import unittest
from pathlib import Path
try:
    from tests import render_design_gallery as gallery
except ImportError:
    gallery=None
from pdfstudio.content import load_document
from pdfstudio.design import resolve_design
from pdfstudio.blocks import parse_blocks
from pdfstudio.compositions import plan_sections, composition_signature
from pdfstudio.geometry import resolve_geometry
from pdfstudio.render import RenderOptions

class GalleryTests(unittest.TestCase):
    def test_gallery_uses_locked_theme_with_six_body_grammars(self):
        self.assertIsNotNone(gallery,'Representative skill fixtures missing')
        signatures=set()
        for file in gallery.FIXTURES:
            doc=load_document(file)
            d=resolve_design(doc,RenderOptions(Path('out/test.pdf')))
            self.assertEqual(d.theme_id,'swiss')
            signatures.add(composition_signature(plan_sections(parse_blocks(doc),d,{},resolve_geometry('A4',False,'print'),doc.meta)))
        self.assertEqual(len(signatures),6)
    def test_optional_assets_do_not_create_dead_slots(self):
        self.assertIsNotNone(gallery,'Gallery missing')
        self.assertEqual(len(gallery.FIXTURES),6)
        for path in gallery.FIXTURES:
            self.assertTrue(path.is_file())
            self.assertNotIn('--css',path.read_text(encoding='utf-8'))
    def test_gallery_runner_available(self):
        self.assertIsNotNone(gallery,'Gallery missing')
        self.assertTrue(callable(gallery.render_gallery))

if __name__=='__main__': unittest.main()
