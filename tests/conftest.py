"""
Pytest configuration: mock heavy third-party modules so the test suite can
be collected and run without the full production dependency set installed.
All actual calls to these modules are patched individually in each test.
"""
import sys
from unittest.mock import MagicMock

_MOCKED_MODULES = [
    "atproto",
    "atproto.client_utils",
    "atproto.models",
    "google.generativeai",
    "feedparser",
]

for _mod in _MOCKED_MODULES:
    sys.modules.setdefault(_mod, MagicMock())
