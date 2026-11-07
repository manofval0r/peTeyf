"""Order-preserving semantic blocks; unrecognised trusted HTML stays opaque."""
from __future__ import annotations
from dataclasses import dataclass
from html.parser import HTMLParser
import html
import re
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .content import Document

@dataclass
class ContentBlock:
    id: str
    kind: str
    html: str
    section_id: str
    request_slot: str | None = None
    presentation: str | None = None

VOID={'img','br','hr','meta','link','input','source','wbr','area','base','col','embed','param','track'}

class _Roots(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.source=source; self.lines=[0]; self.parts=[]; self.depth=0; self.cursor=0
        for m in re.finditer('\n',source): self.lines.append(m.end())
    def position(self):
        row,col=self.getpos(); return self.lines[row-1]+col
    def flush(self,end):
        if end>self.cursor:
            self.parts.append(self.source[self.cursor:end]); self.cursor=end
    def handle_starttag(self,tag,attrs):
        pos=self.position()
        if self.depth==0: self.flush(pos)
        if tag not in VOID: self.depth+=1
        elif self.depth==0: self.flush(pos+len(self.get_starttag_text()))
    def handle_startendtag(self,tag,attrs):
        pos=self.position()
        if self.depth==0:
            self.flush(pos); self.flush(pos+len(self.get_starttag_text()))
    def handle_endtag(self,tag):
        if tag in VOID: return
        self.depth=max(0,self.depth-1)
        if self.depth==0:
            end=self.source.find('>',self.position())+1
            self.flush(end)
    def finish(self):
        self.feed(self.source); self.close(); self.flush(len(self.source)); return self.parts


def parse_blocks(doc: Document) -> tuple[ContentBlock,...]:
    roots=_Roots(doc.body_html).finish()
    result=[]; section='preamble'
    authored=(doc.meta.get('design') or {}).get('sections',{}) if isinstance(doc.meta.get('design') or {},dict) else {}
    for part in roots:
        if not part.strip():
            if result: result[-1].html+=part
            continue
        heading=re.match(r'<h([1-6])\b([^>]*)>',part,re.I)
        slot=re.search(r'@@(?:IMG|CHART)_\d+@@',part)
        kind='flow'
        if heading:
            kind='heading'
            ident=re.search(r"""\bid=["']([^"']+)""",heading.group(2))
            sid=ident.group(1) if ident else f'section-{len(result)+1}'
            if heading.group(1)=='1' or sid in authored or section=='preamble': section=sid
        elif slot: kind='figure' if slot.group().startswith('@@IMG') else 'chart'
        else:
            tag=re.match(r'<(\w+)\b',part)
            tag=tag.group(1).lower() if tag else ''
            classes=re.search(r"""\bclass=["']([^"']+)""",part)
            classes=set(classes.group(1).split()) if classes else set()
            kind=next((k for k in ('metrics','swot','callout','figure','chart') if k in classes),'flow')
            if kind=='flow': kind={'p':'paragraph','ul':'list','ol':'list','table':'table','blockquote':'quote','pre':'code'}.get(tag,'flow')
        bid=sid if heading else f'{section}-block-{len(result)+1}'
        result.append(ContentBlock(bid,kind,part,section,slot.group() if slot else None))
    return tuple(result)


def present_block(block: ContentBlock, variant: str) -> str:
    allowed={'metrics':{'open','ruled','table'},'swot':{'matrix','statements'},'callout':{'open','rail','alert'}}
    if block.kind in allowed and variant not in allowed[block.kind]: raise ValueError(f'Invalid {block.kind} presentation {variant!r}.')
    if not re.fullmatch(r'[a-z-]+',variant): raise ValueError('Unsafe presentation identifier.')
    return f'<div class="block block--{html.escape(block.kind)} variant--{variant}" data-block-id="{html.escape(block.id,quote=True)}">{block.html}</div>'
