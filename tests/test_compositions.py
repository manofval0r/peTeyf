import unittest
from pathlib import Path
from pdfstudio.blocks import parse_blocks
from pdfstudio.content import Document
from pdfstudio.render import RenderOptions
from pdfstudio.design import resolve_design, FAMILIES
from pdfstudio.geometry import resolve_geometry
from pdfstudio.asset_layout import AssetLayout
try:
    from pdfstudio import compositions
except ImportError:
    compositions=None

class CompositionTests(unittest.TestCase):
    def plan(self,family,asset=None,meta=None):
        self.assertIsNotNone(compositions,'Composition families missing')
        meta={'theme':'swiss','composition':family,**(meta or {})}
        doc=Document(meta,'<h1 id="summary">Overview</h1><p>Evidence.</p><p>@@IMG_1@@</p><div class="metrics"><div class="metric">20</div></div>',[])
        blocks=parse_blocks(doc)
        return compositions.plan_sections(blocks,resolve_design(doc,RenderOptions(Path('out/test.pdf'))),{'@@IMG_1@@':asset} if asset else {},resolve_geometry('A4',False,'print'),meta)
    def test_six_families_have_distinct_body_signatures(self):
        signatures={compositions.composition_signature(self.plan(f)) for f in FAMILIES} if compositions else set()
        self.assertEqual(len(signatures),6)
    def test_asset_aspect_changes_photo_placement(self):
        a=AssetLayout('@@IMG_1@@','photo',600,1200,.5,False,'contain',(.5,.5),None,True)
        b=AssetLayout('@@IMG_1@@','photo',1200,400,3,False,'contain',(.5,.5),None,True)
        self.assertEqual(self.plan('photo-essay',a)[0].columns,2)
        self.assertEqual(self.plan('photo-essay',b)[0].columns,1)
    def test_object_uses_contain_stage(self):
        a=AssetLayout('@@IMG_1@@','object',800,1200,2/3,True,'contain',(.5,.5),None,True)
        self.assertEqual(self.plan('object-catalogue',a)[0].columns,2)
    def test_explicit_family_not_changed_by_photo(self):
        a=AssetLayout('@@IMG_1@@','photo',800,1200,2/3,False,'contain',(.5,.5),None,True)
        self.assertEqual(self.plan('institutional-paper',a)[0].family_id,'institutional-paper')
    def test_no_image_has_text_fallback(self):
        self.assertEqual(self.plan('photo-essay')[0].columns,1)
        self.assertEqual(self.plan('object-catalogue')[0].columns,1)
    def test_invalid_section_reference_rejected(self):
        self.assertIsNotNone(compositions,'Composition families missing')
        with self.assertRaisesRegex(ValueError,'section'):
            self.plan('editorial-narrative',meta={'design':{'sections':{'unknown':{'role':'feature'}}}})
    def test_role_independent_of_english_heading(self):
        plan=self.plan('editorial-narrative',meta={'design':{'sections':{'summary':{'role':'feature','field':'panel'}}}})
        self.assertEqual(plan[0].treatment,'feature')
        self.assertEqual(plan[0].field,'panel')
    def test_asset_accent_never_overrides_locked_theme(self):
        self.assertIsNotNone(compositions,'Composition families missing')
        doc=Document({'theme':'swiss'},'',[])
        d=resolve_design(doc,RenderOptions(Path('out/test.pdf')))
        a=AssetLayout('a','object',20,20,1,True,'contain',(.5,.5),None,True,'#123456')
        self.assertEqual(compositions.apply_asset_accent(d,{'a':a}).tokens.palette.accent,d.tokens.palette.accent)
    def test_short_section_not_forced_full_page(self):
        plan=self.plan('editorial-narrative')
        self.assertEqual(plan[0].treatment,'flow')

class AdaptiveCompositionTests(unittest.TestCase):
    def test_reviewed_object_selects_catalogue_when_family_is_auto(self):
        doc=Document({'title':'Form and function','scenario':'portfolio'},'<h1 id="intro">Overview</h1><p>@@IMG_1@@</p>',[])
        d=resolve_design(doc,RenderOptions(Path('out/test.pdf')))
        self.assertTrue(hasattr(compositions,'adapt_composition'),'Asset-led inference missing')
        a=AssetLayout('@@IMG_1@@','object',800,1200,2/3,True,'contain',(.5,.5),None,True)
        self.assertEqual(compositions.adapt_composition(d,parse_blocks(doc),{'a':a}).family_id,'object-catalogue')
    def test_reviewed_photo_does_not_override_explicit_family(self):
        doc=Document({'composition':'institutional-paper'},'<h1>Overview</h1>',[])
        d=resolve_design(doc,RenderOptions(Path('out/test.pdf')))
        self.assertTrue(hasattr(compositions,'adapt_composition'),'Asset-led inference missing')
        a=AssetLayout('a','photo',800,1200,2/3,False,'contain',(.5,.5),None,True)
        self.assertEqual(compositions.adapt_composition(d,parse_blocks(doc),{'a':a}).family_id,'institutional-paper')

if __name__=='__main__': unittest.main()
