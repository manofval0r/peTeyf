from pathlib import Path
p=Path('C:/Users/HomePC/Documents/Default Project/pdf-studio/examples/crocs-plan.md')
t=p.read_text(encoding='utf-8')
has_dash=' — ' in t or '—' in t
fun_words=['fun','comfortable','playful','habit','refresh']
print('FILE:', 'crocs-plan.md')
print('HAS_EM_DASH:', has_dash, '| FUN_WORDS:', any(w in t.lower() for w in fun_words))
print('LINES:', len(t.splitlines()))

import fitz
pdf=Path('C:/Users/HomePC/Documents/Default Project/pdf-studio/out/crocs-plan.pdf')
if pdf.exists():
    d=fitz.open(str(pdf))
    print('PDF:', d.page_count, 'pages,', d.load_page(0).rect.width, 'x', d.load_page(0).rect.height, 'pt')
    d.close()
else:
    print('PDF not found at', pdf)
