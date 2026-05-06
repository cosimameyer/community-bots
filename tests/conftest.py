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
    "google",
    "google.genai",
    "feedparser",
    "requests",
    "requests.exceptions",
    "bs4",
    "mastodon",
]

# requests must be the real module so its exception classes remain valid
# BaseException subclasses. Import it before the setdefault loop so
# sys.modules["requests"] is already populated and setdefault is a no-op.
try:
    import importlib
    importlib.import_module("requests")
    importlib.import_module("requests.exceptions")
except ImportError:
    pass

for _mod in _MOCKED_MODULES:
    sys.modules.setdefault(_mod, MagicMock())
