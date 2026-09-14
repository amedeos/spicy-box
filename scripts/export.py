#!/usr/bin/env python
"""Thin wrapper so the exporter can be run straight from the repository.

Equivalent to the ``spicy-box-export`` console script installed by the package.
"""

import sys

from spicy_box.cli import main

if __name__ == "__main__":
    sys.exit(main())
