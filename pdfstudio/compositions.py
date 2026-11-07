"""Content/asset composition families, independent of colour and type tokens."""
from __future__ import annotations
from collections import OrderedDict
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from .blocks import ContentBlock, present_block
from .design import DesignDecision
from .geometry import PageGeometry
from .asset_layout import AssetLayout

GRAMMAR={
 'editorial-narrative':{'metrics':'open','swot':'statements','callout':'open','heading':'lead','quote':'pull'},
 'evidence-led':{'metrics':'ruled','swot':'matrix','callout':'rail','heading':'findings','quote':'evidence'},
 'object-catalogue':{'metrics':'table','swot':'statements','callout':'open','heading':'stage','quote':'caption'},
 'photo-essay':{'metrics':'open','swot':'statements','callout':'open','heading':'display','quote':'pull'},
 'technical-reference':{'metrics':'table','swot':'matrix','callout':'rail','heading':'indexed','quote':'reference'},
 'institutional-paper':{'metrics':'table','swot':'statements','callout':'open','heading':'formal','quote':'reference'},
}

@dataclass
class SectionLayout:
    section_id: str
    family_id: str
    treatment: str
    columns: int
    field: str | None
    presentations: dict[str,str]
    asset_slots: tuple[str,...]


def plan_sections(blocks: tuple[ContentBlock,...], decision: DesignDecision, assets: dict[str,AssetLayout], geometry: PageGeometry, meta: dict) -> tuple[SectionLayout,...]:
    groups=OrderedDict()
    for block in blocks: groups.setdefault(block.section_id,[]).append(block)
    authored=(meta.get('design') or {}).get('sections',{})
    if not isinstance(authored,dict): raise ValueError('design.sections must be a mapping.')
    heading_ids={block.id for block in blocks if block.kind=='heading'}
    for section,settings in authored.items():
        if section not in heading_ids: raise ValueError(f'Unknown design section {section!r}; use an explicit heading ID.')
        if not isinstance(settings,dict) or set(settings)-{'role','field'}: raise ValueError(f'Invalid settings for section {section!r}.')
        if settings.get('role','flow') not in ('flow','opening','feature','closing'): raise ValueError('Invalid section role.')
        if settings.get('field') not in (None,'bg','panel','accent'): raise ValueError('Invalid section field.')
    result=[]
    for section,items in groups.items():
        slots=tuple(b.request_slot for b in items if b.request_slot in assets)
        present=[assets[s] for s in slots]
        family=decision.family_id
        columns=2 if family=='evidence-led' and geometry.inner_width_mm>=140 else 1
        if family=='object-catalogue' and any(a.role in ('object','logo') for a in present) and geometry.inner_width_mm>=130: columns=2
        if family=='photo-essay' and any(a.role=='photo' and a.aspect<.85 for a in present) and geometry.inner_width_mm>=130: columns=2
        settings=authored.get(section,{})
        result.append(SectionLayout(section,family,settings.get('role','flow'),columns,settings.get('field'),dict(GRAMMAR[family]),slots))
    return tuple(result)


def render_sections(blocks: tuple[ContentBlock,...], layouts: tuple[SectionLayout,...], credits_html: str = '') -> str:
    env=Environment(loader=FileSystemLoader(str(Path(__file__).parent/'templates')),autoescape=select_autoescape(['html','xml','j2']))
    template=env.get_template('compositions/section.html.j2')
    out=[]
    for number,layout in enumerate(layouts,1):
        pieces=[]
        for b in blocks:
            if b.section_id!=layout.section_id: continue
            variant=layout.presentations.get(b.kind,'flow')
            if b.kind=='callout' and 'callout--warning' in b.html: variant='alert'
            if b.kind not in ('metrics','swot','callout'): variant='flow'
            pieces.append(present_block(b,variant))
        out.append(template.render(layout=layout,number=number,blocks_html=''.join(pieces),credits_html=credits_html if number==len(layouts) else ''))
    return ''.join(out)


def composition_signature(layouts: tuple[SectionLayout,...]) -> tuple[tuple,...]:
    return tuple((l.treatment,l.columns,tuple(sorted(l.presentations.items())),bool(l.asset_slots)) for l in layouts)


def _contrast(a,b):
    def lum(c):
        rgb=[int(c[i:i+2],16)/255 for i in (1,3,5)]
        rgb=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in rgb]
        return sum(v*w for v,w in zip(rgb,(.2126,.7152,.0722)))
    x,y=sorted((lum(a),lum(b))); return (y+.05)/(x+.05)


def adapt_composition(decision: DesignDecision, blocks, assets: dict[str,AssetLayout]) -> DesignDecision:
    if decision.family_locked or decision.family_id in ('institutional-paper','technical-reference','evidence-led'):
        return decision
    reviewed=[a for a in assets.values() if a.approved]
    family=decision.family_id
    if any(a.role=='object' for a in reviewed): family='object-catalogue'
    elif any(a.role=='diagram' for a in reviewed): family='technical-reference'
    elif any(a.role=='photo' for a in reviewed): family='photo-essay'
    elif any(b.kind=='chart' for b in blocks): family='evidence-led'
    if family==decision.family_id: return decision
    return replace(decision,family_id=family,reasons=decision.reasons+(f'Composition adapted to reviewed asset/content roles: {family}.',))


def apply_asset_accent(decision: DesignDecision, assets: dict[str,AssetLayout]) -> DesignDecision:
    if {'palette','accent'} & set(decision.locked_fields): return decision
    for a in assets.values():
        if a.approved and a.accent:
            if _contrast(a.accent,decision.tokens.palette.bg)<4.5: continue
            ds=deepcopy(decision.tokens); ds.palette.accent=a.accent
            return replace(decision,tokens=ds,reasons=decision.reasons+(f'Approved opt-in asset accent from {a.slot}.',))
    return decision
