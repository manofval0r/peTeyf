from pathlib import Path
p=Path(r'C:\Users\HomePC\.agents\skills\impeccable\reference\craft-floor.md')
with p.open('r',encoding='utf-8',errors='ignore') as f:
    for i in range(40):
        line=f.readline()
        if not line: break
        print(i+1, line.rstrip()[:140])
