"""Allow `python -m longshot <stage> --config ...` (safer than the console script on Windows,
where multiprocessing re-imports the main module in each worker)."""

import sys

from longshot.cli import main

if __name__ == "__main__":
    sys.exit(main())
