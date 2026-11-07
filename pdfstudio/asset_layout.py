"""Reviewed asset metadata and explicit crops, independent of page composition.

Dimensions/colour statistics are not semantic vision. Analysis never rewrites
source bytes, and an accent is a suggestion only; the design resolver owns locks.
"""
from __future__ import annotations

import base64
import io
import math
from dataclasses import dataclass, fields, replace
from typing import TYPE_CHECKING

from PIL import Image

from .images import ResolvedImage, _from_bytes

if TYPE_CHECKING:
    from .content import Document


@dataclass
class AssetSpec:
    role: str = "photo"
    fit: str = "contain"
    focal: tuple[float, float] = (0.5, 0.5)
    crop: tuple[float, float, float, float] | None = None
    approved: bool = False
    derive_accent: bool = False


@dataclass
class AssetLayout:
    slot: str
    role: str
    width_px: int
    height_px: int
    aspect: float
    has_alpha: bool
    fit: str
    focal: tuple[float, float]
    crop: tuple[float, float, float, float] | None
    approved: bool
    accent: str | None = None


def _coordinates(value, count: int, name: str) -> tuple:
    if not isinstance(value, (tuple, list)) or len(value) != count:
        raise ValueError(f"asset {name} must have {count} normalised coordinates")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in value):
        raise ValueError(f"asset {name} coordinates must be finite numbers in [0, 1]")
    return tuple(value)


def _validate_spec(spec: AssetSpec) -> None:
    if not isinstance(spec, AssetSpec):
        raise ValueError("asset metadata must be an AssetSpec")
    if spec.role not in ("photo", "object", "diagram", "logo"):
        raise ValueError("asset role must be photo, object, diagram or logo")
    if spec.fit not in ("contain", "cover"):
        raise ValueError("asset fit must be contain or cover")
    if not isinstance(spec.approved, bool) or not isinstance(spec.derive_accent, bool):
        raise ValueError("asset approved and derive_accent must be booleans")
    x, y = _coordinates(spec.focal, 2, "focal")
    if spec.crop is not None:
        x0, y0, x1, y1 = _coordinates(spec.crop, 4, "crop")
        if not x0 < x1 or not y0 < y1:
            raise ValueError("asset crop requires x0 < x1 and y0 < y1")
        if not x0 <= x <= x1 or not y0 <= y <= y1:
            raise ValueError("asset focal point must lie inside its approved crop")


def read_asset_specs(meta: dict) -> dict[str, AssetSpec]:
    """Read design.assets keyed by literal ImageRequest.slot or reserved slots.

    Nested mappings must already be parsed by the source loader (PyYAML for
    YAML). Reject flattened strings/unknown fields rather than dropping them.
    """
    if not isinstance(meta, dict):
        raise ValueError("document metadata must be a mapping")
    if "design" not in meta:
        return {}
    design = meta["design"]
    if not isinstance(design, dict):
        raise ValueError("design must be a parsed mapping; nested YAML requires PyYAML")
    raw_specs = design.get("assets", {})
    if not isinstance(raw_specs, dict):
        raise ValueError("design.assets must be a parsed mapping; nested YAML requires PyYAML")
    allowed = {f.name for f in fields(AssetSpec)}
    specs = {}
    for slot, value in raw_specs.items():
        if not isinstance(slot, str) or not slot:
            raise ValueError("asset slot must be a nonempty string")
        if not isinstance(value, dict):
            raise ValueError(f"asset slot {slot!r} must contain a mapping")
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"unknown asset fields for slot {slot!r}: {', '.join(sorted(map(str, unknown)))}")
        spec = AssetSpec(**value)
        _validate_spec(spec)
        spec = replace(spec, focal=tuple(spec.focal), crop=tuple(spec.crop) if spec.crop is not None else None)
        specs[slot] = spec
    return specs


def validate_asset_specs(doc: Document, specs: dict[str, AssetSpec]) -> None:
    """Validate before downloading; request slots are placeholders, not IDs."""
    if not isinstance(specs, dict):
        raise ValueError("asset specs must be a mapping")
    known = {request.slot for request in doc.image_requests} | {"cover", "back_cover"}
    for slot, spec in specs.items():
        if slot not in known:
            raise ValueError(f"unknown asset slot {slot!r}; use an existing ImageRequest.slot, cover or back_cover")
        _validate_spec(spec)


