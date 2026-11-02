import subprocess, sys

def sh(cmd, label):
    print(f"\n=== {label} ===")
    r = subprocess.run(cmd, shell=True, text=True, capture_output=True,
                       timeout=300, cwd=r"C:\Users\HomePC\Documents\Default Project\pdf-studio")
    text = (r.stdout + r.stderr).strip()
    for line in text.splitlines()[-8:]:
        print(line)
    return r.returncode

sh('python -c "import pathlib; p=pathlib.Path(\'C:/Users/HomePC/.config/opencode/skills/pdf/SKILL.md\'); a=pathlib.Path(\'C:/Users/HomePC/.config/opencode/skills/any2pdf\'); print(\'SKILL_OK=\', p.exists(), \"ANY2PDF_GONE=\", not a.exists())"', "SKILL CHECK")
sh('python -m pdfstudio build examples/marketing-plan.md --out out/final-check.pdf --scenario marketing-plan --images auto --preview-pages 6', "FINAL BUILD")
sh('python -m pdfstudio build examples/certificate.md --out out/final-cert.pdf --scenario certificate --images off --no-preview', "CERTIFICATE")
