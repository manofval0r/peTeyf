import tempfile
import unittest
from pathlib import Path
try:
    from pdfstudio import blocks
except ImportError:
    blocks=None
from pdfstudio.content import Document, load_document

class ContentBlockTests(unittest.TestCase):
    def test_block_order_and_slots_preserved(self):
        self.assertIsNotNone(blocks,'Semantic blocks missing')
        doc=Document({},'<h1 id="intro">Intro</h1><p>Text</p><p>@@IMG_1@@</p><p>@@CHART_1@@</p>',[])
        result=blocks.parse_blocks(doc)
        self.assertEqual([b.kind for b in result],['heading','paragraph','figure','chart'])
        self.assertEqual(result[2].request_slot,'@@IMG_1@@')
        self.assertEqual(''.join(b.html for b in result),doc.body_html)
    def test_json_and_html_keep_anchors(self):
        folder=Path('out/skill-upgrade/block-tests'); folder.mkdir(parents=True,exist_ok=True)
        for ext,text in (('html','<h1 id="stable">Renamed overview</h1><p>Body</p>'),('json','{"html":"<h1 id=\"stable\">Renamed overview</h1><p>Body</p>"}')):
            # JSON is produced normally to avoid escaping being the tested behavior.
            if ext=='json':
                import json
                text=json.dumps({'html':'<h1 id="stable">Renamed overview</h1><p>Body</p>'})
            path=folder/f'input.{ext}'; path.write_text(text,encoding='utf-8')
            self.assertIn('id="stable"',load_document(path).body_html)
    def test_unknown_html_is_opaque_flow(self):
        self.assertIsNotNone(blocks,'Semantic blocks missing')
        raw='<aside data-custom="yes"><strong>Unusual</strong><span>markup</span></aside>'
        parsed=blocks.parse_blocks(Document({},raw,[]))
        self.assertEqual(parsed[0].kind,'flow')
        self.assertEqual(parsed[0].html,raw)
    def test_empty_source_has_no_fabricated_components(self):
        self.assertIsNotNone(blocks,'Semantic blocks missing')
        self.assertEqual(blocks.parse_blocks(Document({},'',[])),())
    def test_renamed_heading_keeps_stable_role(self):
        self.assertIsNotNone(blocks,'Semantic blocks missing')
        a=blocks.parse_blocks(Document({},'<h1 id="summary">Executive summary</h1><p>A.</p>',[]))
        b=blocks.parse_blocks(Document({},'<h1 id="summary">Overview</h1><p>A.</p>',[]))
        self.assertEqual([x.section_id for x in a],[x.section_id for x in b])

class MetadataTests(unittest.TestCase):
    def test_nested_design_requires_real_yaml_parser(self):
        from unittest.mock import patch
        from pdfstudio import content
        with patch.object(content,'yaml',None), self.assertRaisesRegex(ValueError,'PyYAML'):
            content.parse_frontmatter('---\ndesign:\n  assets:\n    cover:\n      role: object\n---\nBody')
    def test_invalid_yaml_does_not_silently_default(self):
        from pdfstudio.content import parse_frontmatter
        with self.assertRaisesRegex(ValueError,'frontmatter'):
            parse_frontmatter('---\ntheme: [unclosed\n---\nBody')

if __name__=='__main__': unittest.main()
