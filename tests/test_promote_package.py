# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access
# pylint: disable=too-few-public-methods,unused-argument
"""
Tests for src/promote_package.py
"""

import json
import pytest
from unittest.mock import MagicMock, patch, mock_open

from promote_package import PromotePackage


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

BASE_CONFIG = {
    "platform": "bluesky",
    "counter": "metadata/test_packages_counter.txt",
    "json_file": "metadata/test_packages.json",
    "client_name": "pyladies_bot",
    "api_base_url": "bluesky",
    "password": "pw",
    "username": "user",
}


def make_handler(config=None, no_dry_run=False):
    cfg = {**BASE_CONFIG, **(config or {})}
    return PromotePackage(config_dict=cfg, no_dry_run=no_dry_run)


def make_package(
    name="CiteLang",
    description="Generate credit summaries.",
    repo_url="https://github.com/vsoch/citelang",
    pypi_url="https://pypi.org/project/citelang/",
    pkdown_url="",
    logo_url="https://example.com/logo.png",
    maintainer_name="Vanessa Sochat",
    mastodon="@vsoch@mastodon.social",
    bluesky="vsoch.bsky.social",
):
    return {
        "name": name,
        "description": description,
        "repo_url": repo_url,
        "pypi_url": pypi_url,
        "pkdown_url": pkdown_url,
        "logo_url": logo_url,
        "maintainer_name": maintainer_name,
        "mastodon": mastodon,
        "bluesky": bluesky,
    }


# ---------------------------------------------------------------------------
# _ensure_metadata_prefix
# ---------------------------------------------------------------------------

class TestEnsureMetadataPrefix:
    def test_adds_prefix_when_absent(self):
        assert PromotePackage._ensure_metadata_prefix("counter.txt") == "metadata/counter.txt"

    def test_leaves_existing_prefix_intact(self):
        assert PromotePackage._ensure_metadata_prefix("metadata/counter.txt") == "metadata/counter.txt"

    def test_leaves_relative_metadata_path_intact(self):
        """../metadata/file.txt already contains 'metadata/' so must not be double-prefixed."""
        assert PromotePackage._ensure_metadata_prefix("../metadata/counter.txt") == "../metadata/counter.txt"

    def test_empty_string_unchanged(self):
        assert PromotePackage._ensure_metadata_prefix("") == ""


# ---------------------------------------------------------------------------
# _check_handle
# ---------------------------------------------------------------------------

class TestCheckHandle:
    def test_adds_at_sign_when_missing(self):
        assert PromotePackage._check_handle("alice.bsky.social") == "@alice.bsky.social"

    def test_preserves_existing_at_sign(self):
        assert PromotePackage._check_handle("@alice.bsky.social") == "@alice.bsky.social"

    def test_empty_string_unchanged(self):
        assert PromotePackage._check_handle("") == ""

    def test_single_char_unchanged(self):
        assert PromotePackage._check_handle("a") == "a"


# ---------------------------------------------------------------------------
# define_tags
# ---------------------------------------------------------------------------

class TestDefineTags:
    def test_pyladies_bot_tags(self):
        handler = make_handler({"client_name": "pyladies_bot"})
        tags = handler.define_tags()
        assert "#pyladies" in tags
        assert "#python" in tags
        assert "#opensource" in tags

    def test_rladies_bot_tags(self):
        handler = make_handler({"client_name": "rladies_bot"})
        tags = handler.define_tags()
        assert "#rladies" in tags
        assert "#rstats" in tags
        assert "#opensource" in tags

    def test_unknown_bot_returns_opensource_only(self):
        handler = make_handler({"client_name": "unknown_bot"})
        tags = handler.define_tags()
        assert "#opensource" in tags
        assert "#pyladies" not in tags
        assert "#rladies" not in tags


# ---------------------------------------------------------------------------
# read_counter_name
# ---------------------------------------------------------------------------

class TestReadCounterName:
    def test_reads_and_strips_counter(self):
        handler = make_handler()
        with patch("builtins.open", mock_open(read_data="CiteLang\n")):
            assert handler.read_counter_name() == "CiteLang"

    def test_missing_counter_file_returns_empty_string(self):
        handler = make_handler()
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert handler.read_counter_name() == ""


# ---------------------------------------------------------------------------
# update_counter
# ---------------------------------------------------------------------------

class TestUpdateCounter:
    def test_writes_name_to_counter_file(self):
        handler = make_handler()
        m = mock_open()
        with patch("builtins.open", m):
            handler.update_counter("artpack")
        m.assert_called_once_with(
            BASE_CONFIG["counter"], "w", encoding="utf-8"
        )
        m().write.assert_called_once_with("artpack")


# ---------------------------------------------------------------------------
# read_metadata_json
# ---------------------------------------------------------------------------

