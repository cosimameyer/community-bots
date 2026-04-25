# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access
# pylint: disable=too-few-public-methods
"""
Tests for src/get_rss_data.py
"""

import json
import requests
import pytest
from unittest.mock import MagicMock, patch, mock_open

from get_rss_data import RSSData


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

BASE_CONFIG = {
    "api_base_url": "https://github.example.com/repo",
    "github_raw_url": "https://raw.example.com/repo",
    "json_file": "metadata/test_rss.json",
}


def make_handler(config=None, no_dry_run=False):
    cfg = {**BASE_CONFIG, **(config or {})}
    return RSSData(config_dict=cfg, no_dry_run=no_dry_run)


def make_content(
    rss_feed="https://example.com/feed.xml",
    rss_feed_youtube=None,
    name="Alice",
    mastodon="@alice@fosstodon.org",
    bluesky="@alice.bsky.social",
):
    """Build a minimal parsed-JSON content dict."""
    social = {}
    if mastodon is not None:
        social["mastodon"] = mastodon
    if bluesky is not None:
        social["bluesky"] = bluesky

    content = {}
    if rss_feed is not None:
        content["rss_feed"] = rss_feed
    if rss_feed_youtube is not None:
        content["rss_feed_youtube"] = rss_feed_youtube
    content["authors"] = [{"name": name, "social_media": [social]}]
    return content


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_config_dict_takes_priority_over_env(self, monkeypatch):
        """config_dict provided → attributes come from it regardless of no_dry_run."""
        monkeypatch.setenv("BASE_URL", "https://env-base.example.com")
        for no_dry_run in (True, False):
            handler = make_handler(no_dry_run=no_dry_run)
            assert handler.base_url == BASE_CONFIG["api_base_url"]
            assert handler.github_raw_url == BASE_CONFIG["github_raw_url"]
            assert handler.json_file == BASE_CONFIG["json_file"]

    def test_no_config_dict_reads_from_env(self, monkeypatch):
        """config_dict=None → attributes come from environment variables."""
        monkeypatch.setenv("BASE_URL", "https://env-base.example.com")
        monkeypatch.setenv("GITHUB_RAW_URL", "https://env-raw.example.com")
        monkeypatch.setenv("JSON_FILE", "metadata/env.json")
        handler = RSSData(config_dict=None, no_dry_run=True)
        assert handler.base_url == "https://env-base.example.com"
        assert handler.github_raw_url == "https://env-raw.example.com"
        assert handler.json_file == "metadata/env.json"

    def test_missing_env_vars_are_none(self, monkeypatch):
        """Unset env vars must not raise — attributes become None."""
        monkeypatch.delenv("BASE_URL", raising=False)
        monkeypatch.delenv("GITHUB_RAW_URL", raising=False)
        monkeypatch.delenv("JSON_FILE", raising=False)
        handler = RSSData(config_dict=None, no_dry_run=True)
        assert handler.base_url is None
        assert handler.github_raw_url is None
        assert handler.json_file is None

    def test_none_config_dict_falls_back_to_env(self, monkeypatch):
        """config_dict=None falls back to env vars (None if unset)."""
        monkeypatch.delenv("BASE_URL", raising=False)
        handler = RSSData(config_dict=None, no_dry_run=False)
        assert handler.base_url is None


# ---------------------------------------------------------------------------
# extract_info
# ---------------------------------------------------------------------------

