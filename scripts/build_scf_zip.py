"""
Package SCF function code into a zip for upload.

Outputs dist/scf.zip containing:
- scripts/server_scf.py (entry: main_handler)
- db/zhl.sqlite3 (data file)

You can upload this zip via Tencent Cloud SCF console or API.
"""
import os
from pathlib import Path
import zipfile

BASE = Path(__file__).resolve().parent.parent
DIST = BASE / 'dist'

FILES = [
    (BASE / 'scripts' / 'server_scf.py', 'server_scf.py'),
    (BASE / 'db' / 'zhl.sqlite3', 'db/zhl.sqlite3'),
]

def main():
    DIST.mkdir(exist_ok=True)
    out = DIST / 'scf.zip'
    with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for src, arc in FILES:
            if not src.exists():
                raise FileNotFoundError(f'Missing: {src}')
            z.write(src, arcname=arc)
    print('Built:', out)

if __name__ == '__main__':
    main()