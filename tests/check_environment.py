"""Simple environment check for SalesLens.

This script only validates that the core analysis libraries can be imported.
It does not read or modify any dataset.
"""

import sys


def main() -> int:
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import matplotlib  # noqa: F401
    import seaborn  # noqa: F401

    print("Environment OK")
    print(f"Python: {sys.version.split()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