class TestExtractInfo:
    def test_returns_rss_feed_as_single_item_list(self):
        """rss_feed is returned as a one-element list when only rss_feed is set."""
        content = make_content(rss_feed="https://example.com/feed.xml", rss_feed_youtube=None)
        result = RSSData.extract_info(content)
        assert result["rss_feed"] == ["https://example.com/feed.xml"]

    def test_returns_youtube_as_single_item_list_when_rss_feed_absent(self):
        """rss_feed_youtube produces a one-element list when rss_feed is missing."""
        content = make_content(rss_feed=None, rss_feed_youtube="https://yt.example.com/feed")
        result = RSSData.extract_info(content)
        assert result["rss_feed"] == ["https://yt.example.com/feed"]

    def test_both_feeds_included_when_present(self):
        """Both rss_feed and rss_feed_youtube are included when both are set."""
        content = make_content(
            rss_feed="https://example.com/feed.xml",
            rss_feed_youtube="https://yt.example.com/feed",
        )
        result = RSSData.extract_info(content)
        assert result["rss_feed"] == [
            "https://example.com/feed.xml",
            "https://yt.example.com/feed",
        ]

    def test_rss_feed_is_empty_list_when_both_absent(self):
        """rss_feed is an empty list when both feed fields are missing."""
        content = make_content(rss_feed=None, rss_feed_youtube=None)
        result = RSSData.extract_info(content)
        assert result["rss_feed"] == []

    def test_rss_feed_type_is_always_list(self):
        """rss_feed must always be a list."""
        for rss, yt in [
            ("https://example.com/feed.xml", None),
            (None, "https://yt.example.com/feed"),
            ("https://example.com/feed.xml", "https://yt.example.com/feed"),
            (None, None),
        ]:
            content = make_content(rss_feed=rss, rss_feed_youtube=yt)
            result = RSSData.extract_info(content)
            assert isinstance(result["rss_feed"], list), (
                f"Expected list for rss={rss!r}, yt={yt!r}; got {type(result['rss_feed'])}"
            )

    def test_extracts_author_name(self):
        """Author name from the first authors entry is returned."""
        content = make_content(name="Bob")
        assert RSSData.extract_info(content)["name"] == "Bob"

    def test_extracts_mastodon(self):
        """Mastodon handle is extracted from social_media."""
        content = make_content(mastodon="@bob@mastodon.social")
        assert RSSData.extract_info(content)["mastodon"] == "@bob@mastodon.social"

    def test_extracts_bluesky(self):
        """Bluesky handle is extracted from social_media."""
        content = make_content(bluesky="@bob.bsky.social")
        assert RSSData.extract_info(content)["bluesky"] == "@bob.bsky.social"

    def test_missing_authors_key_returns_empty_name(self):
        """Missing authors key must not raise; name defaults to ''."""
        content = {"rss_feed": "https://example.com/feed.xml"}
        result = RSSData.extract_info(content)
        assert result["name"] == ""

    def test_empty_authors_list_returns_empty_name(self):
        """Empty authors list must not raise; name defaults to ''."""
        content = {"rss_feed": "https://example.com/feed.xml", "authors": []}
        # authors falls back to [{}] default so this should not raise
        # but an empty list would cause IndexError — test the guard
        content_with_guard = {"rss_feed": "https://example.com/feed.xml", "authors": [{}]}
        result = RSSData.extract_info(content_with_guard)
        assert result["name"] == ""

    def test_empty_social_media_list_does_not_raise(self):
        """Empty social_media list must not raise IndexError."""
        content = {
            "rss_feed": "https://example.com/feed.xml",
            "authors": [{"name": "Carol", "social_media": []}],
        }
        result = RSSData.extract_info(content)
        assert result["mastodon"] == ""
        assert result["bluesky"] == ""

    def test_missing_social_media_key_returns_empty_handles(self):
        """Missing social_media key must not raise; handles default to ''."""
        content = {
            "rss_feed": "https://example.com/feed.xml",
            "authors": [{"name": "Dave"}],
        }
        result = RSSData.extract_info(content)
        assert result["mastodon"] == ""
        assert result["bluesky"] == ""

    def test_missing_mastodon_in_social_media_defaults_to_empty(self):
        """Missing mastodon key in social_media defaults to ''."""
        content = {
            "authors": [{"name": "Eve", "social_media": [{"bluesky": "@eve.bsky.social"}]}]
        }
        result = RSSData.extract_info(content)
        assert result["mastodon"] == ""
        assert result["bluesky"] == "@eve.bsky.social"

    def test_missing_bluesky_in_social_media_defaults_to_empty(self):
        """Missing bluesky key in social_media defaults to ''."""
        content = {
            "authors": [{"name": "Frank", "social_media": [{"mastodon": "@frank@fosstodon.org"}]}]
        }
        result = RSSData.extract_info(content)
        assert result["mastodon"] == "@frank@fosstodon.org"
        assert result["bluesky"] == ""

    def test_only_first_author_is_used(self):
        """When multiple authors are present, only the first is used."""
        content = {
            "rss_feed": "https://example.com/feed.xml",
            "authors": [
                {"name": "First", "social_media": [{"mastodon": "@first@example.social"}]},
                {"name": "Second", "social_media": [{"mastodon": "@second@example.social"}]},
            ],
        }
        result = RSSData.extract_info(content)
        assert result["name"] == "First"
        assert result["mastodon"] == "@first@example.social"

    def test_completely_empty_content_dict(self):
        """Fully empty dict must not raise; all fields default to ''."""
        result = RSSData.extract_info({})
        assert result == {"name": "", "rss_feed": [], "mastodon": "", "bluesky": ""}

    def test_return_dict_has_expected_keys(self):
        """Returned dict must always have exactly the four expected keys."""
        result = RSSData.extract_info(make_content())
        assert set(result.keys()) == {"name", "rss_feed", "mastodon", "bluesky"}


