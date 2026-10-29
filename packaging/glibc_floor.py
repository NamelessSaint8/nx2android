# The newest GLIBC_ symbol version any ELF in a Linux bundle needs, and a gate on it:
#   python packaging/glibc_floor.py dist/nx2android 2.34      (exit 1 above the floor)
# The x64 bundle is gated at 2.34 and the arm64 bundle at 2.39 (the arm64 PySide6 wheel alone needs GLIBC_2.38); the first release run measures the
# real x64 value (RESEARCH Open Question 4). Needs binutils' objdump.
import re, subprocess, sys
from pathlib import Path


def need(texts):   # {file name: objdump -T text} -> {(major, minor): {file names needing it}}
    out = {}
    for name, text in texts.items():
        for v in set(re.findall(r'GLIBC_(\d+)\.(\d+)', text)): out.setdefault(tuple(map(int, v)), set()).add(name)
    return out


def objdump(root):
    texts = {}
    for f in sorted(Path(root).rglob('*')):
        if f.is_file() and not f.is_symlink():
            with f.open('rb') as h:
                if h.read(4) != b'\x7fELF': continue
            texts[str(f.relative_to(root))] = subprocess.run(['objdump', '-T', str(f)], capture_output=True, text=True).stdout
    return texts


def main(argv, texts=None):
    if len(argv) != 3: sys.exit('usage: python packaging/glibc_floor.py <bundle folder> <floor, e.g. 2.34>')
    n = need(objdump(argv[1]) if texts is None else texts); floor = tuple(int(x) for x in argv[2].split('.'))
    top = max(n, default=(0, 0))
    print(f'glibc floor {top[0]}.{top[1]}: {", ".join(sorted(n.get(top, ()))[:5])}' + (f'  [RED] above {argv[2]}' if top > floor else ''))
    return 1 if top > floor else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
