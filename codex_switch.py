#!/usr/bin/env python3
"""Codex multi-account switcher: the file to run.

  python3 codex_switch.py              open the menu
  python3 codex_switch.py status       show saved accounts and the active one
  python3 codex_switch.py use NAME     switch the main login to a saved account
  python3 codex_switch.py add [NAME]   log in and save a new account
  python3 codex_switch.py remove NAME  delete a saved account
  python3 codex_switch.py logout       log out the active account

Windows: python or py -3 codex_switch.py. The logic is in functions/codex_functions.py.
Standard library only. Requires Python 3.8 or newer.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from functions.codex_functions import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
