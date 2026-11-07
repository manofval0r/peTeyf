import unittest
from pathlib import Path
import fitz
from pdfstudio.content import Document
from pdfstudio.blocks import parse_blocks
from pdfstudio.design import resolve_design
from pdfstudio.geometry import resolve_geometry
from pdfstudio.compositions import plan_sections
from pdfstudio.render import RenderOptions
try:
    from pdfstudio import design_qa
except ImportError:
    design_qa=None

class DesignQATests(unittest.TestCase):
    def manifest(self):
        self.assertIsNotNone(design_qa,'Design manifest missing')
        doc=Document({'theme':'midnight'},'<h1 id="intro">Introduction</h1><p>A readable paragraph.</p>',[])
        d=resolve_design(doc,RenderOptions(Path('out/test.pdf'))); g=resolve_geometry('A4',False,'print')
        m=design_qa.build_design_manifest(d,g,plan_sections(parse_blocks(doc),d,{},g,doc.meta),{},False)
        m['sections'][0]['pages']=[1]
        return m
    def pdf(self,colour,x=60):
        folder=Path('out/skill-upgrade/qa-tests'); folder.mkdir(parents=True,exist_ok=True)
        path=folder/'test.pdf'
        pdf=fitz.open(); p=pdf.new_page(width=210*72/25.4,height=297*72/25.4)
        p.draw_rect(p.rect,color=None,fill=colour)
        p.insert_text((x,80),'Introduction',fontsize=12)
        p.insert_text((x,110),'A readable paragraph.',fontsize=10)
        pdf.save(path); pdf.close(); return path
    def test_manifest_explains_theme_and_family(self):
        m=self.manifest(); self.assertEqual(m['theme'],'midnight'); self.assertEqual(m['schema_version'],1); self.assertTrue(m['reasons'])
    def test_manifest_has_no_embedded_asset_bytes(self):
        import json
        self.assertNotIn('data:image',json.dumps(self.manifest()))
    def test_white_frame_detected_for_full_field(self):
        r=design_qa.check_design(self.pdf((1,1,1)),self.manifest()) if design_qa else None
        self.assertIsNotNone(r,'Design QA missing'); self.assertFalse(r['passed']); self.assertTrue(any(i['code']=='page_field' for i in r['issues']))
    def test_safe_inset_violation_detected(self):
        m=self.manifest(); r=design_qa.check_design(self.pdf((11/255,16/255,32/255),x=10),m)
        self.assertTrue(any(i['code']=='safe_area' for i in r['issues']))
    def test_manifest_round_trip(self):
        import json
        m=self.manifest(); self.assertEqual(json.loads(json.dumps(m)),m)
    def test_missing_block_detected_even_if_clipped(self):
        m=self.manifest(); m['expected_text']=['An entirely absent source paragraph.']
        r=design_qa.check_design(self.pdf((11/255,16/255,32/255)),m)
        self.assertTrue(any(i['code']=='missing_content' for i in r['issues']))
    def test_intentional_feature_sparse_is_reported_not_rejected(self):
        m=self.manifest(); m['sections'][0]['treatment']='feature'
        r=design_qa.check_design(self.pdf((11/255,16/255,32/255)),m)
        self.assertTrue(r['passed']); self.assertTrue(r['exceptions'])
    def test_near_empty_spill_warned(self):
        r=design_qa.check_design(self.pdf((11/255,16/255,32/255)),self.manifest())
        self.assertTrue(any(i['code']=='sparse_flow' for i in r['issues']))
    def test_ambiguous_mapping_cannot_claim_design_pass(self):
        m=self.manifest(); m['sections'][0]['pages']=[]
        r=design_qa.check_design(self.pdf((11/255,16/255,32/255)),m)
        self.assertFalse(r['passed'])

if __name__=='__main__': unittest.main()
