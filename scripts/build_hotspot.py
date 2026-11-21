#!/usr/bin/env python3
"""Build a reproducible RouterOS HotSpot ZIP from approved runtime files only.
No compiler is required; the output is copied to the router's active HTML dir.
"""
import argparse
import hashlib
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parent.parent
FILES = (
    'alogin.html', 'error.html', 'flogin.html', 'flogout.html', 'fstatus.html',
    'index.html', 'login.html', 'logout.html', 'redirect.html', 'status.html',
    'css/style.css', 'js/chap-md5.js', 'js/portal.core.js',
    'font/Almarai.woff2', 'font/fontello-used.woff',
)
NAME = 'Jawhrah2-r8-hotspot.zip'


def build(destination: Path) -> tuple[Path, Path]:
    destination.mkdir(parents=True, exist_ok=True)
    output = destination / NAME
    with ZipFile(output, 'w', compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in FILES:
            path = ROOT / relative
            if not path.is_file():
                raise FileNotFoundError(f'Required HotSpot asset is missing: {relative}')
            info = ZipInfo(relative, date_time=(2024, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o644 << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, path.read_bytes(), compress_type=ZIP_DEFLATED, compresslevel=9)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    sums = destination / (NAME + '.sha256')
    sums.write_text(f'{digest}  {NAME}\n', encoding='ascii')
    return output, sums


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    zipped, checksum = build(args.output)
    print(f'Built {zipped} ({zipped.stat().st_size} bytes); SHA-256 in {checksum}')
