from pathlib import Path
text = Path(r'C:\Users\HomePC\.agents\skills\impeccable\reference\craft-floor.md').read_text(encoding='utf-8', errors='replace')
print('LENGTH:', len(text))
print(text[:3000])
print('---END---')
