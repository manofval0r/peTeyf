import base64, re, requests
from pathlib import Path

root = Path(r'C:\Users\HomePC\Documents\Default Project\pdf-studio')
out_dir = root / 'assets' / 'fonts'
out_dir.mkdir(parents=True, exist_ok=True)
ua = {'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131 Safari/537.36'}

families = [
  ('Fraunces', 'https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,600;9..144,700&display=swap'),
  ('Space Grotesk', 'https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap'),
  ('Source Serif 4', 'https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap'),
  ('Barlow Condensed', 'https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;500;600;700&display=swap'),
  ('Manrope', 'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap'),
]

blocks=[]
# Fontshare Clash Grotesk
clash = [
 ('400','https://cdn.fontshare.com/wf/O462VY6O6FTQCS72XVMTQHXAM4NN5CY3/TWF57ITZORMJ3MEWLQQIVO6BMXIB6FUR/MJQFMMOTEGNXDVM7HBBDTQHTVB2M7Y6G.woff2'),
 ('500','https://cdn.fontshare.com/wf/2SAK53YLUN7RMYJU4MYLSBV6SSSJEJZB/RXS4DPGJRKOUFZMF5X5BVUGNNKJT65XZ/DJS4RYGIUYUXJQOHY5VCZPKSTXUSHTSP.woff2')]
for weight,url in clash:
    data=requests.get(url,timeout=30).content
    fn=f'clash-grotesk-{weight}.woff2'; (out_dir/fn).write_bytes(data)
    b64=base64.b64encode(data).decode('ascii')
    blocks.append(f"@font-face{{font-family:'Clash Grotesk';src:url(data:font/woff2;base64,{b64}) format('woff2');font-weight:{weight};font-style:normal;font-display:swap;}}")

for family,url in families:
    css=requests.get(url,headers=ua,timeout=30).text
    face_blocks=re.findall(r'@font-face\s*\{.*?\}',css,re.S)
    kept=[]
    for block in face_blocks:
        # Google serves one block per subset; keep latin (or no unicode range).
        if 'unicode-range' in block and 'U+0000-00FF' not in block:
            continue
        m=re.search(r'url\((https://[^)]+)\)',block)
        if not m: continue
        furl=m.group(1)
        data=requests.get(furl,headers=ua,timeout=30).content
        weight=re.search(r'font-weight:\s*([^;]+)',block)
        style=re.search(r'font-style:\s*([^;]+)',block)
        w=(weight.group(1).strip() if weight else '400').replace(' ','-')
        s=style.group(1).strip() if style else 'normal'
        slug=re.sub(r'[^a-z0-9]+','-',family.lower()).strip('-')
        fn=f'{slug}-{w}-{s}.woff2'; (out_dir/fn).write_bytes(data)
        b64=base64.b64encode(data).decode('ascii')
        block=re.sub(r'url\(https://[^)]+\)',f'url(data:font/woff2;base64,{b64})',block)
        blocks.append(block)
        kept.append(fn)
    print(family, len(kept), kept)

(root/'assets'/'css'/'fonts.css').write_text('\n'.join(blocks),encoding='utf-8')
print('fonts.css bytes', (root/'assets'/'css'/'fonts.css').stat().st_size)
