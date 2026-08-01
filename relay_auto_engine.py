#!/usr/bin/env python3
"""
LEGACY — do not run.

Production relay automation:
  iot_core/runners/relay_engine.py  (systemd: relay-engine.service)

This old engine ignored time windows, leaked DB connections, and would
fight relay_engine over relay_state if started in parallel.
"""

import sys


def main():
    print(
        "ERROR: relay_auto_engine.py is legacy and disabled.\n"
        "Use: systemctl status relay-engine\n"
        "Or:  PYTHONPATH=. .venv/bin/python iot_core/runners/relay_engine.py",
        file=sys.stderr,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