class TestReadMetadataJson:
    def test_missing_file_returns_empty_list(self):
        handler = make_handler()
        with patch("builtins.open", side_effect=FileNotFoundError):
            result = handler.read_metadata_json()
        assert result == []

    def test_returns_parsed_packages(self):
        packages = [make_package(name="CiteLang"), make_package(name="artpack")]
        handler = make_handler()
        with patch("builtins.open", mock_open(read_data=json.dumps(packages))):
            result = handler.read_metadata_json()
        assert len(result) == 2
        assert result[0]["name"] == "CiteLang"


# ---------------------------------------------------------------------------
# process_packages — counter & cycling
# ---------------------------------------------------------------------------

class TestProcessPackages:
    def _make_packages(self, names):
        return [make_package(name=n) for n in names]

    def test_promotes_package_after_counter(self):
        """Should promote the package immediately after the counter entry."""
        handler = make_handler(no_dry_run=True)
        packages = self._make_packages(["A", "B", "C"])
        with patch.object(handler, "send_post", return_value="success") as mock_send, \
             patch.object(handler, "update_counter"):
            handler.process_packages(packages, "A", client=None)
        # "A" is at index 0, next is index 1 → "B"
        args = mock_send.call_args[0]
        assert args[0]["name"] == "B"

    def test_wraps_around_at_end_of_list(self):
        """Counter on last item → next is the first."""
        handler = make_handler(no_dry_run=True)
        packages = self._make_packages(["X", "Y", "Z"])
        with patch.object(handler, "send_post", return_value="success"), \
             patch.object(handler, "update_counter") as mock_update:
            handler.process_packages(packages, "Z", client=None)
        mock_update.assert_called_once_with("X")

    def test_unknown_counter_starts_from_second_item(self):
        """Counter name not in list → start_index stays 0, next is index 1."""
        handler = make_handler(no_dry_run=True)
        packages = self._make_packages(["P", "Q", "R"])
        with patch.object(handler, "send_post", return_value="success"), \
             patch.object(handler, "update_counter") as mock_update:
            handler.process_packages(packages, "UNKNOWN", client=None)
        mock_update.assert_called_once_with("Q")

    def test_update_counter_called_even_on_failed_post(self):
        """Counter advances even if the post fails."""
        handler = make_handler(no_dry_run=True)
        packages = self._make_packages(["A", "B"])
        with patch.object(handler, "send_post", return_value="failed"), \
             patch.object(handler, "update_counter") as mock_update:
            handler.process_packages(packages, "A", client=None)
        mock_update.assert_called_once_with("B")

    def test_dry_run_does_not_call_send_post(self):
        handler = make_handler(no_dry_run=False)
        packages = self._make_packages(["A", "B"])
        with patch.object(handler, "send_post") as mock_send, \
             patch.object(handler, "update_counter"):
            handler.process_packages(packages, "A", client=None)
        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# build_post_mastodon
# ---------------------------------------------------------------------------

class TestBuildPostMastodon:
    def test_includes_package_name(self):
        handler = make_handler({"platform": "mastodon"})
        post = handler.build_post_mastodon(make_package(name="CiteLang"))
        assert "CiteLang" in post

    def test_includes_description(self):
        handler = make_handler({"platform": "mastodon"})
        post = handler.build_post_mastodon(make_package(description="Great lib."))
        assert "Great lib." in post

    def test_includes_repo_url(self):
        handler = make_handler({"platform": "mastodon"})
        post = handler.build_post_mastodon(make_package(repo_url="https://github.com/x/y"))
        assert "https://github.com/x/y" in post

    def test_includes_maintainer_name(self):
        handler = make_handler({"platform": "mastodon"})
        post = handler.build_post_mastodon(make_package(maintainer_name="Alice"))
        assert "Alice" in post

    def test_includes_mastodon_handle(self):
        handler = make_handler({"platform": "mastodon"})
        post = handler.build_post_mastodon(make_package(mastodon="@alice@fosstodon.org"))
        assert "@alice@fosstodon.org" in post

    def test_no_pypi_or_docs_links_in_post(self):
        """Post should only contain the repo URL, not pypi or pkdown links."""
        handler = make_handler({"platform": "mastodon"})
        post = handler.build_post_mastodon(make_package(
            pypi_url="https://pypi.org/project/mylib/",
            pkdown_url="https://pkg.example.com/",
        ))
        assert "PyPI" not in post
        assert "Docs" not in post
        assert "pypi.org" not in post
        assert "pkg.example.com" not in post

    def test_missing_maintainer_skips_author_line(self):
        handler = make_handler({"platform": "mastodon"})
        post = handler.build_post_mastodon(make_package(maintainer_name="", mastodon=""))
        assert "👤" not in post

    def test_includes_hashtags(self):
        handler = make_handler({"client_name": "pyladies_bot", "platform": "mastodon"})
        post = handler.build_post_mastodon(make_package())
        assert "#pyladies" in post

    def test_returns_string(self):
        handler = make_handler({"platform": "mastodon"})
        result = handler.build_post_mastodon(make_package())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# build_post_bluesky
