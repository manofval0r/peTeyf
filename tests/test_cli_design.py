import tempfile
import unittest
from pathlib import Path
from pdfstudio.cli import build_parser, _expect_from_source
from pdfstudio.tokens import get_theme

class CLIDesignTests(unittest.TestCase):
    def test_new_design_options_exist(self):
        parser = build_parser()
        build = next(a for a in parser._actions if getattr(a, 'choices', None)).choices['build']
        options = {o for a in build._actions for o in a.option_strings}
        self.assertIn('--composition', options)
        self.assertIn('--output-mode', options)

    def test_source_check_uses_locked_theme(self):
        with tempfile.TemporaryDirectory(dir='out/skill-upgrade') as tmp:
            source = Path(tmp)/'source.md'
            source.write_text('---\ntitle: Cloud software platform\ntheme: luxury\n---\n# Overview\nText.', encoding='utf-8')
            self.assertEqual(_expect_from_source(source)['body_size_pt'], float(get_theme('luxury').body_size[:-2]))

    def test_compositions_are_discoverable(self):
        parser=build_parser()
        choices=next(a for a in parser._actions if getattr(a,'choices',None)).choices
        self.assertIn('compositions',choices)

class UnicodeCLITests(unittest.TestCase):
    def test_unicode_image_title_prints_on_legacy_console(self):
        import io, sys
        from unittest.mock import patch
        from pdfstudio.cli import main
        raw=io.BytesIO(); stream=io.TextIOWrapper(raw,encoding='ascii')
        candidate={'title':'庭院花园','width':800,'height':1200,'license':'CC BY-SA'}
        with patch.object(sys,'stdout',stream), patch('pdfstudio.images.contact_sheet',return_value=(Path('candidates.jpg'),[candidate])):
            self.assertEqual(main(['images','garden']),0)
            stream.flush()
        self.assertIn('庭院花园',raw.getvalue().decode('utf-8'))

class ReleaseTests(unittest.TestCase):
    def test_release_identifies_upgraded_engine(self):
        from pdfstudio import __version__
        self.assertEqual(__version__,'2.0.0')

if __name__ == '__main__':
    unittest.main()
