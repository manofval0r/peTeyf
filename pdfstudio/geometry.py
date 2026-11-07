"""Physical PDF geometry: page paint never determines text-safe insets."""
from __future__ import annotations
from dataclasses import dataclass
import math
import re

PAGE_SIZES_MM={'A3':(297.,420.),'A4':(210.,297.),'A5':(148.,210.),'Letter':(215.9,279.4),'Legal':(215.9,355.6),'Tabloid':(279.4,431.8)}

@dataclass(frozen=True)
class PageGeometry:
    width_mm: float
    height_mm: float
    safe_mm: tuple[float,float,float,float]
    @property
    def inner_width_mm(self): return self.width_mm-self.safe_mm[1]-self.safe_mm[3]
    @property
    def inner_height_mm(self): return self.height_mm-self.safe_mm[0]-self.safe_mm[2]
    @property
    def margin_css(self): return ' '.join(f'{v:g}mm' for v in self.safe_mm)


def resolve_geometry(page_size: str, landscape: bool, output_mode: str, safe_mm=None) -> PageGeometry:
    if page_size not in PAGE_SIZES_MM:
        raise ValueError(f'Unknown page size {page_size!r}. Supported: {", ".join(PAGE_SIZES_MM)}')
    if output_mode not in ('print','digital'): raise ValueError('output_mode must be print or digital.')
    width,height=PAGE_SIZES_MM[page_size]
    if landscape: width,height=height,width
    safe=tuple(float(v) for v in (safe_mm if safe_mm is not None else ((16,14,18,14) if output_mode=='print' else (14,14,14,14))))
    if len(safe)!=4 or not all(math.isfinite(v) and v>=0 for v in safe): raise ValueError('safe_mm must contain four finite nonnegative insets.')
    result=PageGeometry(width,height,safe)
    if result.inner_width_mm<30 or result.inner_height_mm<30: raise ValueError('Safe insets leave too little usable page area.')
    return result


def page_field_css(name: str, colour: str, geometry: PageGeometry) -> str:
    if not re.fullmatch(r'[a-z][a-z0-9-]*',name) or not re.fullmatch(r'#[0-9a-fA-F]{6}',colour):
        raise ValueError('Page field must have a safe identifier and #RRGGBB colour.')
    return f'@page {name} {{ size: {geometry.width_mm}mm {geometry.height_mm}mm; margin: {geometry.margin_css}; background: {colour}; }}'
