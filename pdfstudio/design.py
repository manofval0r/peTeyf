"""Explainable PDF design decisions. Brand tokens and composition are independent."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass, fields
import re
from typing import TYPE_CHECKING
from .art_direction import DIRECTIONS, THEME_DEFAULTS
from .tokens import DesignSystem, get_theme
from .scenarios import get_scenario
if TYPE_CHECKING:
    from .content import Document
    from .render import RenderOptions

FAMILIES = ('editorial-narrative', 'evidence-led', 'object-catalogue', 'photo-essay', 'technical-reference', 'institutional-paper')
DIRECTION_FAMILIES = {'object-playful':'object-catalogue', 'editorial-contrast':'editorial-narrative', 'quiet-luxury':'photo-essay', 'technical-field':'technical-reference', 'industrial-machine':'technical-reference', 'institutional-clear':'evidence-led', 'organic-human':'photo-essay', 'scholarly-book':'institutional-paper', 'essential-minimal':'institutional-paper'}
SUGGESTED_THEMES = {'object-playful':'vibrant', 'editorial-contrast':'editorial', 'quiet-luxury':'luxury', 'technical-field':'modern-saas', 'industrial-machine':'brutalist', 'institutional-clear':'corporate', 'organic-human':'warm-sage', 'scholarly-book':'academic', 'essential-minimal':'minimal'}
SCENARIO_DIRECTIONS = {'academic':'scholarly-book', 'whitepaper':'scholarly-book', 'invoice':'essential-minimal', 'resume':'essential-minimal', 'certificate':'quiet-luxury', 'one-pager':'institutional-clear', 'pitch-deck':'institutional-clear', 'proposal':'institutional-clear', 'portfolio':'quiet-luxury', 'brochure':'editorial-contrast'}
EXTRA_KEYWORDS = {'organic-human':('garden','courtyard','landscape','horticulture'), 'quiet-luxury':('photography','travel','hospitality'), 'object-playful':('furniture','catalogue','catalog','product collection')}

@dataclass(frozen=True)
class DesignBrief:
    subject: str
    audience: str
    purpose: str
    visual_argument: str
    output_mode: str = 'print'
    composition: str | None = None

@dataclass
class DesignDecision:
    theme_id: str
    direction_id: str
    family_id: str
    tokens: DesignSystem
    output_mode: str
    locked_fields: tuple[str, ...]
    reasons: tuple[str, ...]
    family_locked: bool


def match_keywords(text: str, keywords: tuple[str, ...]) -> tuple[str, ...]:
    text = text.casefold()
    return tuple(k for k in keywords if re.search(r'(?<!\w)' + r'[\s-]+'.join(re.escape(w) for w in k.casefold().split()) + r'(?!\w)', text))


def recommend_direction(meta: dict, scenario_id: str, body_html: str, theme_id: str):
    explicit = str(meta.get('art_direction') or meta.get('direction') or '').strip()
    if explicit:
        if explicit not in DIRECTIONS:
            raise ValueError(f'Unknown direction {explicit!r}. Supported: {", ".join(DIRECTIONS)}')
        return DIRECTIONS[explicit], (f'Explicit direction: {explicit}.',)
    get_scenario(scenario_id)
    get_theme(theme_id)
    brief = meta.get('design') or {}
    if not isinstance(brief, dict):
        raise ValueError('design must be a mapping.')
    corpus = dict(meta)
    corpus['subject'] = brief.get('subject', meta.get('subject',''))
    corpus['purpose'] = brief.get('purpose', meta.get('purpose',''))
    corpus['body'] = re.sub(r'<[^>]+>', ' ', body_html)[:12000]
    scores = {}
    for key, direction in DIRECTIONS.items():
        score = 0
        keys = tuple(k for k in direction.keywords + EXTRA_KEYWORDS.get(key, ()) if k not in ('brief','study','paper','report','proposal','plan','newsletter','portfolio'))
        for field, weight in (('title',6), ('industry',6), ('subject',6), ('purpose',6), ('subtitle',3), ('summary',3), ('audience',3), ('body',1)):
            text = str(corpus.get(field,''))
            text = re.sub(r'(?i)\b(case[\s-]+study|marketing[\s-]+plan|annual[\s-]+report|research[\s-]+report)\b', '', text)
            score += weight * len(match_keywords(text, keys))
        if str(meta.get('tone','')).casefold() == direction.tone:
            score += 6
        scores[key] = score
    ranked = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    best, value = ranked[0]
    fallback = SCENARIO_DIRECTIONS.get(scenario_id, 'editorial-contrast')
    if value >= 6 and value - ranked[1][1] >= 2:
        return DIRECTIONS[best], (f'Subject evidence selected {best} (score {value}, lead {value-ranked[1][1]}).',)
    why = 'Ambiguous subject evidence' if value >= 6 else 'Insufficient subject evidence'
    return DIRECTIONS[fallback], (f'{why}; neutral scenario fallback {fallback}.',)


def resolve_design(doc: Document, opts: RenderOptions) -> DesignDecision:
    meta = doc.meta or {}
    brief = meta.get('design') or {}
    if not isinstance(brief, dict):
        raise ValueError('design must be a mapping.')
    scenario = get_scenario(opts.scenario or str(meta.get('scenario') or 'report'))
    explicit_theme = opts.theme or meta.get('theme') or brief.get('theme')
    seed = str(explicit_theme or scenario.default_theme)
    get_theme(seed)
    direction_meta = dict(meta)
    if getattr(opts,'art_direction',None):
        direction_meta['art_direction'] = opts.art_direction
    direction, reasons = recommend_direction(direction_meta, scenario.id, doc.body_html, seed)
    explicit_direction = bool(direction_meta.get('art_direction') or direction_meta.get('direction'))
    family = getattr(opts,'composition',None) or meta.get('composition') or brief.get('composition') or DIRECTION_FAMILIES[direction.id]
    if family not in FAMILIES:
        raise ValueError(f'Unknown composition {family!r}. Supported: {", ".join(FAMILIES)}')
    if scenario.id == 'one-pager' and not (meta.get('composition') or getattr(opts,'composition',None) or brief.get('composition')):
        family = 'evidence-led'
    locked = ['palette','fonts','radius','body_size'] if explicit_theme else []
    # Inferred technical subject is light; explicit legacy dark direction remains intentional.
    neutral = any(reason.startswith(('Insufficient','Ambiguous')) for reason in reasons)
    theme_id = str(explicit_theme or (scenario.default_theme if neutral else 'midnight' if explicit_direction and direction.id == 'technical-field' else SUGGESTED_THEMES[direction.id]))
    ds = deepcopy(get_theme(theme_id))
    reasons += (f'Theme {theme_id}: {"explicit tokens locked" if explicit_theme else "scenario/subject suggestion"}.',)
    brand = meta.get('brand') or brief.get('brand') or {}
    if brand and not isinstance(brand, dict):
        raise ValueError('brand must be a mapping of palette/fonts.')
    for group in ('palette','fonts'):
        values = brand.get(group,{})
        if not isinstance(values,dict):
            raise ValueError(f'brand.{group} must be a mapping.')
        valid = {f.name for f in fields(getattr(ds,group))}
        for key, value in values.items():
            if key not in valid or not isinstance(value,str) or any(c in value for c in ';{}<>\n\r'):
                raise ValueError(f'Invalid brand {group} field {key!r}.')
            if group == 'palette' and not re.fullmatch(r'#[0-9a-fA-F]{6}',value):
                raise ValueError(f'Brand colour {key} must be #RRGGBB.')
            setattr(getattr(ds,group),key,value)
            locked.extend((group,key))
    mode = getattr(opts,'output_mode',None) or meta.get('output_mode') or brief.get('output_mode') or 'print'
    if mode not in ('print','digital'):
        raise ValueError('output_mode must be print or digital.')
    ds.extras.update({'field-1':ds.palette.bg,'field-2':ds.palette.panel,'field-3':ds.palette.accent2})
    return DesignDecision(theme_id,direction.id,str(family),ds,str(mode),tuple(sorted(set(locked))),reasons,bool(explicit_direction or getattr(opts,'composition',None) or meta.get('composition') or brief.get('composition')))
