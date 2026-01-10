"""Enable python -m cloud_mirror invocation.

This module allows the package to be run as a script:
    python3 -m cloud_mirror [args]

It simply delegates to the main() function.
"""

import sys

from cloud_mirror.main import main

if __name__ == "__main__":
    sys.exit(main())
