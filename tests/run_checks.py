"""Windows-safe unittest log capture; no dependency on shell stderr encoding."""
import argparse
from pathlib import Path
import subprocess
import sys

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--log', required=True)
    p.add_argument('--expect-red', action='store_true')
    p.add_argument('modules', nargs='*')
    a = p.parse_args()
    cmd = [sys.executable, '-m', 'unittest'] + (a.modules if a.modules else ['discover', '-s', 'tests', '-p', 'test_*.py']) + ['-v']
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    text = r.stdout + r.stderr
    path = Path(a.log)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    print('\n'.join(text.splitlines()[-20:]))
    print(f'Exit: {r.returncode}; full UTF-8 log: {path}')
    sys.exit(0 if (r.returncode != 0 if a.expect_red else r.returncode == 0) else 1)
