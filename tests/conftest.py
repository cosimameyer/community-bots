"""
Pytest configuration: mock heavy third-party modules so the test suite can
be collected and run without the full production dependency set installed.
All actual calls to these modules are patched individually in each test.
"""
import sys
from unittest.mock import MagicMock, patch
import pytest

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


@pytest.fixture(autouse=True)
def _isolate_seen_cids_file():
    """
    Prevent tests from reading or writing the persistent bluesky_seen_cids.json
    file on disk.  Each test gets an empty in-memory dict from _load_seen_cids
    and _save_seen_cids is a no-op.  This stops state leaking between test runs.
    """
    try:
        import boost_tags
    except ImportError:
        yield
        return

    with patch.object(boost_tags.BoostTags, "_load_seen_cids", return_value={}), \
         patch.object(boost_tags.BoostTags, "_save_seen_cids", return_value=None):
        yield


@pytest.fixture(autouse=True)
def _bypass_security_validation():
    """
    Bypass URL allowlist and path validation so tests can use any mock URL or
    tmp_path without raising ValueError.  Dedicated security unit tests exercise
    these checks directly; other tests should not be blocked by them.
    """
    import contextlib
    import importlib

    patches = []

    # URL and path validation in RSSData and PackagesData
    for module_name, cls_name in [
        ("get_rss_data", "RSSData"),
        ("get_packages_data", "PackagesData"),
    ]:
        try:
            mod = sys.modules.get(module_name) or importlib.import_module(module_name)
            cls = getattr(mod, cls_name)
            patches.append(patch.object(cls, "_validate_urls", return_value=None))
            patches.append(patch.object(cls, "_validate_json_file_path", return_value=None))
        except (ImportError, AttributeError):
            pass

    # Archive path validation in PromoteBlogPost
    try:
        mod = sys.modules.get("promote_blog_post") or importlib.import_module("promote_blog_post")
        cls = getattr(mod, "PromoteBlogPost")

        original_save = cls._save_rss_feed_archive.__func__ if hasattr(cls._save_rss_feed_archive, "__func__") else cls._save_rss_feed_archive

        def _save_no_check(self, feed, rss_feed_archive):
            import os, json
            archive_path = os.path.join(feed['ARCHIVE'][0], 'file.json')
            with open(archive_path, 'w', encoding='utf-8') as fp:
                json.dump(rss_feed_archive, fp)
            self.logger.info("Archive for %s updated successfully.", feed['name'])

        patches.append(patch.object(cls, "_save_rss_feed_archive", _save_no_check))
    except (ImportError, AttributeError):
        pass

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield
