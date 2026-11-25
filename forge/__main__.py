"""Run Forge from a terminal: python -m forge.

Role: run · Part of: forge · Entry
"""

from .standard import main


if __name__ == '__main__':
    raise SystemExit(
        main()
    )