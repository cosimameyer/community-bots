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

for _mod in _MOCKED_MODULES:
    sys.modules.setdefault(_mod, MagicMock())

# requests must be the real module so its exception classes remain valid
# BaseException subclasses. Without this, the mocked module's attributes
# (e.g. requests.RequestException) are MagicMocks that Python rejects in
# except clauses at runtime.
try:
    import requests
    import requests.exceptions
    sys.modules["requests"] = requests
    sys.modules["requests.exceptions"] = requests.exceptions
except ImportError:
    pass
