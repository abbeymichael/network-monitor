#!/usr/bin/env python3
"""
PingSentry - Desktop uptime monitor with SMS alerting.

Run with:  python3 main.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pingsentry.gui.app import PingSentryApp


def main():
    app = PingSentryApp()
    app.mainloop()


if __name__ == "__main__":
    main()
