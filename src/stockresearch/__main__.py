"""Allow ``python -m stockresearch <command>``."""

import sys

from stockresearch.main import main

if __name__ == "__main__":
    sys.exit(main())
