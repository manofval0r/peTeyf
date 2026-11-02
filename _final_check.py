import subprocess, sys, pathlib

def run(cmd, label):
    print(f"\n=== {label} ===")
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                            timeout=300, cwd=r"C:\Users\HomePC\Documents\Default Project\pdf-studio")
        lines = (out.stdout + out.stderr).strip().splitlines()
        print("\n".join(lines[-8:]))
    except Exception as e:
        print("ERROR:", e)

run('python -c "import pathlib; p=pathlib.Path(r\'C:\\Users\\HomePC\\.config\\opencode\\skills\\pdf\\SKILL.md\'); a=pathlib.Path(r\'C:\\Users\\HomePC\\.config\\opencode\\skills\\any2pdf\'); print(\'SKILL=\', p.exists(), \"ANY2PDF_GONE=\", not a.exists())"', "SKILL STATUS")
run('python -m pdfstudio build examples/marketing-plan.md --out out/final-check.pdf --scenario marketing-plan --images auto --preview-pages 6', "FINAL MARKETING PLAN")
run('python -m pdfstudio build examples/certificate.md --out out/final-cert.pdf --scenario certificate --images off --no-preview', "CERTIFICATE")
