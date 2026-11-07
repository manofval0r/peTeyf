"""Render deterministic built-in skill fixtures; no custom CSS or PDF edits."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import fitz
from PIL import Image, ImageDraw, ImageOps
from pdfstudio.content import load_document
from pdfstudio.render import RenderOptions, render
from pdfstudio.qa import has_errors

ROOT=Path(__file__).resolve().parents[1]
FIXTURES=tuple(ROOT/'tests'/'fixtures'/'design'/f'{name}.md' for name in ('editorial','evidence','object','photo','technical','institutional'))


def make_assets():
    out=ROOT/'out'/'skill-upgrade'/'gallery-assets'; out.mkdir(parents=True,exist_ok=True)
    obj=Image.new('RGBA',(1000,1400),(0,0,0,0)); d=ImageDraw.Draw(obj)
    d.rounded_rectangle((230,100,770,840),80,fill='#B96C47'); d.polygon([(260,830),(340,830),(280,1310),(200,1310)],fill='#70432B'); d.polygon([(660,830),(740,830),(800,1310),(720,1310)],fill='#70432B'); d.rectangle((230,760,770,880),fill='#895232'); obj.save(out/'object.png')
    portrait=Image.new('RGB',(1000,1600),'#B6CEC4'); d=ImageDraw.Draw(portrait)
    d.rectangle((0,650,1000,1600),fill='#315D53'); d.rectangle((120,350,320,1300),fill='#E8D7B5'); d.rectangle((600,120,810,1180),fill='#D7C6A3'); d.ellipse((180,850,890,1560),fill='#789785'); portrait.save(out/'portrait.png')
    diagram=Image.new('RGB',(1600,380),'#F4F5F7'); d=ImageDraw.Draw(diagram)
    for x in (80,620,1160): d.rounded_rectangle((x,90,x+350,290),20,outline='#233446',width=8)
    for x in (450,990): d.line((x,190,x+130,190),fill='#C74632',width=10); d.polygon([(x+130,190),(x+105,170),(x+105,210)],fill='#C74632')
    diagram.save(out/'diagram.png')


def render_gallery(output_dir: Path) -> dict[str,Path]:
    output_dir=output_dir.resolve(); output_dir.mkdir(parents=True,exist_ok=True); make_assets()
    results={}; reports={}; tiles=[]
    for fixture in FIXTURES:
        doc=load_document(fixture); name=fixture.stem; directory=output_dir/name; directory.mkdir(exist_ok=True)
        result=render(doc,RenderOptions(directory/'document.pdf',preview_pages=30,keep_html=True,images='off'))
        results[name]=result.pdf_path; reports[name]=result.report
        with fitz.open(result.pdf_path) as pdf:
            index=1 if len(pdf)>1 else 0; pix=pdf[index].get_pixmap(matrix=fitz.Matrix(.85,.85),alpha=False)
            im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples); im.thumbnail((350,500))
            tile=Image.new('RGB',(390,550),'#ECECEC'); ImageDraw.Draw(tile).text((15,12),result.design_manifest['composition'],fill='#111111'); tile.paste(im,((390-im.width)//2,40)); tiles.append(tile)
        print(name, 'pages=',result.pages,'errors=',[i['code'] for i in result.report.get('issues',[]) if i['severity']=='error'],flush=True)
    sheet=Image.new('RGB',(1170,1100),'#ECECEC')
    for i,tile in enumerate(tiles): sheet.paste(tile,((i%3)*390,(i//3)*550))
    sheet.save(output_dir/'comparison.png'); ImageOps.grayscale(sheet).save(output_dir/'comparison-grayscale.png')
    (output_dir/'qa.json').write_text(json.dumps(reports,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
    if any(has_errors(r) for r in reports.values()): raise RuntimeError('Gallery has QA errors; inspect qa.json and final previews.')
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',type=Path,default=ROOT/'out'/'design-gallery'); args=p.parse_args(); render_gallery(args.out)
