"""Inspect all PDF pages without changing the documents."""
import argparse
from pathlib import Path
import fitz
from PIL import Image, ImageDraw

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--out',required=True,type=Path); p.add_argument('--columns',type=int,default=4); p.add_argument('pdfs',nargs='+',type=Path); a=p.parse_args()
    tiles=[]
    for path in a.pdfs:
        with fitz.open(path) as pdf:
            for number,page in enumerate(pdf,1):
                pix=page.get_pixmap(matrix=fitz.Matrix(.65,.65),alpha=False); im=Image.frombytes('RGB',(pix.width,pix.height),pix.samples); im.thumbnail((260,380))
                tile=Image.new('RGB',(290,425),'#ECECEC'); ImageDraw.Draw(tile).text((10,10),f'{path.parent.name}: {number}/{len(pdf)}',fill='#111111'); tile.paste(im,((290-im.width)//2,35)); tiles.append(tile)
    rows=(len(tiles)+a.columns-1)//a.columns; sheet=Image.new('RGB',(290*a.columns,425*rows),'#ECECEC')
    for i,tile in enumerate(tiles): sheet.paste(tile,((i%a.columns)*290,(i//a.columns)*425))
    a.out.parent.mkdir(parents=True,exist_ok=True); sheet.save(a.out); print('Pages:',len(tiles),'Sheet:',a.out.resolve())
