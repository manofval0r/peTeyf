"""Resolve reviewed assets before layout; render charts at their final column width."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import re
from .asset_layout import AssetSpec, AssetLayout, read_asset_specs, validate_asset_specs, analyse_asset, apply_crop
from .images import ResolvedImage, resolve_search, resolve_file, resolve_url, figure_html, credits_html
from .charts import make_chart

@dataclass
class ResolvedAssets:
    images: dict[str,ResolvedImage] = field(default_factory=dict)
    layouts: dict[str,AssetLayout] = field(default_factory=dict)
    replacements: dict[str,str] = field(default_factory=dict)
    credits: str = ''


def _path(value,doc):
    value=str(value)
    if value.startswith('img:'): value=value[4:]
    p=Path(value)
    return p if p.is_absolute() else (doc.source_path.parent if doc.source_path else Path.cwd())/p


def _resolve(value,caption,doc,opts,role,avoid):
    if value.startswith('search:'):
        return resolve_search(value[7:],caption,avoid=avoid,role=role) if opts.images!='off' else ResolvedImage(error='image search disabled')
    if value.startswith(('https://','http://')): return resolve_url(value,caption)
    return resolve_file(str(_path(value,doc)),caption)


def collect_assets(doc,meta,opts) -> ResolvedAssets:
    specs=read_asset_specs(meta); validate_asset_specs(doc,specs)
    result=ResolvedAssets(); used=set()
    requests=[]
    for reserved,key in (('cover','cover_image'),('back_cover','back_cover_image')):
        value=meta.get(key) or (meta.get('cover_photo') if reserved=='cover' else '')
        if value: requests.append((reserved,str(value),str(meta.get('cover_caption') or meta.get('title','')) if reserved=='cover' else str(meta.get('back_cover_caption') or 'Closing photograph')))
    for req in doc.image_requests:
        value='search:'+req.query if req.kind=='search' else req.url if req.kind=='url' else req.path
        requests.append((req.slot,value,req.caption or req.alt))
    for slot,value,caption in requests:
        spec=specs.get(slot,AssetSpec())
        image=_resolve(value,caption,doc,opts,spec.role,used)
        if image.ok:
            layout=analyse_asset(slot,image,spec)
            if spec.crop is not None: image=apply_crop(image,spec)
            result.layouts[slot]=layout
            used.update(v for v in (image.source_url,image.source_title,image.caption) if v)
            if not layout.approved: doc.warnings.append(f'Asset {slot} is not marked visually reviewed; fit is bounded and no derived accent is used.')
        else:
            doc.warnings.append(f'Asset {slot} omitted: {image.error}')
        result.images[slot]=image
    return result


def _placed_figure(image,layout,alt,number):
    markup=figure_html(image,alt,number)
    if not markup or layout is None: return markup
    fit='contain' if layout.role in ('object','logo','diagram') else layout.fit
    focal=layout.focal
    if layout.crop:
        x0,y0,x1,y1=layout.crop
        focal=((focal[0]-x0)/(x1-x0),(focal[1]-y0)/(y1-y0))
    aspect='portrait' if layout.aspect<.85 else 'panorama' if layout.aspect>2 else 'landscape'
    markup=markup.replace('class="figure"',f'class="figure figure--{layout.role}" data-aspect="{aspect}"',1)
    # Validated numeric coordinates, not authored CSS.
    return markup.replace('<img ',f'<img style="object-fit:{fit};object-position:{focal[0]*100:g}% {focal[1]*100:g}%" ',1)


def render_assets(doc,assets,decision,geometry,sections):
    positions=[]
    for req in doc.image_requests: positions.append((doc.body_html.find(req.slot),'image',req))
    for req in doc.chart_requests: positions.append((doc.body_html.find(req.slot),'chart',req))
    positions.sort(key=lambda x:x[0])
    number=0
    for _,kind,req in positions:
        if kind=='image':
            image=assets.images.get(req.slot,ResolvedImage(error='missing asset'))
            if not image.ok:
                assets.replacements[req.slot]=''; continue
            number+=1
            assets.replacements[req.slot]=_placed_figure(image,assets.layouts.get(req.slot),req.alt,number)
        else:
            number+=1
            width=geometry.inner_width_mm-(13 if decision.family_id=='technical-reference' else 0)
            width/=25.4
            height=max(2.5,min(3.6,width*.55))
            if req.kind in ('bar','line','area') and len(req.labels)<=6:
                height=min(height,2.9)
            markup=make_chart(req,decision.tokens,number=number,width=width,height=height)
            assets.replacements[req.slot]=markup
    assets.credits=credits_html([img for img in assets.images.values() if img.ok])
    return assets


def replace_slots(html,replacements):
    for slot,markup in replacements.items(): html=html.replace(slot,markup)
    return html
