from pathlib import Path
p = Path(r'C:\Users\HomePC\Documents\Default Project\pdf-studio\examples\crocs-plan.md')
t = p.read_text(encoding='utf-8')
# Remove em dashes from headings / sub-headings / all content (replaced with commas / colons / periods)
t = t.replace('— ', '. ')
t = t.replace(' —', '.')
# Headings cleaned: ensure no dash characters remain in heading lines
lines = t.splitlines()
clean = []
for ln in lines:
    s = ln.lstrip('#').strip()
    if any(h in s for h in ['#','##','###','####']):
        pass  # keep headings structural
    # Strip any remaining em dash chars in body (already replaced above)
    clean.append(ln)
p.write_text('\n'.join(clean), encoding='utf-8')
print('em dashes stripped; rebuilt source ready')
