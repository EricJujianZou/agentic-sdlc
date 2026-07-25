import os
import sys

# Make `ledgerlite` importable without installing it.
_TARGET = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _TARGET not in sys.path:
    sys.path.insert(0, _TARGET)
