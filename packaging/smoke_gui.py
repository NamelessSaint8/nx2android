# Run by the frozen app (nx2android packaging/smoke_gui.py) from packaging/smoke_bundle.py, under QT_QPA_PLATFORM=offscreen. It checks what only a
# frozen, possibly signed, app can show: the engine's modules import, capstone disassembles under the hardened runtime with no entitlements
# (RESEARCH Assumption A9), and the desktop Window starts and lists the profiles (its Games tab asks a porter child process for them).
import sys, time
from pathlib import Path

if not getattr(sys, 'frozen', False): sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # a checkout run finds gui/ as the bundle does

FAILS = []


def check(name, ok, detail=''):
    print(f'PASS {name}' if ok else f'[RED] {name}' + (f': {detail}' if detail else ''), flush=True)
    if not ok: FAILS.append(name)


def main():
    import importlib
    for m in ('lz4.block', 'capstone', 'PIL.Image', 'yaml', 'compression.zstd' if sys.version_info >= (3, 14) else 'backports.zstd'):
        try: importlib.import_module(m); check(f'import {m}', True)
        except Exception as e: check(f'import {m}', False, repr(e))
    try:
        import capstone
        ins = list(capstone.Cs(capstone.CS_ARCH_ARM64, capstone.CS_MODE_ARM).disasm(bytes.fromhex('1f2003d5'), 0))
        check('capstone disassembles an AArch64 nop', [i.mnemonic for i in ins] == ['nop'], str([i.mnemonic for i in ins]))
    except Exception as e: check('capstone disassembles an AArch64 nop', False, repr(e))
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from gui.app import Window
    app = QApplication(sys.argv[:1]); w = Window(); w.show(); end = time.monotonic() + 30
    def poll():
        if w.games.table.rowCount() > 0 or time.monotonic() > end: app.quit()
    t = QTimer(); t.timeout.connect(poll); t.start(100)
    app.exec()
    n = w.games.table.rowCount()
    check(f'Window: {n} profiles', n > 0, 'the Games tab stayed empty for 30 s')
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