# ---------------------------------------------------------------------------
# get_meta_data
# ---------------------------------------------------------------------------

class TestGetMetaData:
    def test_empty_list_returns_empty_list(self):
        """Empty input produces empty output without errors."""
        handler = make_handler()
        assert handler.get_meta_data([]) == []

    def test_single_item_is_processed(self):
        """A single content dict is extracted and returned."""
        handler = make_handler()
        content = make_content(name="Grace")
        result = handler.get_meta_data([content])
        assert len(result) == 1
        assert result[0]["name"] == "Grace"

    def test_multiple_items_all_processed(self):
        """All items in the list are extracted."""
        handler = make_handler()
        contents = [make_content(name="Hank"), make_content(name="Ivy")]
        result = handler.get_meta_data(contents)
        assert len(result) == 2
        assert result[0]["name"] == "Hank"
        assert result[1]["name"] == "Ivy"

    def test_empty_content_dict_is_included(self):
        """Even an empty content dict is included (extract_info always returns a dict)."""
        handler = make_handler()
        result = handler.get_meta_data([{}])
        assert len(result) == 1
        assert result[0] == {"name": "", "rss_feed": [], "mastodon": "", "bluesky": ""}


# ---------------------------------------------------------------------------
# get_json_file_names
# ---------------------------------------------------------------------------

def _make_tree_payload(items):
    """Build a minimal GitHub-style tree payload string."""
    return json.dumps(
        {"payload": {"codeViewTreeRoute": {"tree": {"items": items}}}}
    )


def _mock_soup(script_string):
    """
    Return a BeautifulSoup stand-in whose .find("react-app").find("script").string
    equals `script_string`.
    """
    script_tag = MagicMock()
    script_tag.string = script_string
    react_app = MagicMock()
    react_app.find.return_value = script_tag
    soup = MagicMock()
    soup.find.return_value = react_app
    return soup


