"""Manifest-aware checks of rendered PDF paint, text bounds and content presence."""
from __future__ import annotations
from dataclasses import asdict
import html
from pathlib import Path
import re
import unicodedata
import fitz


def plain_text(markup: str) -> str:
    return html.unescape(re.sub(r'<[^>]+>',' ',markup)).strip()


def normalise(text: str) -> str:
    return re.sub(r'[\W_]+','',unicodedata.normalize('NFKC',text).casefold())


def build_design_manifest(decision,geometry,layouts,assets,custom_css: bool) -> dict:
    return {'schema_version':1,'theme':decision.theme_id,'direction':decision.direction_id,'composition':decision.family_id,'output_mode':decision.output_mode,'locks':list(decision.locked_fields),'reasons':list(decision.reasons),'custom_css':bool(custom_css),'geometry':{'width_mm':geometry.width_mm,'height_mm':geometry.height_mm,'safe_mm':list(geometry.safe_mm)},'palette':asdict(decision.tokens.palette),'fonts':asdict(decision.tokens.fonts),'sections':[{**asdict(s),'asset_slots':list(s.asset_slots),'pages':[]} for s in layouts],'assets':[{**asdict(a),'focal':list(a.focal),'crop':list(a.crop) if a.crop else None} for a in assets.values()],'expected_text':[],'cover_pages':0,'skip_pages':[]}


def text_units(markup):
    from html.parser import HTMLParser
    class Units(HTMLParser):
        def __init__(self): super().__init__(convert_charrefs=True); self.units=[]
        def handle_data(self,data):
            if data.strip(): self.units.append(data.strip())
    parser=Units(); parser.feed(markup); return parser.units


def _ink_spans(page,safe):
    top,right,bottom,left=[v*72/25.4 for v in safe]
    spans=[]
    for trace in page.get_texttrace():
        box=fitz.Rect(trace['bbox'])
        if box.y1<=top+1 or box.y0>=page.rect.height-bottom-1: continue
        text=''.join(chr(c[0]) for c in trace['chars'] if 0<=c[0]<=0x10FFFF)
        if text.strip(): spans.append({'text':text,'bbox':trace['bbox'],'size':trace['size']})
    return spans


def _page_text(page,safe=(20,18,22,18)):
    # Texttrace uses character ink/advance boxes rather than inflated font ascenders.
    return normalise(' '.join(s['text'] for s in _ink_spans(page,safe)))


def map_rendered_sections(pdf_path: Path, blocks, layouts, skip_pages=None, safe_mm=(20,18,22,18)) -> dict[str,tuple[int,...]]:
    skip=set(skip_pages or ())
    with fitz.open(pdf_path) as pdf:
        texts=[_page_text(p,safe_mm) if i+1 not in skip else '' for i,p in enumerate(pdf)]
    starts=[]; cursor=0; offset=0
    for section in layouts:
        items=[b for b in blocks if b.section_id==section.section_id]
        lead=next((b for b in items if b.kind=='heading'),items[0] if items else None)
        target=normalise(plain_text(lead.html)) if lead else ''
        found=None
        for i in range(cursor,len(texts)):
            position=texts[i].find(target,offset if i==cursor else 0) if target else -1
            if position>=0:
                found=i+1; cursor=i; offset=position+len(target); break
        starts.append(found)
    result={}
    for i,section in enumerate(layouts):
        start=starts[i]
        if start is None: result[section.section_id]=(); continue
        next_start=next((v for v in starts[i+1:] if v is not None),len(texts)+1)
        # Sections sharing a page all include it; field changes require a boundary.
        end=max(start,next_start-1)
        result[section.section_id]=tuple(p for p in range(start,end+1) if p not in skip)
    return result


def check_design(pdf_path: Path, manifest: dict) -> dict:
    if manifest.get('schema_version')!=1: raise ValueError('Unsupported design manifest schema.')
    issues=[]; exceptions=[]; observations=[]
    def issue(code,message,page=None,severity='error'):
        record={'severity':severity,'code':code,'message':message}
        if page is not None: record['page']=page
        issues.append(record)
    g=manifest['geometry']; safe=g['safe_mm']; top,right,bottom,left=[v*72/25.4 for v in safe]
    skip=set(manifest.get('skip_pages',[]))|set(range(1,manifest.get('cover_pages',0)+1))
    palette=manifest['palette']; fields={}; roles={}
    for section in manifest['sections']:
        if not section.get('pages'): issue('page_mapping',f"No measured pages for section {section['section_id']}.")
        for p in section.get('pages',[]):
            colour=palette[section.get('field') or 'bg']
            if p in fields and fields[p]!=colour: issue('page_mapping','Conflicting field runs on one physical page.',p)
            fields[p]=colour
            roles.setdefault(p,[]).append(section['treatment'])
    content=[]
    with fitz.open(pdf_path) as pdf:
        for number,page in enumerate(pdf,1):
            if number in skip: continue
            content.append(_page_text(page,safe))
            expected=fields.get(number,palette['bg'])
            rgb=tuple(int(expected[i:i+2],16) for i in (1,3,5))
            pix=page.get_pixmap(alpha=False)
            points=((3,3),(pix.width//2,3),(pix.width-4,3),(3,pix.height//2),(pix.width-4,pix.height//2),(3,pix.height-4),(pix.width//2,pix.height-4),(pix.width-4,pix.height-4))
            if any(any(abs(a-b)>3 for a,b in zip(pix.pixel(x,y),rgb)) for x,y in points): issue('page_field','Physical sheet edges do not match the declared page field.',number)
            occupied=0; meaningful=0
            for block in page.get_text('dict')['blocks']:
                if block['type']==1:
                    box=fitz.Rect(block['bbox']); occupied+=box.get_area(); meaningful+=1; continue
            for span in _ink_spans(page,safe):
                box=fitz.Rect(span['bbox'])
                meaningful+=1; occupied+=box.get_area()
                if box.x0<left-1 or box.x1>page.rect.width-right+1 or box.y0<top-1 or box.y1>page.rect.height-bottom+1:
                    issue('safe_area','Rendered text leaves its declared safe area.',number)
            area=(page.rect.width-left-right)*(page.rect.height-top-bottom)
            fill=min(1,occupied/area) if area else 0
            intentional=any(role!='flow' for role in roles.get(number,[]))
            if meaningful==0: issue('empty_design_page','No content on a non-cover/TOC page.',number)
            elif fill<.35:
                if intentional: exceptions.append({'page':number,'reason':'Authored opening/feature/closing treatment','occupancy':round(fill,3)})
                else: issue('sparse_flow','Low text/image occupancy on ordinary flow; inspect for avoidable spill, do not add filler.',number,'warning')
            observations.append({'page':number,'field':expected,'occupancy':round(fill,3),'intentional_feature':intentional})
    text=''.join(content)
    for expected in manifest.get('expected_text',[]):
        target=normalise(expected)
        if len(target)>=10 and target not in text:
            issue('missing_content',f'Source content not found in rendered body: {expected[:100]}')
    return {'passed':not any(i['severity']=='error' for i in issues),'issues':issues,'exceptions':exceptions,'pages':observations,'limitations':['Semantic image relevance/crop approval and grayscale aesthetic diversity require visual review.','Raster chart label sizes are checked at generation/final width, not by PDF text extraction.']}
