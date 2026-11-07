"""Image sourcing, embedding, and attribution.

Providers (no API key required):
  * Wikimedia Commons — https://commons.wikimedia.org/w/api.php  (fast, reliable)
  * Openverse         — https://api.openverse.org/v1/images/

Images are downloaded once, validated, resized, cached on disk, and embedded as
base64 data URIs so the PDF renders identically in Chromium and WeasyPrint with
no dependency on local file paths or a live network at render time. Every
sourced image carries a credit line.
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import re
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:  # pragma: no cover
    requests = None

try:
    from PIL import Image, ImageDraw
except Exception:  # pragma: no cover
    Image = None
    ImageDraw = None


CACHE_DIR = Path(__file__).resolve().parent.parent / "assets" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

UA = {
    "User-Agent": "PDFStudio/1.0 (design-first PDF generation; contact: local)",
    "Accept": "application/json",
}

MAX_WIDTH = 1600
JPEG_QUALITY = 84
TIMEOUT = 20
RETRIES = 4
_LAST_UPLOAD = 0.0


@dataclass
class ResolvedImage:
    data_uri: str = ""
    caption: str = ""
    credit: str = ""
    license: str = ""
    license_url: str = ""
    source_url: str = ""
    creator: str = ""
    width: int = 0
    height: int = 0
    dominant: str = ""
    ok: bool = False
    error: str = ""
    provider: str = ""
    source_title: str = ""
    has_alpha: bool = False
    media_type: str = "image/jpeg"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _cache_key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:20]


def _to_data_uri(raw: bytes, mime: str = "image/jpeg") -> str:
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


def _process_bytes(raw: bytes) -> tuple[bytes, int, int, str]:
    """Validate and resize, preserving alpha as PNG; opaque photos remain JPEG.

    The four-value return is retained for existing callers. ``dominant`` is a
    legacy average, not a reviewed accent (see asset_layout.suggest_asset_accent).
    """
    if Image is None:
        return raw, 0, 0, ""
    img = Image.open(io.BytesIO(raw))
    img.load()
    has_alpha = "A" in img.getbands() or "transparency" in img.info
    img = img.convert("RGBA" if has_alpha else "RGB")
    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        img = img.resize((MAX_WIDTH, max(1, int(img.height * ratio))), Image.LANCZOS)
    sample = img
    if has_alpha:
        sample = Image.new("RGB", img.size, (255, 255, 255))
        sample.paste(img, mask=img.getchannel("A"))
    dominant = "#%02X%02X%02X" % sample.resize((1, 1), Image.LANCZOS).getpixel((0, 0))
    out = io.BytesIO()
    if has_alpha:
        img.save(out, format="PNG", optimize=True)
    else:
        img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return out.getvalue(), img.width, img.height, dominant


def _from_bytes(
    raw: bytes,
    caption: str = "",
    credit: str = "",
    license_name: str = "",
    license_url: str = "",
    source_url: str = "",
    creator: str = "",
    provider: str = "",
    source_title: str = "",
) -> ResolvedImage:
    try:
        data, w, h, dominant = _process_bytes(raw)
        has_alpha = False
        media_type = "image/jpeg"
        if Image is not None:
            with Image.open(io.BytesIO(data)) as encoded:
                has_alpha = "A" in encoded.getbands() or "transparency" in encoded.info
                media_type = Image.MIME.get(encoded.format, media_type)
        return ResolvedImage(
            data_uri=_to_data_uri(data, media_type),
            caption=caption,
            credit=credit,
            license=license_name,
            license_url=license_url,
            source_url=source_url,
            creator=creator,
            width=w,
            height=h,
            dominant=dominant,
            ok=True,
            provider=provider,
            source_title=source_title,
            has_alpha=has_alpha,
            media_type=media_type,
        )
    except Exception as exc:  # pragma: no cover
        return ResolvedImage(error=f"image decode failed: {exc}", provider=provider)


def _get(url: str, params: Optional[Dict[str, Any]] = None,
         headers: Optional[Dict[str, str]] = None, timeout: int = TIMEOUT):
    """GET with retries, backoff, and Wikimedia upload throttling."""
    if requests is None:
        return None
    global _LAST_UPLOAD
    merged = dict(UA)
    if headers:
        merged.update(headers)
    for attempt in range(RETRIES + 1):
        try:
            if "upload.wikimedia.org" in url:
                wait = 1.5 - (time.time() - _LAST_UPLOAD)
                if wait > 0:
                    time.sleep(wait)
                _LAST_UPLOAD = time.time()
            r = requests.get(url, params=params, headers=merged, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (429, 500, 502, 503, 504) and attempt < RETRIES:
                time.sleep(2.0 + attempt * 2.0)
                continue
            return None
        except Exception:
            if attempt < RETRIES:
                time.sleep(1.5 + attempt)
    return None


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def _cache_read(key: str) -> Optional[ResolvedImage]:
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return ResolvedImage(**data)
    except Exception:
        return None


def _cache_write(key: str, img: ResolvedImage) -> None:
    try:
        (CACHE_DIR / f"{key}.json").write_text(
            json.dumps(asdict(img), ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------

STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "for", "with", "and", "or",
    "to", "from", "by", "as", "is", "are", "be", "into", "over", "under",
    "photo", "image", "picture", "shot", "background", "view", "close",
    "above", "rows", "row", "colourful", "colorful", "colour", "color",
}

# Small, explicit synonym groups make product photography rank ahead of
# unrelated high-resolution stock.  It is deliberately narrow: a general
# thesaurus would reward the wrong subject.
RELATED_TERMS = {
    "shoe": {"footwear", "sandal", "clog", "boot", "sneaker", "trainer"},
    "shoes": {"footwear", "sandal", "clog", "boot", "sneaker", "trainer"},
    "clog": {"shoe", "sandal", "footwear", "croc", "crocs"},
    "clogs": {"shoe", "sandal", "footwear", "croc", "crocs"},
    "sandal": {"shoe", "clog", "footwear", "croc", "crocs"},
    "sandals": {"shoe", "clog", "footwear", "croc", "crocs"},
    "footwear": {"shoe", "sandal", "clog", "croc", "crocs"},
    "croc": {"crocs", "clog", "sandal", "footwear"},
    "crocs": {"croc", "clog", "sandal", "footwear"},
    "store": {"shop", "retail", "display", "shelf"},
    "shop": {"store", "retail", "display", "shelf"},
    "retail": {"store", "shop", "display", "shelf"},
    "display": {"store", "shop", "retail", "shelf"},
    "charm": {"jibbitz", "decoration", "ornament"},
    "charms": {"jibbitz", "decoration", "ornament"},
    "jibbitz": {"charm", "charms", "decoration", "ornament"},
    "pink": {"rose", "magenta", "fuchsia"},
}

BAD_TITLE_HINTS = (
    "logo", "icon", "map", "diagram", "chart", "graph", "seal", "coat of arms",
    "flag", "signature", "symbol", "svg",
)


def _clean(value: Any) -> str:
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return html.unescape(text).strip()


def _candidate_queries(query: str) -> List[str]:
    """Progressively simpler search phrases, most specific first."""
    query = re.sub(r"\s+", " ", query).strip()
    words = [w for w in re.split(r"[\s,]+", query) if w]
    content_words = [w for w in words if w.lower() not in STOPWORDS]
    candidates = [query]
    if content_words:
        candidates.append(" ".join(content_words))
    if len(content_words) >= 3:
        candidates.append(" ".join(content_words[:3]))
        candidates.append(" ".join(content_words[-2:]))
    elif len(content_words) == 2:
        candidates.append(content_words[0])
    seen, ordered = set(), []
    for c in candidates:
        c = c.strip()
        if c and c.casefold() not in seen:
            seen.add(c.casefold())
            ordered.append(c)
    return ordered


def _is_usable(item: Dict[str, Any], *, role: str = "photo") -> bool:
    if role not in ("photo", "object", "diagram", "logo"):
        raise ValueError("image role must be photo, object, diagram or logo")
    if role != "photo":
        # Reviewed illustrations/cutouts are not constrained by photo ratios,
        # minimum photo dimensions or photo-only title exclusions.
        return True
    title = (item.get("title") or "").lower()
    if any(hint in title for hint in BAD_TITLE_HINTS):
        return False
    if title.endswith(".svg"):
        return False
    width = int(item.get("width") or 0)
    height = int(item.get("height") or 0)
    if width and height:
        if width < 640 or height < 480:
            return False
        ratio = width / max(1, height)
        # Portrait photographs are fine: figures crop with object-fit: cover.
        if ratio < 0.55 or ratio > 3.2:
            return False
    return True


def _terms(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[^\W_]+", str(text or "").casefold())
        if word not in STOPWORDS and word not in {"diagram", "logo", "icon", "illustration"}
    }


def _subject_matches(query: str, item: Dict[str, Any]) -> int:
    title_terms = _terms(item.get("title") or "")
    return sum(
        term in title_terms or bool(RELATED_TERMS.get(term, set()) & title_terms)
        for term in _terms(query)
    )


def _relevance_score(query: str, item: Dict[str, Any]) -> float:
    """Rank candidates by literal subject match before resolution.

    A zero-match result is pushed far down.  This is the fix for the common
    failure where a provider returns a beautiful but unrelated photograph and
    the old scorer rewarded it for being large.
    """
    terms = _terms(query)
    matched = _subject_matches(query, item)
    missed = max(0, len(terms) - matched)

    width = float(item.get("width") or 0)
    height = float(item.get("height") or 0)
    ratio = width / max(1.0, height)
    landscape_bonus = 1.0 if 1.2 <= ratio <= 2.4 else 0.0
    size_bonus = min(width, 2400.0) / 2400.0
    provider = item.get("provider") or ""
    provider_bonus = 1.0 if provider == "Wikimedia Commons" else (
        0.4 if provider == "Openverse" else 0.2
    )
    phrase_bonus = 2.0 if re.sub(r"\s+", " ", query.casefold()) in str(
        item.get("title") or ""
    ).casefold() else 0.0
    score = matched * 6.0 - missed * 1.5 + landscape_bonus + size_bonus
    score += provider_bonus + phrase_bonus
    if matched == 0:
        score -= 30.0
    return score


def search_candidates(query: str, count: int = 12, *, role: str = "photo") -> List[Dict[str, Any]]:
    """Merged, de-duplicated, relevance-sorted candidates from all providers."""
    merged: Dict[str, Dict[str, Any]] = {}
    for provider in (search_wikimedia, search_wikipedia, search_openverse):
        for item in provider(query, count=count):
            key = (item.get("title") or "").casefold()
            if not key:
                continue
            current = merged.get(key)
            if current is None or int(item.get("width") or 0) > int(current.get("width") or 0):
                merged[key] = item
    items = [item for item in merged.values() if _is_usable(item, role=role)]
    items.sort(key=lambda item: _relevance_score(query, item), reverse=True)
    return items


def search_wikimedia(query: str, count: int = 8) -> List[Dict[str, Any]]:
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": "6",
        "gsrlimit": max(3, min(count, 20)),
        "prop": "imageinfo",
        "iiprop": "url|size|extmetadata",
        "iiurlwidth": "1400",
    }
    r = _get("https://commons.wikimedia.org/w/api.php", params=params)
    if r is None:
        return []
    try:
        pages = (r.json().get("query") or {}).get("pages") or {}
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
        if not isinstance(meta, dict):
            meta = {}

        def field_value(name: str) -> str:
            entry = meta.get(name) or {}
            if isinstance(entry, dict):
                return _clean(entry.get("value", ""))
            return _clean(entry)

        url = info.get("thumburl") or info.get("url") or ""
        if not url:
            continue
        out.append({
            "url": url,
            "fallback_url": info.get("url") or "",
            "title": _clean(page.get("title", "")).replace("File:", ""),
            "creator": field_value("Artist") or field_value("Credit"),
            "license": field_value("LicenseShortName"),
            "license_url": field_value("LicenseUrl"),
            "source_url": info.get("descriptionurl", ""),
            "width": info.get("width") or 0,
            "height": info.get("height") or 0,
            "provider": "Wikimedia Commons",
        })
    out.sort(key=lambda i: int(i.get("width") or 0), reverse=True)
    return out


def _wikimedia_file(filename: str) -> Optional[Dict[str, Any]]:
    """Resolve one exact Commons filename with full credit metadata."""
    filename = filename.strip()
    if not filename:
        return None
    title = filename if filename.casefold().startswith("file:") else f"File:{filename}"
    params = {
        "action": "query", "format": "json", "titles": title,
        "prop": "imageinfo", "iiprop": "url|size|extmetadata",
        "iiurlwidth": "1600",
    }
    response = _get("https://commons.wikimedia.org/w/api.php", params=params)
    if response is None:
        return None
    try:
        pages = (response.json().get("query") or {}).get("pages") or {}
        page = next(iter(pages.values()))
        info = (page.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata") or {}
    except Exception:
        return None

    def field_value(name: str) -> str:
        entry = meta.get(name) or {}
        return _clean(entry.get("value", "") if isinstance(entry, dict) else entry)

    url = info.get("thumburl") or info.get("url") or ""
    if not url:
        return None
    return {
        "url": url,
        "fallback_url": info.get("url") or "",
        "title": _clean(page.get("title", "")).replace("File:", ""),
        "creator": field_value("Artist") or field_value("Credit"),
        "license": field_value("LicenseShortName"),
        "license_url": field_value("LicenseUrl"),
        "source_url": info.get("descriptionurl", ""),
        "width": info.get("width") or 0,
        "height": info.get("height") or 0,
        "provider": "Wikimedia Commons",
    }


def search_wikipedia(query: str, count: int = 5) -> List[Dict[str, Any]]:
    """Pull the lead image of Wikipedia articles matching the query.

    This is the best generic fallback for topic photography: article lead
    images are curated, high quality, and freely licensed.
    """
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrlimit": max(1, min(count, 5)),
        "prop": "pageimages",
        "piprop": "original|thumbnail",
        "pithumbsize": "1400",
    }
    r = _get("https://en.wikipedia.org/w/api.php", params=params)
    if r is None:
        return []
    try:
        pages = (r.json().get("query") or {}).get("pages") or {}
    except Exception:
        return []
    out = []
    for page in pages.values():
        original = page.get("original") or {}
        thumb = page.get("thumbnail") or {}
        url = thumb.get("source") or original.get("source") or ""
        if not url:
            continue
        out.append({
            "url": url,
            "fallback_url": original.get("source") or "",
            "title": _clean(page.get("title", "")),
            "creator": "Wikipedia contributors",
            "license": "CC BY-SA",
            "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
            "source_url": f"https://en.wikipedia.org/wiki/{urllib.parse.quote(page.get('title', '').replace(' ', '_'))}",
            "width": thumb.get("width") or original.get("width") or 0,
            "height": thumb.get("height") or original.get("height") or 0,
            "provider": "Wikipedia",
        })
    return out


def search_openverse(query: str, count: int = 5) -> List[Dict[str, Any]]:
    params = {
        "q": query,
        "page_size": max(1, min(count, 10)),
        "license_type": "commercial,modification",
        "mature": "false",
    }
    r = _get("https://api.openverse.org/v1/images/", params=params, timeout=8)
    if r is None:
        return []
    try:
        results = r.json().get("results", []) or []
    except Exception:
        return []
    out = []
    for item in results:
        url = item.get("url") or item.get("thumbnail") or ""
        if not url:
            continue
        out.append({
            "url": url,
            "fallback_url": item.get("thumbnail") or "",
            "title": _clean(item.get("title", "")),
            "creator": _clean(item.get("creator", "")),
            "license": _clean(item.get("license", "")),
            "license_url": item.get("license_url", "") or "",
            "source_url": item.get("foreign_landing_url", "") or "",
            "width": item.get("width") or 0,
            "height": item.get("height") or 0,
            "provider": "Openverse",
        })
    return out


def _download(url: str) -> Optional[bytes]:
    if not url:
        return None
    r = _get(url, headers={"Accept": "image/*"}, timeout=25)
    if r is None:
        return None
    content = r.content
    if len(content) < 1024:
        return None
    ctype = r.headers.get("Content-Type", "").lower()
    if "image" not in ctype and not url.lower().endswith(
        (".jpg", ".jpeg", ".png", ".webp", ".gif")
    ):
        return None
    return content


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _credit_for(item: Dict[str, Any]) -> str:
    bits = []
    creator = (item.get("creator") or "").strip()
    if creator:
        bits.append(creator)
    license_name = (item.get("license") or "").strip()
    if license_name:
        bits.append(license_name)
    provider = item.get("provider") or ""
    if provider:
        bits.append(provider)
    return " · ".join(bits)


def resolve_search(query: str, caption: str = "", count: int = 8,
                   avoid: Optional[set[str]] = None, *, role: str = "photo") -> ResolvedImage:
    """Find a freely-licensed image for a query, cache it, and embed it.

    ``avoid`` is a set of source titles and URLs already used in the document.
    It prevents the same photograph appearing twice under two different
    queries, which is the most common image failure in generated PDFs.
    """
    if role not in ("photo", "object", "diagram", "logo"):
        raise ValueError("image role must be photo, object, diagram or logo")
    query = (query or "").strip()
    if not query:
        return ResolvedImage(error="empty image query")
    avoid = {str(value).strip().casefold() for value in (avoid or set()) if value}

    if query.casefold().startswith("commons:"):
        filename = query.split(":", 1)[1].strip()
        if filename.casefold() in avoid:
            return ResolvedImage(error=f"Commons file already used: {filename}")
        key = _cache_key(f"commons-v2::{filename.casefold()}")
        cached = _cache_read(key)
        if cached is not None:
            if caption:
                cached.caption = caption
            return cached
        item = _wikimedia_file(filename)
        if item:
            raw = _download(item.get("url") or "") or _download(item.get("fallback_url") or "")
            if raw:
                img = _from_bytes(
                    raw, caption=caption, credit=_credit_for(item),
                    license_name=item.get("license") or "",
                    license_url=item.get("license_url") or "",
                    source_url=item.get("source_url") or "",
                    creator=item.get("creator") or "",
                    provider=item.get("provider") or "",
                    source_title=item.get("title") or "",
                )
                if img.ok:
                    _cache_write(key, img)
                    return img
        return ResolvedImage(error=f"Commons file not found: {filename}")

    avoid_key = "|".join(sorted(avoid))
    key = _cache_key(f"search-v4::{role}::{query.casefold()}::{avoid_key}")
    cached = _cache_read(key)
    if cached is not None and cached.ok:
        identity = {str(cached.source_title or "").casefold(),
                    str(cached.source_url or "").casefold()}
        if not (identity & avoid):
            if caption:
                cached.caption = caption
            return cached

    last_error = "no provider returned an image"
    tried: List[str] = []
    for candidate in _candidate_queries(query):
        tried.append(candidate)
        for item in search_candidates(candidate, count=count, role=role):
            # Ranking alone must never admit a beautiful but unrelated asset.
            # Match the original required subject, not only a simplified query.
            if not _is_usable(item, role=role) or _subject_matches(query, item) == 0:
                last_error = "no required subject matched"
                continue
            title = str(item.get("title") or "").casefold()
            source = str(item.get("source_url") or "").casefold()
            if title in avoid or source in avoid:
                continue
            raw = _download(item.get("url") or "")
            if not raw:
                raw = _download(item.get("fallback_url") or "")
            if not raw:
                last_error = "download failed"
                continue
            img = _from_bytes(
                raw,
                caption=caption,
                credit=_credit_for(item),
                license_name=item.get("license") or "",
                license_url=item.get("license_url") or "",
                source_url=item.get("source_url") or "",
                creator=item.get("creator") or "",
                provider=item.get("provider") or "",
                source_title=item.get("title") or "",
            )
            if img.ok:
                identity = {str(img.source_title or "").casefold(),
                            str(img.source_url or "").casefold()}
                if identity & avoid:
                    continue
                _cache_write(key, img)
                return img
            last_error = img.error
    return ResolvedImage(
        error=f"no image found for '{query}' ({last_error}; tried {len(tried)} queries)"
    )


def resolve_file(path: str, caption: str = "") -> ResolvedImage:
    p = Path(path)
    if not p.exists():
        return ResolvedImage(error=f"file not found: {path}")
    return _from_bytes(
        p.read_bytes(), caption=caption, credit="Local asset",
        license_name="Local", provider="local",
    )


def resolve_url(url: str, caption: str = "") -> ResolvedImage:
    key = _cache_key(f"url-v2::{url}")
    cached = _cache_read(key)
    if cached is not None:
        return cached
    raw = _download(url)
    if not raw:
        return ResolvedImage(error=f"could not download: {url}")
    img = _from_bytes(
        raw, caption=caption, credit="Web asset",
        license_name="Unknown", provider="url",
    )
    if img.ok:
        _cache_write(key, img)
    return img


# ---------------------------------------------------------------------------
# Visual review
# ---------------------------------------------------------------------------

def contact_sheet(query: str, out_path: str | Path, count: int = 12,
                  columns: int = 4) -> tuple[Path, List[Dict[str, Any]]]:
    """Download candidate thumbnails into one labelled sheet for review.

    The agent should *look* at this image before choosing a photograph.  A
    title match is not a visual match.  The sheet prints the candidate index,
    title, dimensions, and licence so the chosen item can be pinned with
    ``commons:<exact filename>``.
    """
    if Image is None or ImageDraw is None:
        raise RuntimeError("Pillow is required for the candidate contact sheet")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    items = search_candidates(query, count=count)

    tiles = []
    for index, item in enumerate(items):
        raw = _download(item.get("url") or "") or _download(item.get("fallback_url") or "")
        if not raw:
            continue
        try:
            im = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:
            continue
        im.thumbnail((300, 210), Image.LANCZOS)
        tile = Image.new("RGB", (320, 286), "white")
        tile.paste(im, ((320 - im.width) // 2, 8))
        draw = ImageDraw.Draw(tile)
        title = str(item.get("title") or "")[:46]
        title = title.encode("ascii", "replace").decode("ascii")
        draw.text((8, 226), f"{index}: {title}", fill="#111111")
        draw.text((8, 242), f"{item.get('width')}x{item.get('height')} | {item.get('license') or ''}",
                  fill="#666666")
        draw.text((8, 258), str(item.get("provider") or "")[:46], fill="#999999")
        tiles.append(tile)

    if not tiles:
        raise RuntimeError(f"No downloadable candidates for '{query}'")

    rows = (len(tiles) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * 320, rows * 286), (225, 225, 225))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, ((index % columns) * 320, (index // columns) * 286))
    sheet.save(out_path, quality=90)
    return out_path, items


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def _esc(value: str) -> str:
    """Escape text for safe interpolation into HTML."""
    return html.escape(str(value or ""), quote=True)


def figure_html(img: ResolvedImage, alt: str = "", number: int = 0) -> str:
    alt_text = _esc(alt or img.caption or "Image")
    if not img.ok:
        # Keep the diagnostic on ResolvedImage for renderer warnings, not on a
        # decorative publishable placeholder. Families use a text-led fallback.
        return ""
    cap = _esc(img.caption or alt)
    credit = _esc(img.credit or "")
    if img.source_url and credit:
        credit = f'<a href="{_esc(img.source_url)}">{credit}</a>'
    num = f'<span class="figure__num">Fig. {number}</span> ' if number else ""
    credit_html = f'<span class="figure__credit">{credit}</span>' if credit else ""
    caption_html = (
        f'<figcaption>{num}<span class="figure__caption">{cap}</span>{credit_html}</figcaption>'
        if cap or credit else ""
    )
    return (
        f'<figure class="figure">'
        f'<img src="{img.data_uri}" alt="{alt_text}" '
        f'width="{img.width}" height="{img.height}" />'
        f"{caption_html}</figure>"
    )


def credits_html(images: List[ResolvedImage]) -> str:
    rows = [i for i in images if i.ok and (i.credit or i.source_url)]
    if not rows:
        return ""
    items = []
    seen = set()
    for i in rows:
        identity = str(i.source_title or i.source_url or i.caption or "").casefold()
        if identity and identity in seen:
            continue
        seen.add(identity)
        label = _esc(i.caption or "Image")
        credit = _esc(i.credit or "Unknown")
        link = (
            f'<a href="{_esc(i.source_url)}">{credit}</a>'
            if i.source_url else credit
        )
        lic = f" ({_esc(i.license)})" if i.license else ""
        items.append(f"<li>{label} - {link}{lic}</li>")
    return (
        '<section class="credits"><h2>Image credits</h2><ul>'
        + "".join(items)
        + "</ul></section>"
    )
