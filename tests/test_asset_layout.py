"""Deterministic reviewed-asset contract tests; no network or cache writes."""
import base64
import io
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from pdfstudio import images
from pdfstudio.content import Document, ImageRequest

ARTIFACTS = Path(__file__).resolve().parents[1] / "out/skill-upgrade/asset-tests"


def image_bytes(size=(240, 240), mode="RGB", colour="red", fmt="PNG"):
    image = Image.new(mode, size, colour)
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


def decode(image):
    return Image.open(io.BytesIO(base64.b64decode(image.data_uri.split(",", 1)[1])))


class AssetLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        cls.object_raw = image_bytes(mode="RGBA", colour=(210, 40, 70, 0))
        obj = Image.open(io.BytesIO(cls.object_raw))
        ImageDraw.Draw(obj).ellipse((60, 40, 180, 210), fill=(210, 40, 70, 255))
        buffer = io.BytesIO()
        obj.save(buffer, format="PNG")
        cls.object_raw = buffer.getvalue()
        (ARTIFACTS / "object.png").write_bytes(cls.object_raw)
        for name, size in (("portrait", (300, 900)), ("panorama", (1200, 200)), ("diagram", (1000, 80))):
            (ARTIFACTS / f"{name}.png").write_bytes(image_bytes(size))

    def api(self):
        from pdfstudio import asset_layout
        return asset_layout

    def test_object_alpha_survives_decode_encode(self):
        resolved = images._from_bytes(self.object_raw)
        self.assertTrue(resolved.ok)
        self.assertTrue(resolved.has_alpha)
        self.assertEqual(resolved.media_type, "image/png")
        self.assertEqual(decode(resolved).getpixel((0, 0))[3], 0)
        for role in ("object", "logo"):
            self.assertTrue(self.api().analyse_asset("slot", resolved, self.api().AssetSpec(role=role)).has_alpha)
        field = Image.new("RGBA", (240, 240), "#243B53")
        field.alpha_composite(decode(resolved).convert("RGBA"))
        field.convert("RGB").save(ARTIFACTS / "object-nonwhite-preview.png")

    def test_transparent_webp_and_palette_png_preserved(self):
        webp = images._from_bytes(image_bytes(mode="RGBA", colour=(50, 100, 200, 0), fmt="WEBP"))
        self.assertTrue(webp.has_alpha)
        self.assertIn(webp.media_type, ("image/png", "image/webp"))
        palette = Image.new("P", (20, 20), 0)
        palette.info["transparency"] = 0
        buffer = io.BytesIO()
        palette.save(buffer, format="PNG")
        self.assertEqual(decode(images._from_bytes(buffer.getvalue())).getpixel((0, 0))[3], 0)

    def test_photo_retains_jpeg_processing(self):
        resolved = images._from_bytes(image_bytes((2000, 1000)))
        self.assertEqual((resolved.width, resolved.height), (1600, 800))
        self.assertEqual(resolved.media_type, "image/jpeg")
        self.assertFalse(resolved.has_alpha)

    def test_portrait_and_panorama_report_intrinsics(self):
        api = self.api()
        for name, expected in (("portrait", (300, 900, 1 / 3)), ("panorama", (1200, 200, 6))):
            resolved = images.resolve_file(str(ARTIFACTS / f"{name}.png"))
            layout = api.analyse_asset(name, resolved, api.AssetSpec())
            self.assertEqual((layout.width_px, layout.height_px), expected[:2])
            self.assertAlmostEqual(layout.aspect, expected[2])

    def test_focal_point_validated(self):
        api = self.api()
        for focal in ((-0.1, 0.5), (0.5, 1.1), (float("nan"), 0.5), (0.5,), (True, 0.5)):
            with self.subTest(focal=focal), self.assertRaises(ValueError):
                api.analyse_asset("slot", images._from_bytes(self.object_raw), api.AssetSpec(focal=focal))

    def test_crop_rectangle_validated_and_focal_inside(self):
        api = self.api()
        bad = ((0, 0, 0, 1), (0, 0, 1.1, 1), (0.8, 0, 0.2, 1), (0, float("nan"), 1, 1), (0, 0, 1))
        for crop in bad:
            with self.subTest(crop=crop), self.assertRaises(ValueError):
                api.analyse_asset("slot", images._from_bytes(self.object_raw), api.AssetSpec(crop=crop))
        with self.assertRaises(ValueError):
            api.analyse_asset("slot", images._from_bytes(self.object_raw), api.AssetSpec(crop=(0.6, 0, 1, 1)))
        image = images._from_bytes(image_bytes((1200, 200)))
        spec = api.AssetSpec(crop=(0.25, 0, 0.75, 1), approved=True)
        original_uri = image.data_uri
        layout = api.analyse_asset("slot", image, spec)
        self.assertEqual(layout.crop, spec.crop)
        self.assertEqual((layout.width_px, layout.height_px), (1200, 200))
        self.assertEqual(layout.aspect, 3)
        self.assertEqual(image.data_uri, original_uri, "analysis must not alter encoded source")
        cropped = api.apply_crop(image, spec)
        self.assertEqual((cropped.width, cropped.height), (600, 200))
        self.assertEqual(image.width, 1200)
        with self.assertRaises(ValueError):
            api.apply_crop(image, replace(spec, approved=False))

    def test_accent_suggestion_requires_review_and_opt_in(self):
        api = self.api()
        image = images._from_bytes(self.object_raw)
        for approved, derive in ((False, False), (True, False), (False, True)):
            self.assertIsNone(api.suggest_asset_accent(image, api.AssetSpec(approved=approved, derive_accent=derive)))
        spec = api.AssetSpec(approved=True, derive_accent=True, role="object")
        self.assertEqual(api.suggest_asset_accent(image, spec), "#D22846")
        self.assertIsNone(api.suggest_asset_accent(images._from_bytes(image_bytes(colour="white")), spec))
        self.assertIsNone(api.suggest_asset_accent(images._from_bytes(image_bytes(mode="RGBA", colour=(10, 20, 30, 0))), spec))
        white = Image.new("RGB", (100, 100), "white")
        ImageDraw.Draw(white).rectangle((35, 35, 65, 65), fill="#D22846")
        buffer = io.BytesIO()
        white.save(buffer, format="PNG")
        suggested = api.suggest_asset_accent(images._from_bytes(buffer.getvalue()), spec)
        self.assertIsNotNone(suggested)
        self.assertNotEqual(suggested, "#FFFFFF")

    def test_zero_subject_match_not_auto_selected(self):
        candidate = {"title": "Mountain landscape", "url": "mock://mountain", "width": 1600, "height": 900}
        with patch.object(images, "_cache_read", return_value=None), patch.object(images, "search_candidates", return_value=[candidate]), patch.object(images, "_download") as download:
            resolved = images.resolve_search("quartz laboratory")
        self.assertFalse(resolved.ok)
        download.assert_not_called()

    def test_short_and_unicode_subject_matches(self):
        api_candidates = [{"title": "AI diagram", "url": "mock://ai", "width": 1000, "height": 80}]
        with patch.object(images, "_cache_read", return_value=None), patch.object(images, "_cache_write"), patch.object(images, "search_candidates", return_value=api_candidates), patch.object(images, "_download", return_value=image_bytes((1000, 80))):
            self.assertTrue(images.resolve_search("AI", role="diagram").ok)
        self.assertIn("家具", images._terms("家具"))

    def test_diagram_role_not_photo_filtered(self):
        candidate = {"title": "Network diagram", "url": "mock://diagram", "width": 1000, "height": 80}
        self.assertFalse(images._is_usable(candidate))
        self.assertTrue(images._is_usable(candidate, role="diagram"))
        with patch.object(images, "search_wikimedia", return_value=[candidate]), patch.object(images, "search_wikipedia", return_value=[]), patch.object(images, "search_openverse", return_value=[]):
            self.assertEqual(images.search_candidates("network", role="diagram"), [candidate])
            self.assertEqual(images.search_candidates("network"), [])

    def test_missing_hero_warns_without_publish_placeholder(self):
        failed = images.ResolvedImage(error="optional hero not found")
        self.assertEqual(images.figure_html(failed), "")
        self.assertIn("optional hero", failed.error)
        self.assertFalse(failed.ok)  # orchestrator consumes this diagnostic as its warning

    def test_nested_asset_metadata_not_silently_lost(self):
        api = self.api()
        slot = "<!--IMG_1-->"
        meta = {"design": {"assets": {slot: {"role": "object", "fit": "contain", "focal": [0.4, 0.6], "approved": True}, "cover": {"role": "photo"}, "back_cover": {"role": "logo"}}}}
        specs = api.read_asset_specs(meta)
        self.assertEqual(specs[slot].focal, (0.4, 0.6))
        self.assertTrue(specs[slot].approved)
        api.validate_asset_specs(Document({}, "", [], [ImageRequest(slot)]), specs)
        for malformed in ({"design": "role: object"}, {"design": {"assets": "object"}}, {"design": {"assets": {slot: {"rol": "object"}}}}, {"design": {"assets": {slot: {"approved": "false"}}}}):
            with self.subTest(meta=malformed), self.assertRaises(ValueError):
                api.read_asset_specs(malformed)
        for spec in (api.AssetSpec(role="unknown"), api.AssetSpec(fit="stretch")):
            with self.assertRaises(ValueError):
                api.validate_asset_specs(Document({}, "", [], [ImageRequest(slot)]), {slot: spec})
        with self.assertRaisesRegex(ValueError, "unknown.*slot"):
            api.validate_asset_specs(Document({}, "", [], [ImageRequest(slot)]), {"IMG_1": api.AssetSpec()})

    def test_credits_survive_role_reassignment(self):
        api = self.api()
        image = images._from_bytes(self.object_raw, caption="Reviewed object", credit="Artist · CC BY", license_name="CC BY", license_url="https://example.test/license", source_url="https://example.test/source", creator="Artist", provider="local", source_title="Exact source")
        api.analyse_asset("cover", image, api.AssetSpec(role="logo"))
        cropped = api.apply_crop(image, api.AssetSpec(role="object", crop=(0.2, 0.1, 0.8, 0.9), approved=True))
        for attr in ("caption", "credit", "license", "license_url", "source_url", "creator", "provider", "source_title"):
            self.assertEqual(getattr(cropped, attr), getattr(image, attr))
        self.assertIn("Artist", images.figure_html(cropped))
        self.assertIn("https://example.test/source", images.credits_html([cropped]))
        self.assertTrue(cropped.has_alpha)


if __name__ == "__main__":
    unittest.main()
