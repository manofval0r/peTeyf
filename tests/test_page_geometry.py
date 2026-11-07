import unittest
try:
    from pdfstudio import geometry
except ImportError:
    geometry = None
from pdfstudio.render import PAGE_SIZES_MM, RenderOptions
from pathlib import Path

class GeometryTests(unittest.TestCase):
    def resolve(self,*args,**kwargs):
        self.assertIsNotNone(geometry, 'Page geometry missing')
        return geometry.resolve_geometry(*args,**kwargs)
    def test_all_formats_and_orientations(self):
        for page,(w,h) in PAGE_SIZES_MM.items():
            for landscape in (False,True):
                g=self.resolve(page,landscape,'print')
                self.assertEqual((g.width_mm,g.height_mm),(h,w) if landscape else (w,h))
                self.assertEqual(g.inner_width_mm,g.width_mm-36)
    def test_mode_safe_insets(self):
        self.assertEqual(self.resolve('A4',False,'print').safe_mm,(20,18,22,18))
        self.assertEqual(self.resolve('A4',False,'digital').safe_mm,(16,16,16,16))
    def test_invalid_safe_area_rejected(self):
        for margin in ((-1,1,1,1),(200,20,200,20),(float('nan'),1,1,1)):
            self.assertIsNotNone(geometry,'Page geometry missing')
            with self.assertRaises(ValueError):
                geometry.resolve_geometry('A4',False,'print',margin)
    def test_invalid_format_rejected(self):
        self.assertIsNotNone(geometry,'Page geometry missing')
        with self.assertRaises(ValueError):
            geometry.resolve_geometry('Imaginary',False,'print')

if __name__=='__main__': unittest.main()
