import copy
import unittest
from pathlib import Path
try:
    from pdfstudio import design
except ImportError:
    design = None
from pdfstudio.art_direction import infer_direction
from pdfstudio.content import Document
from pdfstudio.render import RenderOptions
from pdfstudio.tokens import get_theme, THEMES
from pdfstudio.scenarios import get_scenario

class DesignSelectionTests(unittest.TestCase):
    def decide(self, meta, **opts):
        self.assertIsNotNone(design, 'Explainable design resolver is missing')
        return design.resolve_design(Document(meta, '<h1>Overview</h1><p>Clear decisions.</p>', []), RenderOptions(Path('out/test.pdf'), **opts))

    def test_explicit_theme_survives_auto_direction(self):
        for theme in ('modern-saas', 'luxury', 'warm-sage'):
            with self.subTest(theme=theme):
                result = self.decide({'title': 'Cloud software platform', 'theme': theme})
                base = get_theme(theme)
                for key in ('palette', 'fonts', 'radius', 'body_size'):
                    self.assertEqual(getattr(result.tokens, key), getattr(base, key))
                self.assertIn('palette', result.locked_fields)

    def test_cli_theme_beats_frontmatter_theme(self):
        self.assertEqual(self.decide({'theme': 'warm-sage'}, theme='luxury').theme_id, 'luxury')

    def test_explicit_direction_does_not_replace_locked_theme(self):
        result = self.decide({'theme': 'luxury', 'art_direction': 'technical-field'})
        self.assertEqual(result.family_id, 'technical-reference')
        self.assertEqual(result.tokens.palette, get_theme('luxury').palette)
        self.assertTrue(result.family_locked)

    def test_base_theme_not_mutated(self):
        before = copy.deepcopy(THEMES)
        self.decide({'theme': 'editorial', 'brand': {'palette': {'accent': '#123456'}}})
        self.assertEqual(before, THEMES)

    def test_invalid_explicit_ids_fail(self):
        for meta in ({'theme': 'nope'}, {'scenario': 'nope'}, {'composition': 'nope'}, {'art_direction': 'nope'}):
            with self.subTest(meta=meta), self.assertRaisesRegex(ValueError, 'Supported'):
                self.decide(meta)
        with self.assertRaises(ValueError):
            get_theme('nope')
        with self.assertRaises(ValueError):
            get_scenario('nope')

    def test_ai_not_substring(self):
        for title in ('Retail launch', 'Chair catalogue', 'Portrait collection', 'Local repairs', 'Campaign plan'):
            with self.subTest(title=title):
                self.assertNotEqual(infer_direction({'title': title}, 'report', '', 'editorial').id, 'technical-field')
        self.assertEqual(infer_direction({'title': 'AI systems'}, 'report', '', 'editorial').id, 'technical-field')

    def test_phrase_boundaries(self):
        self.assertIsNotNone(design, 'Keyword matcher missing')
        self.assertEqual(design.match_keywords('The fashion house', ('fashion house', 'ai')), ('fashion house',))
        self.assertEqual(design.match_keywords('fashion household', ('fashion house',)), ())

    def test_case_study_label_not_subject(self):
        self.assertNotEqual(infer_direction({'title': 'A customer case study'}, 'case-study', '', 'editorial').id, 'scholarly-book')

    def test_tied_subject_has_neutral_explanation(self):
        result = self.decide({'title': 'Software and research'})
        self.assertEqual(result.family_id, 'editorial-narrative')
        self.assertTrue(any('ambiguous' in reason.lower() for reason in result.reasons))

    def test_explicit_industry_outweighs_incidental_body_word(self):
        self.assertIsNotNone(design, 'Resolver missing')
        doc = Document({'industry': 'finance'}, '<p>Software supports delivery.</p>', [])
        result = design.resolve_design(doc, RenderOptions(Path('out/test.pdf')))
        self.assertEqual(result.family_id, 'evidence-led')

    def test_brand_overrides_are_locked(self):
        result = self.decide({'theme': 'swiss', 'brand': {'palette': {'accent': '#123456'}}})
        self.assertEqual(result.tokens.palette.accent, '#123456')
        self.assertIn('accent', result.locked_fields)

    def test_scenario_theme_is_neutral_fallback(self):
        result=self.decide({'scenario':'marketing-plan','title':'An undecided brief'})
        self.assertEqual(result.theme_id,get_scenario('marketing-plan').default_theme)
    def test_brief_composition_beats_scenario(self):
        result=self.decide({'scenario':'one-pager','design':{'composition':'institutional-paper'}})
        self.assertEqual(result.family_id,'institutional-paper')

if __name__ == '__main__':
    unittest.main()