# ---------------------------------------------------------------------------

class FakeTextBuilder:
    """
    Minimal TextBuilder stand-in that accumulates all text/link/tag/mention
    display strings so tests can assert on the full rendered text.
    """
    def __init__(self):
        self._parts = []

    def text(self, s):
        self._parts.append(s)
        return self

    def link(self, display, url):
        self._parts.append(display)
        return self

    def mention(self, display, did):
        self._parts.append(display)
        return self

    def tag(self, display, tag_name):
        self._parts.append(display)
        return self

    def build_text(self):
        return "".join(self._parts)


class TestBuildPostBluesky:
    def _make_handler_with_fake_builder(self, config=None):
        """Return a handler whose client_utils.TextBuilder uses FakeTextBuilder."""
        handler = make_handler(config or {"platform": "bluesky"})
        import promote_package as pl
        pl.client_utils.TextBuilder.side_effect = FakeTextBuilder
        return handler

    def test_includes_package_name(self):
        handler = self._make_handler_with_fake_builder()
        with patch.object(handler, "get_bluesky_did", return_value="did:plc:test"):
            tb = handler.build_post_bluesky(make_package(name="CiteLang"))
        assert "CiteLang" in tb.build_text()

    def test_includes_description(self):
        handler = self._make_handler_with_fake_builder()
        with patch.object(handler, "get_bluesky_did", return_value="did:plc:test"):
            tb = handler.build_post_bluesky(make_package(description="Great lib."))
        assert "Great lib." in tb.build_text()

    def test_includes_repo_url(self):
        handler = self._make_handler_with_fake_builder()
        with patch.object(handler, "get_bluesky_did", return_value="did:plc:test"):
            tb = handler.build_post_bluesky(make_package(repo_url="https://github.com/x/y"))
        assert "https://github.com/x/y" in tb.build_text()

    def test_no_pypi_or_pkdown_url_in_post(self):
        """pypi_url and pkdown_url must not appear in the rendered post."""
        handler = self._make_handler_with_fake_builder()
        with patch.object(handler, "get_bluesky_did", return_value=None):
            tb = handler.build_post_bluesky(make_package(
                pypi_url="https://pypi.org/project/mylib/",
                pkdown_url="https://pkg.example.com/",
            ))
        text = tb.build_text()
        assert "pypi.org" not in text
        assert "pkg.example.com" not in text

    def test_within_bluesky_character_limit(self):
        handler = self._make_handler_with_fake_builder()
        with patch.object(handler, "get_bluesky_did", return_value=None):
            tb = handler.build_post_bluesky(make_package())
        assert len(tb.build_text()) <= 300

    def test_long_description_does_not_raise(self):
        """A description longer than 300 chars shouldn't raise — tags are dropped instead."""
        handler = self._make_handler_with_fake_builder()
        with patch.object(handler, "get_bluesky_did", return_value=None):
            tb = handler.build_post_bluesky(make_package(description="A" * 400))
        # The builder still returns a FakeTextBuilder instance (no exception)
        assert tb is not None

    def test_skips_did_resolution_when_no_handle(self):
        handler = self._make_handler_with_fake_builder()
        with patch.object(handler, "get_bluesky_did") as mock_did:
            handler.build_post_bluesky(make_package(bluesky=""))
        mock_did.assert_not_called()

    def test_includes_hashtags(self):
        handler = self._make_handler_with_fake_builder({"platform": "bluesky", "client_name": "pyladies_bot"})
        with patch.object(handler, "get_bluesky_did", return_value=None):
            tb = handler.build_post_bluesky(make_package(bluesky=""))
        assert "pyladies" in tb.build_text()


# ---------------------------------------------------------------------------
# promote_package — integration-level
# ---------------------------------------------------------------------------

class TestPromotePackage:
    def test_no_packages_exits_early(self, caplog):
        import logging
        handler = make_handler()
        handler.no_dry_run = True
        packages = []
        with patch.object(handler, "read_metadata_json", return_value=packages), \
             patch.object(handler, "read_counter_name", return_value=""), \
             caplog.at_level(logging.INFO):
            handler.promote_package()
        assert any("nothing to do" in msg.lower() for msg in caplog.messages)

    def test_dry_run_logs_would_promote(self, caplog):
        import logging
        handler = make_handler()
        handler.no_dry_run = False
        with patch.object(handler, "read_metadata_json", return_value=[make_package(name="CiteLang")]), \
             patch.object(handler, "read_counter_name", return_value=""), \
             patch.object(handler, "update_counter"), \
             caplog.at_level(logging.INFO):
            handler.promote_package()
        assert any("[DRY RUN]" in msg for msg in caplog.messages)
