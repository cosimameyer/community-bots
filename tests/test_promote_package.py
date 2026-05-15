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
    "archive_file": "metadata/test_packages_archive.json",
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
    contributors=None,
    last_updated="",
):
    if contributors is None:
        # PyLadies-style: no directory_id, social handles present
        contributors = [
            {"name": "Vanessa Sochat", "mastodon": "@vsoch@mastodon.social", "bluesky": "vsoch.bsky.social"}
        ]
    return {
        "name": name,
        "description": description,
        "repo_url": repo_url,
        "pypi_url": pypi_url,
        "pkdown_url": pkdown_url,
        "logo_url": logo_url,
        "contributors": contributors,
        "last_updated": last_updated,
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

    def test_does_not_false_positive_on_substring(self):
        """'my-metadata/' contains 'metadata/' as a substring but not as a segment."""
        assert PromotePackage._ensure_metadata_prefix("my-metadata/file.txt") == "metadata/my-metadata/file.txt"


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
# read_archive / write_archive
# ---------------------------------------------------------------------------

class TestArchive:
    def test_read_archive_returns_empty_dict_when_missing(self):
        handler = make_handler()
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert handler.read_archive() == {}

    def test_read_archive_returns_empty_dict_on_invalid_json(self):
        handler = make_handler()
        with patch("builtins.open", mock_open(read_data="not-json")):
            assert handler.read_archive() == {}

    def test_read_archive_returns_parsed_dict(self):
        handler = make_handler()
        data = {"CiteLang": "0.1.2", "artpack": "2023-05-01"}
        with patch("builtins.open", mock_open(read_data=json.dumps(data))):
            assert handler.read_archive() == data

    def test_read_archive_warns_when_archive_file_empty(self, caplog):
        import logging
        handler = make_handler({"archive_file": ""})
        with caplog.at_level(logging.WARNING):
            result = handler.read_archive()
        assert result == {}
        assert any("ARCHIVE_FILE" in msg for msg in caplog.messages)

    def test_write_archive_persists_data(self):
        handler = make_handler()
        m = mock_open()
        archive = {"CiteLang": "0.2.0"}
        with patch("builtins.open", m):
            handler.write_archive(archive)
        m.assert_called_once_with(
            BASE_CONFIG["archive_file"], "w", encoding="utf-8"
        )
        written = "".join(call.args[0] for call in m().write.call_args_list)
        assert "CiteLang" in written

    def test_write_archive_no_op_when_archive_file_empty(self):
        handler = make_handler({"archive_file": ""})
        # Should not raise or call open
        with patch("builtins.open") as mock_file:
            handler.write_archive({"CiteLang": "1.0"})
        mock_file.assert_not_called()


# ---------------------------------------------------------------------------
# get_pypi_version
# ---------------------------------------------------------------------------

class TestGetPypiVersion:
    def test_returns_version_on_success(self):
        handler = make_handler()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"info": {"version": "1.2.3"}}
        with patch("promote_package.requests.get", return_value=mock_resp):
            assert handler.get_pypi_version("https://pypi.org/project/citelang/") == "1.2.3"

    def test_returns_none_on_non_200(self):
        handler = make_handler()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with patch("promote_package.requests.get", return_value=mock_resp):
            assert handler.get_pypi_version("https://pypi.org/project/citelang/") is None

    def test_returns_none_on_request_exception(self):
        import requests as req_lib
        handler = make_handler()
        with patch("promote_package.requests.get", side_effect=req_lib.RequestException("err")):
            assert handler.get_pypi_version("https://pypi.org/project/citelang/") is None

    def test_returns_none_for_empty_pypi_url(self):
        handler = make_handler()
        assert handler.get_pypi_version("") is None

    def test_extracts_name_correctly_from_url_with_version_segment(self):
        """URLs like /project/foo/1.0/ must resolve to 'foo', not '1.0'."""
        handler = make_handler()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"info": {"version": "1.0"}}
        with patch("promote_package.requests.get", return_value=mock_resp) as mock_get:
            handler.get_pypi_version("https://pypi.org/project/mylib/1.0/")
        called_url = mock_get.call_args[0][0]
        assert called_url == "https://pypi.org/pypi/mylib/json"


# ---------------------------------------------------------------------------
# get_current_version
# ---------------------------------------------------------------------------

