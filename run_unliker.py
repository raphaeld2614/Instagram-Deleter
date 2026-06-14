"""Launcher script — the PyInstaller entry point and a convenient `python run_unliker.py`."""

import multiprocessing

from unliker.gui import main

if __name__ == "__main__":
    # Required so a frozen (PyInstaller) build never re-launches the GUI when any
    # dependency spins up a child process.
    multiprocessing.freeze_support()
    main()