class TestGetJsonFileNames:
    def _setup_mocks(self, mock_get, mock_bs4, items):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        mock_bs4.return_value = _mock_soup(_make_tree_payload(items))

    @patch("get_rss_data.BeautifulSoup")
    @patch("get_rss_data.requests.get")
    def test_returns_json_urls(self, mock_get, mock_bs4):
        """JSON file paths are converted to full raw GitHub URLs."""
        handler = make_handler()
        self._setup_mocks(mock_get, mock_bs4, [
            {"path": "data/alice.json"},
            {"path": "data/bob.json"},
        ])

        result = handler.get_json_file_names()

        assert result == [
            f"{BASE_CONFIG['github_raw_url']}/alice.json",
            f"{BASE_CONFIG['github_raw_url']}/bob.json",
        ]

    @patch("get_rss_data.BeautifulSoup")
    @patch("get_rss_data.requests.get")
    def test_filters_out_non_json_files(self, mock_get, mock_bs4):
        """Non-JSON files in the tree must be excluded."""
        handler = make_handler()
        self._setup_mocks(mock_get, mock_bs4, [
            {"path": "data/alice.json"},
            {"path": "data/readme.md"},
            {"path": "data/config.yaml"},
        ])

        result = handler.get_json_file_names()

        assert len(result) == 1
        assert result[0].endswith("alice.json")

    @patch("get_rss_data.BeautifulSoup")
    @patch("get_rss_data.requests.get")
    def test_empty_tree_returns_empty_list(self, mock_get, mock_bs4):
        """An empty tree produces an empty list."""
        handler = make_handler()
        self._setup_mocks(mock_get, mock_bs4, [])

        assert handler.get_json_file_names() == []

    @patch("get_rss_data.requests.get")
    def test_http_error_propagates(self, mock_get):
        """An HTTP error from the base URL must propagate (raise_for_status)."""
        handler = make_handler()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        mock_get.return_value = mock_resp

        with pytest.raises(requests.HTTPError):
            handler.get_json_file_names()

    @patch("get_rss_data.BeautifulSoup")
    @patch("get_rss_data.requests.get")
    def test_missing_react_app_raises_attribute_error(self, mock_get, mock_bs4):
        """Missing <react-app> element raises AttributeError."""
        handler = make_handler()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        # soup.find("react-app") returns None → None.find("script") raises AttributeError
        soup = MagicMock()
        soup.find.return_value = None
        mock_bs4.return_value = soup

        with pytest.raises(AttributeError):
            handler.get_json_file_names()

    @patch("get_rss_data.BeautifulSoup")
    @patch("get_rss_data.requests.get")
    def test_all_non_json_files_returns_empty_list(self, mock_get, mock_bs4):
        """If tree has only non-JSON items, result is empty."""
        handler = make_handler()
        self._setup_mocks(mock_get, mock_bs4, [
            {"path": "docs/readme.md"},
            {"path": "images/logo.png"},
        ])

        assert handler.get_json_file_names() == []

    @patch("get_rss_data.BeautifulSoup")
    @patch("get_rss_data.requests.get")
    def test_missing_tree_key_raises_descriptive_runtime_error(self, mock_get, mock_bs4):
        """Regression: missing 'tree' key raises RuntimeError with a diagnostic message."""
        handler = make_handler()
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp
        mock_bs4.return_value = _mock_soup(json.dumps({"payload": {}}))

        with pytest.raises(RuntimeError, match="Update the key path"):
            handler.get_json_file_names()


# ---------------------------------------------------------------------------
# get_json_data
# ---------------------------------------------------------------------------

class TestGetJsonData:
    @patch.object(RSSData, "get_json_file_names", return_value=[])
    def test_no_files_raises_runtime_error(self, _):
        """Empty file list must raise RuntimeError."""
        handler = make_handler()
        with pytest.raises(RuntimeError, match="No JSON files found"):
            handler.get_json_data()

    @patch("get_rss_data.requests.get")
    @patch.object(RSSData, "get_json_file_names")
    def test_fetches_and_parses_all_files(self, mock_names, mock_get):
        """All discovered JSON files are fetched and parsed."""
        handler = make_handler()
        mock_names.return_value = [
            "https://raw.example.com/alice.json",
            "https://raw.example.com/bob.json",
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = [{"name": "Alice"}, {"name": "Bob"}]
        mock_get.return_value = mock_resp

        result = handler.get_json_data()

        assert result == [{"name": "Alice"}, {"name": "Bob"}]
        assert mock_get.call_count == 2

    @patch("get_rss_data.requests.get")
    @patch.object(RSSData, "get_json_file_names")
    def test_failed_file_fetch_is_skipped_with_warning(self, mock_names, mock_get, caplog):
        """A per-file HTTP error is logged and skipped; other files still returned."""
        import logging
        handler = make_handler()
        mock_names.return_value = [
            "https://raw.example.com/bad.json",
            "https://raw.example.com/good.json",
        ]

        bad_resp = MagicMock()
        bad_resp.raise_for_status.side_effect = requests.HTTPError("500")

        good_resp = MagicMock()
        good_resp.raise_for_status = MagicMock()
        good_resp.json.return_value = {"name": "Good"}

        mock_get.side_effect = [bad_resp, good_resp]

        with caplog.at_level(logging.WARNING):
            result = handler.get_json_data()

        assert result == [{"name": "Good"}]
        assert any("bad.json" in msg for msg in caplog.messages)

    @patch("get_rss_data.requests.get")
    @patch.object(RSSData, "get_json_file_names")
    def test_json_decode_error_is_skipped_with_warning(self, mock_names, mock_get, caplog):
        """A JSONDecodeError per file is logged and skipped."""
        import logging
        handler = make_handler()
        mock_names.return_value = ["https://raw.example.com/broken.json"]

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)
        mock_get.return_value = mock_resp

        with caplog.at_level(logging.WARNING):
            result = handler.get_json_data()

        assert result == []
        assert any("broken.json" in msg for msg in caplog.messages)

    @patch("get_rss_data.requests.get")
    @patch.object(RSSData, "get_json_file_names")
    def test_all_files_fail_returns_empty_list(self, mock_names, mock_get):
        """If every file fetch fails, an empty list is returned without raising."""
        handler = make_handler()
        mock_names.return_value = ["https://raw.example.com/a.json"]
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.RequestException("timeout")
        mock_get.return_value = mock_resp

        result = handler.get_json_data()
        assert result == []