class TestGetCurrentVersion:
    def test_pyladies_bot_uses_pypi(self):
        handler = make_handler({"client_name": "pyladies_bot"})
        with patch.object(handler, "get_pypi_version", return_value="3.0.1") as mock_pypi:
            result = handler.get_current_version(make_package(pypi_url="https://pypi.org/project/citelang/"))
        mock_pypi.assert_called_once_with("https://pypi.org/project/citelang/")
        assert result == "3.0.1"

    def test_rladies_bot_uses_last_updated(self):
        handler = make_handler({"client_name": "rladies_bot"})
        pkg = make_package(last_updated="2024-03-15")
        assert handler.get_current_version(pkg) == "2024-03-15"

    def test_rladies_bot_returns_none_when_last_updated_empty(self):
        handler = make_handler({"client_name": "rladies_bot"})
        pkg = make_package(last_updated="")
        assert handler.get_current_version(pkg) is None

    def test_unknown_bot_returns_none(self):
        handler = make_handler({"client_name": "unknown_bot"})
        assert handler.get_current_version(make_package()) is None


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
             patch.object(handler, "update_counter"), \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "write_archive"), \
             patch.object(handler, "get_current_version", return_value=None):
            handler.process_packages(packages, "A", client=None)
        # "A" is at index 0, next is index 1 → "B"
        args = mock_send.call_args[0]
        assert args[0]["name"] == "B"

    def test_wraps_around_at_end_of_list(self):
        """Counter on last item → next is the first."""
        handler = make_handler(no_dry_run=True)
        packages = self._make_packages(["X", "Y", "Z"])
        with patch.object(handler, "send_post", return_value="success"), \
             patch.object(handler, "update_counter") as mock_update, \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "write_archive"), \
             patch.object(handler, "get_current_version", return_value=None):
            handler.process_packages(packages, "Z", client=None)
        mock_update.assert_called_once_with("X")

    def test_unknown_counter_starts_from_second_item(self):
        """Counter name not in list → start_index stays 0, next is index 1."""
        handler = make_handler(no_dry_run=True)
        packages = self._make_packages(["P", "Q", "R"])
        with patch.object(handler, "send_post", return_value="success"), \
             patch.object(handler, "update_counter") as mock_update, \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "write_archive"), \
             patch.object(handler, "get_current_version", return_value=None):
            handler.process_packages(packages, "UNKNOWN", client=None)
        mock_update.assert_called_once_with("Q")

    def test_counter_not_updated_on_failed_post(self):
        """Counter must NOT advance when the post fails, so the package is retried next run."""
        handler = make_handler(no_dry_run=True)
        packages = self._make_packages(["A", "B"])
        with patch.object(handler, "send_post", return_value="failed"), \
             patch.object(handler, "update_counter") as mock_update, \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "write_archive"), \
             patch.object(handler, "get_current_version", return_value=None):
            handler.process_packages(packages, "A", client=None)
        mock_update.assert_not_called()

    def test_dry_run_does_not_call_send_post_or_update_counter(self):
        handler = make_handler(no_dry_run=False)
        packages = self._make_packages(["A", "B"])
        with patch.object(handler, "send_post") as mock_send, \
             patch.object(handler, "update_counter") as mock_update, \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "get_current_version", return_value=None):
            handler.process_packages(packages, "A", client=None)
        mock_send.assert_not_called()
        mock_update.assert_not_called()

    def test_skips_when_version_unchanged_promotes_next(self):
        """Next package already promoted at same version → loop finds the one after."""
        handler = make_handler(no_dry_run=True)
        packages = self._make_packages(["A", "B", "C"])
        # B is up-to-date, C is not in archive → should promote C
        archive = {"B": "1.0.0"}

        def _version(pkg):
            return "1.0.0" if pkg["name"] == "B" else None

        with patch.object(handler, "send_post", return_value="success") as mock_send, \
             patch.object(handler, "update_counter") as mock_update, \
             patch.object(handler, "read_archive", return_value=archive), \
             patch.object(handler, "write_archive"), \
             patch.object(handler, "get_current_version", side_effect=_version):
            handler.process_packages(packages, "A", client=None)
        mock_send.assert_called_once()
        assert mock_send.call_args[0][0]["name"] == "C"
        mock_update.assert_called_once_with("C")

    def test_all_packages_skipped_no_post_no_counter_update(self):
        """When every package is already at its current version, nothing is posted
        and the counter is not updated."""
        handler = make_handler(no_dry_run=True)
        packages = self._make_packages(["A", "B", "C"])
        archive = {"A": "1.0.0", "B": "1.0.0", "C": "1.0.0"}
        with patch.object(handler, "send_post") as mock_send, \
             patch.object(handler, "update_counter") as mock_update, \
             patch.object(handler, "read_archive", return_value=archive), \
             patch.object(handler, "write_archive"), \
             patch.object(handler, "get_current_version", return_value="1.0.0"):
            handler.process_packages(packages, "A", client=None)
        mock_send.assert_not_called()
        mock_update.assert_not_called()

    def test_promotes_when_version_updated(self):
        """Package in archive but with a newer version → should promote."""
        handler = make_handler(no_dry_run=True)
        packages = [make_package(name="A"), make_package(name="B")]
        archive = {"B": "1.0.0"}
        with patch.object(handler, "send_post", return_value="success") as mock_send, \
             patch.object(handler, "update_counter"), \
             patch.object(handler, "read_archive", return_value=archive), \
             patch.object(handler, "write_archive"), \
             patch.object(handler, "get_current_version", return_value="1.1.0"):
            handler.process_packages(packages, "A", client=None)
        mock_send.assert_called_once()

    def test_package_without_version_promoted_once_then_skipped(self):
        """A package whose version cannot be determined (None) is promoted the
        first time (not in archive), then skipped on subsequent runs
        (sentinel '' stored in archive)."""
        handler = make_handler(no_dry_run=True)
        packages = [make_package(name="A"), make_package(name="B")]

        # First run: B not in archive → promote
        with patch.object(handler, "send_post", return_value="success") as mock_send, \
             patch.object(handler, "update_counter"), \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "write_archive") as mock_write, \
             patch.object(handler, "get_current_version", return_value=None):
            handler.process_packages(packages, "A", client=None)
        mock_send.assert_called_once()
        written = mock_write.call_args[0][0]
        assert written.get("B") == ""  # sentinel stored

        # Second run: B in archive with sentinel "" → skip, fall through to A
        archive_after = {"B": "", "A": ""}  # both already promoted
        with patch.object(handler, "send_post") as mock_send2, \
             patch.object(handler, "update_counter") as mock_update2, \
             patch.object(handler, "read_archive", return_value=archive_after), \
             patch.object(handler, "write_archive"), \
             patch.object(handler, "get_current_version", return_value=None):
            handler.process_packages(packages, "A", client=None)
        mock_send2.assert_not_called()
        mock_update2.assert_not_called()

    def test_archive_updated_on_successful_post(self):
        """After successful post, archive should be updated with current version."""
        handler = make_handler(no_dry_run=True)
        packages = [make_package(name="A"), make_package(name="B")]
        with patch.object(handler, "send_post", return_value="success"), \
             patch.object(handler, "update_counter"), \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "write_archive") as mock_write, \
             patch.object(handler, "get_current_version", return_value="2.0.0"):
            handler.process_packages(packages, "A", client=None)
        written_archive = mock_write.call_args[0][0]
        assert written_archive.get("B") == "2.0.0"

    def test_archive_stores_empty_sentinel_when_no_version(self):
        """When version is None (not determinable), '' is stored as a sentinel."""
        handler = make_handler(no_dry_run=True)
        packages = [make_package(name="A"), make_package(name="B")]
        with patch.object(handler, "send_post", return_value="success"), \
             patch.object(handler, "update_counter"), \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "write_archive") as mock_write, \
             patch.object(handler, "get_current_version", return_value=None):
            handler.process_packages(packages, "A", client=None)
        written_archive = mock_write.call_args[0][0]
        assert written_archive.get("B") == ""

    def test_archive_not_updated_on_failed_post(self):
        """After failed post, archive should NOT be updated."""
        handler = make_handler(no_dry_run=True)
        packages = [make_package(name="A"), make_package(name="B")]
        with patch.object(handler, "send_post", return_value="failed"), \
             patch.object(handler, "update_counter"), \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "write_archive") as mock_write, \
             patch.object(handler, "get_current_version", return_value="2.0.0"):
            handler.process_packages(packages, "A", client=None)
        mock_write.assert_not_called()

    def test_dry_run_logs_post_text(self, caplog):
        """Dry run should log the actual formatted post content."""
        import logging
        handler = make_handler({"platform": "mastodon"}, no_dry_run=False)
        packages = [make_package(name="A"), make_package(name="B", description="Cool lib.")]
        with patch.object(handler, "update_counter"), \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "get_current_version", return_value=None), \
             caplog.at_level(logging.INFO):
            handler.process_packages(packages, "A", client=None)
        full_log = " ".join(caplog.messages)
        assert "[DRY RUN]" in full_log
        assert "Cool lib." in full_log


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

    def test_includes_contributor_name(self):
        handler = make_handler({"platform": "mastodon", "client_name": "pyladies_bot"})
        post = handler.build_post_mastodon(make_package(
            contributors=[{"name": "Alice", "mastodon": "", "bluesky": ""}]
        ))
        assert "Alice" in post

    def test_includes_mastodon_handle_for_pyladies_community_member(self):
        handler = make_handler({"platform": "mastodon", "client_name": "pyladies_bot"})
        post = handler.build_post_mastodon(make_package(
            contributors=[{"name": "Alice", "mastodon": "@alice@fosstodon.org", "bluesky": ""}]
        ))
        assert "@alice@fosstodon.org" in post

    def test_rladies_bot_links_directory_id_member(self):
        handler = make_handler({"platform": "mastodon", "client_name": "rladies_bot"})
        post = handler.build_post_mastodon(make_package(
            contributors=[
                {"name": "Szymon", "mastodon": "", "bluesky": ""},
                {"name": "Anna", "mastodon": "@anna@fosstodon.org", "bluesky": "", "directory_id": "anna-kozak"},
            ]
        ))
        assert "Szymon" in post
        assert "Anna" in post
        assert "@anna@fosstodon.org" in post

    def test_rladies_bot_does_not_link_contributor_without_directory_id(self):
        handler = make_handler({"platform": "mastodon", "client_name": "rladies_bot"})
        post = handler.build_post_mastodon(make_package(
            contributors=[{"name": "Szymon", "mastodon": "@szymon@fosstodon.org", "bluesky": ""}]
        ))
        assert "Szymon" in post
        assert "@szymon@fosstodon.org" not in post

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

    def test_no_contributors_skips_author_line(self):
        handler = make_handler({"platform": "mastodon", "client_name": "pyladies_bot"})
        post = handler.build_post_mastodon(make_package(contributors=[]))
        assert "👤" not in post

    def test_includes_hashtags(self):
        handler = make_handler({"client_name": "pyladies_bot", "platform": "mastodon"})
        post = handler.build_post_mastodon(make_package())
        assert "#pyladies" in post

    def test_returns_string(self):
        handler = make_handler({"platform": "mastodon"})
        result = handler.build_post_mastodon(make_package())
        assert isinstance(result, str)

    def test_long_description_truncated_to_500_chars(self):
        handler = make_handler({"platform": "mastodon", "client_name": "pyladies_bot"})
        post = handler.build_post_mastodon(make_package(description="X" * 600))
        assert len(post) <= 500

    def test_short_description_not_truncated(self):
        handler = make_handler({"platform": "mastodon", "client_name": "pyladies_bot"})
        desc = "Short description."
        post = handler.build_post_mastodon(make_package(description=desc))
        assert desc in post


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

    def test_long_description_truncated_to_300_graphemes(self):
        """A very long description must be trimmed so the post stays within 300 graphemes."""
        handler = self._make_handler_with_fake_builder()
        with patch.object(handler, "get_bluesky_did", return_value=None):
            tb = handler.build_post_bluesky(make_package(description="A" * 400))
        assert len(tb.build_text()) <= 300

    def test_skips_did_resolution_when_no_bluesky_handle(self):
        handler = self._make_handler_with_fake_builder({"platform": "bluesky", "client_name": "pyladies_bot"})
        with patch.object(handler, "get_bluesky_did") as mock_did:
            handler.build_post_bluesky(make_package(
                contributors=[{"name": "Alice", "mastodon": "", "bluesky": ""}]
            ))
        mock_did.assert_not_called()

    def test_rladies_bot_skips_did_for_contributor_without_directory_id(self):
        """R-Ladies bot must not resolve DID for authors who are not R-Ladies members."""
        handler = self._make_handler_with_fake_builder({"platform": "bluesky", "client_name": "rladies_bot"})
        with patch.object(handler, "get_bluesky_did") as mock_did:
            handler.build_post_bluesky(make_package(
                contributors=[{"name": "Szymon", "mastodon": "", "bluesky": "szymon.bsky.social"}]
            ))
        mock_did.assert_not_called()

    def test_all_contributor_names_appear_in_bluesky_post(self):
        handler = self._make_handler_with_fake_builder({"platform": "bluesky", "client_name": "rladies_bot"})
        with patch.object(handler, "get_bluesky_did", return_value=None):
            tb = handler.build_post_bluesky(make_package(
                contributors=[
                    {"name": "Szymon", "mastodon": "", "bluesky": ""},
                    {"name": "Anna", "mastodon": "", "bluesky": "anna.bsky.social", "directory_id": "anna-kozak"},
                ]
            ))
        text = tb.build_text()
        assert "Szymon" in text
        assert "Anna" in text

    def test_includes_hashtags(self):
        handler = self._make_handler_with_fake_builder({"platform": "bluesky", "client_name": "pyladies_bot"})
        with patch.object(handler, "get_bluesky_did", return_value=None):
            tb = handler.build_post_bluesky(make_package(
                contributors=[{"name": "Alice", "mastodon": "", "bluesky": ""}]
            ))
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
        handler = make_handler({"platform": "mastodon"})
        handler.no_dry_run = False
        with patch.object(handler, "read_metadata_json", return_value=[make_package(name="CiteLang")]), \
             patch.object(handler, "read_counter_name", return_value=""), \
             patch.object(handler, "update_counter"), \
             patch.object(handler, "read_archive", return_value={}), \
             patch.object(handler, "get_current_version", return_value=None), \
             caplog.at_level(logging.INFO):
            handler.promote_package()
        assert any("[DRY RUN]" in msg for msg in caplog.messages)