def _decode(image: ResolvedImage) -> Image.Image:
    if not image.ok or not image.data_uri:
        raise ValueError(f"cannot analyse unresolved asset: {image.error or 'missing image'}")
    try:
        header, encoded = image.data_uri.split(",", 1)
        if not header.startswith("data:image/") or not header.endswith(";base64"):
            raise ValueError("expected a base64 image data URI")
        result = Image.open(io.BytesIO(base64.b64decode(encoded, validate=True)))
        result.load()
        return result
    except Exception as exc:
        raise ValueError(f"invalid resolved asset encoding: {exc}") from exc


def _crop_box(image: Image.Image, spec: AssetSpec) -> tuple[int, int, int, int]:
    if spec.crop is None:
        return (0, 0, image.width, image.height)
    x0, y0, x1, y1 = spec.crop
    # Round inward so no pixel outside the reviewed normalised rectangle leaks.
    box = (math.ceil(x0 * image.width), math.ceil(y0 * image.height), math.floor(x1 * image.width), math.floor(y1 * image.height))
    if box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError("approved crop contains no complete source pixel")
    return box


def suggest_asset_accent(image: ResolvedImage, spec: AssetSpec) -> str | None:
    """Quantise reviewed, opt-in source colour; discard alpha and edge backgrounds.

    No theme mutation or network access. Opaque border-dominated bins and near
    white/black neutral bins are not useful accent evidence; an empty remainder
    yields no suggestion. Crop statistics stay inside the approved rectangle.
    """
    _validate_spec(spec)
    if not spec.approved or not spec.derive_accent or not image.ok:
        return None
    source = _decode(image)
    source = source.crop(_crop_box(source, spec)).convert("RGBA")
    source.thumbnail((128, 128), Image.Resampling.LANCZOS)
    pixels = [source.getpixel((x, y)) for y in range(source.height) for x in range(source.width)]
    visible = [pixel[:3] for pixel in pixels if pixel[3] >= 128]
    if not visible:
        return None
    colours = Image.new("RGB", (len(visible), 1))
    colours.putdata(visible)
    quantised = colours.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
    palette = quantised.getpalette()
    bins = sorted(quantised.getcolors() or [], key=lambda pair: (-pair[0], pair[1]))
    border = [source.getpixel((x, y)) for y in range(source.height) for x in range(source.width) if x in (0, source.width - 1) or y in (0, source.height - 1)]
    border_rgb = [pixel[:3] for pixel in border if pixel[3] >= 128]
    for count, index in bins:
        rgb = tuple(palette[index * 3:index * 3 + 3])
        if min(rgb) >= 240 or max(rgb) <= 20:
            continue
        edge_share = sum(max(abs(a - b) for a, b in zip(pixel, rgb)) <= 24 for pixel in border_rgb) / max(1, len(border_rgb))
        if count / len(visible) >= 0.5 and edge_share >= 0.6:
            continue
        return "#%02X%02X%02X" % rgb
    return None


def analyse_asset(slot: str, image: ResolvedImage, spec: AssetSpec) -> AssetLayout:
    """Return validated metadata only; width/height describe the encoded source.

    aspect describes the effective normalised crop, while focal/crop remain in
    original source coordinates. Use apply_crop explicitly to obtain crop bytes.
    """
    _validate_spec(spec)
    source = _decode(image)
    width, height = source.size
    aspect = width / height
    if spec.crop is not None:
        x0, y0, x1, y1 = spec.crop
        _crop_box(source, spec)
        aspect *= (x1 - x0) / (y1 - y0)
    return AssetLayout(
        slot=slot, role=spec.role, width_px=width, height_px=height,
        aspect=aspect, has_alpha="A" in source.getbands() or "transparency" in source.info,
        fit=spec.fit, focal=tuple(spec.focal), crop=tuple(spec.crop) if spec.crop is not None else None,
        approved=spec.approved, accent=suggest_asset_accent(image, spec),
    )


def apply_crop(image: ResolvedImage, spec: AssetSpec) -> ResolvedImage:
    """Return a new alpha-safe image for an approved crop, retaining all credits.

    No crop is a no-op. A nonempty crop requires spec.approved; apply once to the
    original resolved source, not repeatedly to already cropped bytes.
    """
    _validate_spec(spec)
    if spec.crop is None:
        return image
    if not spec.approved:
        raise ValueError("asset crop must be approved before rewriting source bytes")
    source = _decode(image)
    cropped = source.crop(_crop_box(source, spec))
    output = io.BytesIO()
    cropped.save(output, format="PNG")
    encoded = _from_bytes(output.getvalue())
    if not encoded.ok:
        raise ValueError(encoded.error)
    return replace(image, data_uri=encoded.data_uri, width=encoded.width, height=encoded.height,
                   has_alpha=encoded.has_alpha, media_type=encoded.media_type, dominant=encoded.dominant)
