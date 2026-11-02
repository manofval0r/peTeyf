from pathlib import Path
from playwright.sync_api import sync_playwright
import fitz

html = """<!doctype html><html><head><meta charset=utf-8><style>
@page { size: 210mm 297mm; margin: 20mm 18mm 22mm 18mm; }
@page cover { size: 210mm 297mm; margin: 0; }
html,body{margin:0;padding:0}
p{font:12pt/1.4 Arial;margin:0}
.cover{page:cover;height:297mm;background:#c3cbe5}
.body{padding:0}
</style></head><body>
<section class=cover><p style="margin:40mm">COVER</p></section>
<section class=body><p>BODY PAGE ONE</p></section>
</body></html>"""
o = Path("out/.pdfstudio/test-named")
o.mkdir(parents=True, exist_ok=True)
(o/"t.html").write_text(html, encoding="utf-8")
with sync_playwright() as pw:
    b = pw.chromium.launch()
    pg = b.new_page()
    pg.goto((o/"t.html").resolve().as_uri())
    pg.pdf(path=str(o/"t.pdf"), print_background=True, prefer_css_page_size=True,
           margin={"top":"0","right":"0","bottom":"0","left":"0"})
    b.close()
d = fitz.open(o/"t.pdf")
print("pages", d.page_count)
for i,p in enumerate(d,1):
    print(i, "bg", p.get_drawings()[:1], "text", [round(v,1) for v in p.get_text("blocks")[0][:4]] if p.get_text("blocks") else None)