# ---------------------------------------------------------------------------
# get_rss_data
# ---------------------------------------------------------------------------

class TestGetRssData:
    @patch.object(RSSData, "get_meta_data")
    @patch.object(RSSData, "get_json_data")
    def test_no_dry_run_writes_json_file(self, mock_json, mock_meta):
        """no_dry_run=True must write the metadata JSON to disk."""
        mock_json.return_value = [make_content()]
        mock_meta.return_value = [{"name": "Alice", "rss_feed": "https://example.com/feed.xml",
                                   "mastodon": "", "bluesky": ""}]

        handler = make_handler(no_dry_run=True)
        handler.json_file = "metadata/test_rss.json"

        m = mock_open()
        with patch("builtins.open", m):
            handler.get_rss_data()

        m.assert_called_once_with("metadata/test_rss.json", "w", encoding="utf-8")
        written = "".join(call.args[0] for call in m().write.call_args_list)
        parsed = json.loads(written)
        assert parsed[0]["name"] == "Alice"

    @patch.object(RSSData, "get_meta_data")
    @patch.object(RSSData, "get_json_data")
    def test_dry_run_does_not_write_file(self, mock_json, mock_meta):
        """no_dry_run=False must not write anything to disk."""
        mock_json.return_value = [make_content()]
        mock_meta.return_value = [{"name": "Alice", "rss_feed": "", "mastodon": "", "bluesky": ""}]

        handler = make_handler(no_dry_run=False)

        with patch("builtins.open", mock_open()) as m:
            handler.get_rss_data()

        m.assert_not_called()

    @patch.object(RSSData, "get_meta_data")
    @patch.object(RSSData, "get_json_data")
    def test_dry_run_logs_would_write_message(self, mock_json, mock_meta, caplog):
        """no_dry_run=False must log a dry-run summary instead of writing."""
        import logging
        mock_json.return_value = [make_content()]
        mock_meta.return_value = [{"name": "Alice", "rss_feed": "", "mastodon": "", "bluesky": ""}]

        handler = make_handler(no_dry_run=False)

        with caplog.at_level(logging.INFO):
            handler.get_rss_data()

        assert any("[DRY RUN]" in msg for msg in caplog.messages)
        assert any("Alice" in msg for msg in caplog.messages)

    @patch.object(RSSData, "get_json_data", side_effect=RuntimeError("No JSON files found."))
    def test_runtime_error_from_get_json_data_propagates(self, _):
        """RuntimeError from get_json_data must propagate to the caller."""
        handler = make_handler()
        with pytest.raises(RuntimeError, match="No JSON files found"):
            handler.get_rss_data()

    @patch.object(RSSData, "get_meta_data")
    @patch.object(RSSData, "get_json_data")
    def test_no_dry_run_logs_success(self, mock_json, mock_meta, caplog):
        """Successful file write must log an INFO message."""
        import logging
        mock_json.return_value = [make_content()]
        mock_meta.return_value = [{"name": "Alice", "rss_feed": "", "mastodon": "", "bluesky": ""}]

        handler = make_handler(no_dry_run=True)
        handler.json_file = "metadata/test_rss.json"

        with patch("builtins.open", mock_open()):
            with caplog.at_level(logging.INFO):
                handler.get_rss_data()

        assert any("test_rss.json" in msg for msg in caplog.messages)
