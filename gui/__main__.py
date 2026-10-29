import sys

# PySide6 6.12 drops a reference to True on each signal emit; on 3.11 that aborts the process (bool_dealloc)
if sys.version_info < (3, 12): sys.exit(f'[RED] the GUI needs Python 3.12 or later (this is {sys.version.split()[0]}); the CLI, python -m porter, runs on 3.11')

from gui.app import main

sys.exit(main(sys.argv))
