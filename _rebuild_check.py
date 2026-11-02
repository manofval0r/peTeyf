import subprocess, sys
cmd = r'python -m pdfstudio build examples/crocs-plan.md --out out/crocs-plan.pdf --scenario marketing-plan --images auto --preview-pages 5'
r = subprocess.run(cmd, shell=True, text=True, capture_output=True, timeout=300, cwd=r"C:\Users\HomePC\Documents\Default Project\pdf-studio")
print("=== OUTPUT ===")
print(r.stdout[-1200:] if len(r.stdout) > 1200 else r.stdout)
print("=== ERR ===")
print(r.stderr[-300:] if len(r.stderr) > 300 else r.stderr)
print("=== EXIT ===")
print(r.returncode)
