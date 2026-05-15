# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access
# pylint: disable=too-few-public-methods
"""
Tests for src/get_packages_data.py
"""

import json
import requests
import pytest
from unittest.mock import MagicMock, patch, mock_open

from get_packages_data import PackagesData


# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

BASE_CONFIG = {
    "base_url": "https://github.example.com/repo/packages",
    "github_raw_url": "https://raw.example.com/repo/packages",
    "json_file": "metadata/test_packages.json",
}


def make_handler(config=None, no_dry_run=False):
    cfg = {**BASE_CONFIG, **(config or {})}
    return PackagesData(config_dict=cfg, no_dry_run=no_dry_run)


def make_pyladies_package(
    name="CiteLang",
    description="Generate credit summaries.",
    repo_url="https://github.com/vsoch/citelang",
    pypi_url="https://pypi.org/project/citelang/",
    logo_url="https://example.com/logo.png",
    maintainers=None,
):
    """Build a minimal PyLadies-style package dict."""
    if maintainers is None:
        maintainers = [
            {
                "name": "Vanessa Sochat",
                "social_media": [{"mastodon": "@vsoch@mastodon.social", "bluesky": "vsoch.bsky.social"}],
            }
        ]
    return {
        "name": name,
        "description": description,
        "repo_url": repo_url,
        "pypi_url": pypi_url,
        "logo_url": logo_url,
        "maintainers": maintainers,
    }


def make_rladies_package(
    name="artpack",
    description="Create generative art data.",
    repo_url="https://github.com/Meghansaha/artpack",
    pkdown_url="https://meghansaha.github.io/artpack/",
    logo_url="https://meghansaha.github.io/artpack/logo.png",
    authors=None,
):
    """Build a minimal RLadies-style package dict."""
    if authors is None:
        authors = [
            {"name": "Meghan Harris", "roles": ["aut", "cre"], "directory_id": "meghan-harris"},
        ]
    return {
        "name": name,
        "description": description,
        "repo_url": repo_url,
        "pkdown_url": pkdown_url,
        "logo_url": logo_url,
        "authors": authors,
    }


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------

class TestInit:
    def test_config_dict_takes_priority_over_env(self, monkeypatch):
        monkeypatch.setenv("BASE_URL", "https://env-base.example.com")
        handler = make_handler()
        assert handler.base_url == BASE_CONFIG["base_url"]
        assert handler.github_raw_url == BASE_CONFIG["github_raw_url"]
        assert handler.json_file == BASE_CONFIG["json_file"]

    def test_no_config_dict_reads_from_env(self, monkeypatch):
        monkeypatch.setenv("BASE_URL", "https://env-base.example.com")
        monkeypatch.setenv("GITHUB_RAW_URL", "https://env-raw.example.com")
        monkeypatch.setenv("JSON_FILE", "metadata/env.json")
        handler = PackagesData(config_dict=None, no_dry_run=True)
        assert handler.base_url == "https://env-base.example.com"
        assert handler.github_raw_url == "https://env-raw.example.com"
        assert handler.json_file == "metadata/env.json"

    def test_missing_env_vars_are_none(self, monkeypatch):
        monkeypatch.delenv("BASE_URL", raising=False)
        monkeypatch.delenv("GITHUB_RAW_URL", raising=False)
        monkeypatch.delenv("JSON_FILE", raising=False)
        handler = PackagesData(config_dict=None, no_dry_run=True)
        assert handler.base_url is None
        assert handler.github_raw_url is None
        assert handler.json_file is None


# ---------------------------------------------------------------------------
# extract_info — PyLadies format (maintainers + pypi_url + social_media)
# ---------------------------------------------------------------------------

class TestExtractInfoPyLadies:
    def test_extracts_package_name(self):
        content = make_pyladies_package(name="mylib")
        assert PackagesData.extract_info(content)["name"] == "mylib"

    def test_extracts_description(self):
        content = make_pyladies_package(description="A great library.")
        assert PackagesData.extract_info(content)["description"] == "A great library."

    def test_extracts_repo_url(self):
        content = make_pyladies_package(repo_url="https://github.com/user/repo")
        assert PackagesData.extract_info(content)["repo_url"] == "https://github.com/user/repo"

    def test_extracts_pypi_url(self):
        content = make_pyladies_package(pypi_url="https://pypi.org/project/mylib/")
        assert PackagesData.extract_info(content)["pypi_url"] == "https://pypi.org/project/mylib/"

    def test_extracts_logo_url(self):
        content = make_pyladies_package(logo_url="https://example.com/logo.png")
        assert PackagesData.extract_info(content)["logo_url"] == "https://example.com/logo.png"

    def test_single_maintainer_extracted(self):
        content = make_pyladies_package()
        contributors = PackagesData.extract_info(content)["contributors"]
        assert len(contributors) == 1
        assert contributors[0]["name"] == "Vanessa Sochat"

    def test_pyladies_contributor_has_no_directory_id(self):
        """PyLadies maintainers carry no directory_id — membership is inferred by the bot."""
        content = make_pyladies_package()
        contributors = PackagesData.extract_info(content)["contributors"]
        assert "directory_id" not in contributors[0]

    def test_extracts_mastodon_handle(self):
        content = make_pyladies_package(
            maintainers=[{"name": "Alice", "social_media": [{"mastodon": "@alice@fosstodon.org"}]}]
        )
        contributors = PackagesData.extract_info(content)["contributors"]
        assert contributors[0]["mastodon"] == "@alice@fosstodon.org"

    def test_extracts_bluesky_handle(self):
        content = make_pyladies_package(
            maintainers=[{"name": "Alice", "social_media": [{"bluesky": "alice.bsky.social"}]}]
        )
        contributors = PackagesData.extract_info(content)["contributors"]
        assert contributors[0]["bluesky"] == "alice.bsky.social"

    def test_multiple_maintainers_all_extracted(self):
        content = make_pyladies_package(
            maintainers=[
                {"name": "Alice", "social_media": [{"mastodon": "@alice@fosstodon.org"}]},
                {"name": "Bob", "social_media": [{"bluesky": "bob.bsky.social"}]},
            ]
        )
        contributors = PackagesData.extract_info(content)["contributors"]
        assert len(contributors) == 2
        assert contributors[0]["name"] == "Alice"
        assert contributors[1]["name"] == "Bob"

    def test_pkdown_url_empty_for_pyladies_package(self):
        content = make_pyladies_package()
        assert PackagesData.extract_info(content)["pkdown_url"] == ""

    def test_docs_url_mapped_to_pkdown_url(self):
        content = make_pyladies_package()
        content["docs_url"] = "https://docs.example.com/"
        assert PackagesData.extract_info(content)["pkdown_url"] == "https://docs.example.com/"

    def test_return_dict_has_expected_keys(self):
        result = PackagesData.extract_info(make_pyladies_package())
        assert set(result.keys()) == {
            "name", "title", "description", "repo_url", "pypi_url",
            "pkdown_url", "bug_reports_url", "logo_url", "last_updated",
            "contributors",
        }


# ---------------------------------------------------------------------------
# extract_info — RLadies format (authors, directory_id marks R-Ladies member)
# ---------------------------------------------------------------------------

class TestExtractInfoRLadies:
    def test_extracts_package_name(self):
        content = make_rladies_package(name="artpack")
        assert PackagesData.extract_info(content)["name"] == "artpack"

    def test_rladies_member_carries_directory_id(self):
        content = make_rladies_package(
            authors=[{"name": "Meghan Harris", "roles": ["aut", "cre"], "directory_id": "meghan-harris"}]
        )
        contributors = PackagesData.extract_info(content)["contributors"]
        assert contributors[0]["directory_id"] == "meghan-harris"

    def test_non_member_author_has_no_directory_id(self):
        content = make_rladies_package(
            authors=[{"name": "Szymon Maksymiuk", "roles": ["aut", "cre"]}]
        )
        contributors = PackagesData.extract_info(content)["contributors"]
        assert len(contributors) == 1
        assert contributors[0]["name"] == "Szymon Maksymiuk"
        assert "directory_id" not in contributors[0]

    def test_all_authors_extracted(self):
        """Every author appears in contributors regardless of directory_id."""
        content = make_rladies_package(
            authors=[
                {"name": "Szymon Maksymiuk", "roles": ["aut", "cre"]},
                {"name": "Anna Kozak", "roles": ["ctb"], "directory_id": "anna-kozak"},
            ]
        )
        contributors = PackagesData.extract_info(content)["contributors"]
        assert len(contributors) == 2
        assert contributors[0]["name"] == "Szymon Maksymiuk"
        assert "directory_id" not in contributors[0]
        assert contributors[1]["name"] == "Anna Kozak"
        assert contributors[1]["directory_id"] == "anna-kozak"

    def test_multiple_rladies_members_all_carry_directory_id(self):
        content = make_rladies_package(
            authors=[
                {"name": "Non Member", "roles": ["aut"]},
                {"name": "Alice", "roles": ["ctb"], "directory_id": "alice"},
                {"name": "Bob", "roles": ["ctb"], "directory_id": "bob"},
            ]
        )
        contributors = PackagesData.extract_info(content)["contributors"]
        assert len(contributors) == 3
        assert "directory_id" not in contributors[0]
        assert contributors[1]["directory_id"] == "alice"
        assert contributors[2]["directory_id"] == "bob"

    def test_rladies_contributors_have_empty_social_handles(self):
        """R-Ladies package JSONs carry no social media — handles are always empty."""
        content = make_rladies_package()
        contributors = PackagesData.extract_info(content)["contributors"]
        assert contributors[0]["mastodon"] == ""
        assert contributors[0]["bluesky"] == ""

    def test_extracts_pkdown_url(self):
        content = make_rladies_package(pkdown_url="https://pkg.example.com/")
        assert PackagesData.extract_info(content)["pkdown_url"] == "https://pkg.example.com/"

    def test_pypi_url_empty_for_rladies_package(self):
        content = make_rladies_package()
        assert PackagesData.extract_info(content)["pypi_url"] == ""

    def test_extracts_last_updated(self):
        content = make_rladies_package()
        content["last_updated"] = "2024-06-01"
        assert PackagesData.extract_info(content)["last_updated"] == "2024-06-01"

    def test_last_updated_empty_when_absent(self):
        content = make_rladies_package()
        assert PackagesData.extract_info(content)["last_updated"] == ""

    def test_extracts_title(self):
        content = make_rladies_package()
        content["title"] = "Art Pack"
        assert PackagesData.extract_info(content)["title"] == "Art Pack"

    def test_extracts_bug_reports_url(self):
        content = make_rladies_package()
        content["bug_reports_url"] = "https://github.com/Meghansaha/artpack/issues"
        assert PackagesData.extract_info(content)["bug_reports_url"] == "https://github.com/Meghansaha/artpack/issues"


# ---------------------------------------------------------------------------
# extract_info — edge cases
# ---------------------------------------------------------------------------

class TestExtractInfoEdgeCases:
    def test_completely_empty_dict_does_not_raise(self):
        result = PackagesData.extract_info({})
        assert result["name"] == ""
        assert result["description"] == ""
        assert result["repo_url"] == ""
        assert result["contributors"] == []

    def test_empty_maintainers_list_gives_no_contributors(self):
        content = {"name": "lib", "maintainers": []}
        assert PackagesData.extract_info(content)["contributors"] == []

    def test_empty_authors_list_gives_no_contributors(self):
        content = {"name": "lib", "authors": []}
        assert PackagesData.extract_info(content)["contributors"] == []

    def test_maintainers_takes_priority_over_authors(self):
        """When both keys exist, maintainers is used."""
        content = {
            "name": "lib",
            "maintainers": [{"name": "MaintainerPerson", "social_media": []}],
            "authors": [{"name": "AuthorPerson", "directory_id": "author-person"}],
        }
        contributors = PackagesData.extract_info(content)["contributors"]
        assert len(contributors) == 1
        assert contributors[0]["name"] == "MaintainerPerson"

    def test_empty_social_media_list_gives_empty_handles(self):
        content = {"name": "lib", "maintainers": [{"name": "Bob", "social_media": []}]}
        contributors = PackagesData.extract_info(content)["contributors"]
        assert contributors[0]["mastodon"] == ""
        assert contributors[0]["bluesky"] == ""

    def test_missing_social_media_key_gives_empty_handles(self):
        content = {"name": "lib", "maintainers": [{"name": "Carol"}]}
        contributors = PackagesData.extract_info(content)["contributors"]
        assert contributors[0]["mastodon"] == ""
        assert contributors[0]["bluesky"] == ""


# ---------------------------------------------------------------------------
# get_meta_data
# ---------------------------------------------------------------------------

class TestGetMetaData:
    def test_empty_list_returns_empty_list(self):
        handler = make_handler()
        assert handler.get_meta_data([]) == []

    def test_single_item_is_processed(self):
        handler = make_handler()
        result = handler.get_meta_data([make_pyladies_package(name="CiteLang")])
        assert len(result) == 1
        assert result[0]["name"] == "CiteLang"

    def test_multiple_items_all_processed(self):
        handler = make_handler()
        contents = [
            make_pyladies_package(name="Lib1"),
            make_rladies_package(name="Lib2"),
        ]
        result = handler.get_meta_data(contents)
        assert len(result) == 2
        assert result[0]["name"] == "Lib1"
        assert result[1]["name"] == "Lib2"

    def test_empty_content_dict_is_included(self):
        handler = make_handler()
        result = handler.get_meta_data([{}])
        assert len(result) == 1
        assert result[0]["name"] == ""


# ---------------------------------------------------------------------------
# get_json_file_names
# ---------------------------------------------------------------------------

def _make_tree_payload(items):
    return json.dumps(
        {"payload": {"codeViewTreeRoute": {"tree": {"items": items}}}}
    )


def _mock_soup(script_string):
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

    @patch("get_packages_data.BeautifulSoup")
    @patch("get_packages_data.requests.get")
    def test_returns_json_urls(self, mock_get, mock_bs4):
        handler = make_handler()
        self._setup_mocks(mock_get, mock_bs4, [
            {"path": "data/packages/citelang.json"},
            {"path": "data/packages/artpack.json"},
        ])
        result = handler.get_json_file_names()
        assert result == [
            f"{BASE_CONFIG['github_raw_url']}/citelang.json",
            f"{BASE_CONFIG['github_raw_url']}/artpack.json",
        ]

    @patch("get_packages_data.BeautifulSoup")
    @patch("get_packages_data.requests.get")
    def test_filters_out_non_json_files(self, mock_get, mock_bs4):
        handler = make_handler()
        self._setup_mocks(mock_get, mock_bs4, [
            {"path": "data/packages/citelang.json"},
            {"path": "data/packages/README.md"},
        ])
        result = handler.get_json_file_names()
        assert len(result) == 1
        assert result[0].endswith("citelang.json")

    @patch("get_packages_data.BeautifulSoup")
    @patch("get_packages_data.requests.get")
    def test_empty_tree_returns_empty_list(self, mock_get, mock_bs4):
        handler = make_handler()
        self._setup_mocks(mock_get, mock_bs4, [])
        assert handler.get_json_file_names() == []

    @patch("get_packages_data.requests.get")
    def test_http_error_propagates(self, mock_get):
        handler = make_handler()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("404")
        mock_get.return_value = mock_resp
        with pytest.raises(requests.HTTPError):
            handler.get_json_file_names()

    @patch("get_packages_data.BeautifulSoup")
    @patch("get_packages_data.requests.get")
    def test_missing_tree_key_raises_descriptive_runtime_error(self, mock_get, mock_bs4):
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
    @patch.object(PackagesData, "get_json_file_names", return_value=[])
    def test_no_files_raises_runtime_error(self, _):
        handler = make_handler()
        with pytest.raises(RuntimeError, match="No JSON files found"):
            handler.get_json_data()

    @patch("get_packages_data.requests.get")
    @patch.object(PackagesData, "get_json_file_names")
    def test_fetches_and_parses_all_files(self, mock_names, mock_get):
        handler = make_handler()
        mock_names.return_value = [
            "https://raw.example.com/citelang.json",
            "https://raw.example.com/artpack.json",
        ]
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.side_effect = [{"name": "CiteLang"}, {"name": "artpack"}]
        mock_get.return_value = mock_resp
        result = handler.get_json_data()
        assert result == [{"name": "CiteLang"}, {"name": "artpack"}]
        assert mock_get.call_count == 2

    @patch("get_packages_data.requests.get")
    @patch.object(PackagesData, "get_json_file_names")
    def test_failed_file_fetch_is_skipped_with_warning(self, mock_names, mock_get, caplog):
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

    @patch("get_packages_data.requests.get")
    @patch.object(PackagesData, "get_json_file_names")
    def test_all_files_fail_returns_empty_list(self, mock_names, mock_get):
        handler = make_handler()
        mock_names.return_value = ["https://raw.example.com/a.json"]
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.RequestException("timeout")
        mock_get.return_value = mock_resp
        result = handler.get_json_data()
        assert result == []


# ---------------------------------------------------------------------------
# get_packages_data
# ---------------------------------------------------------------------------

class TestGetPackagesData:
    @patch.object(PackagesData, "get_meta_data")
    @patch.object(PackagesData, "get_json_data")
    def test_no_dry_run_writes_json_file(self, mock_json, mock_meta):
        mock_json.return_value = [make_pyladies_package()]
        mock_meta.return_value = [{"name": "CiteLang", "description": "..."}]
        handler = make_handler(no_dry_run=True)
        handler.json_file = "metadata/test_packages.json"
        m = mock_open()
        with patch("builtins.open", m):
            handler.get_packages_data()
        m.assert_called_once_with("metadata/test_packages.json", "w", encoding="utf-8")
        written = "".join(call.args[0] for call in m().write.call_args_list)
        parsed = json.loads(written)
        assert parsed[0]["name"] == "CiteLang"

    @patch.object(PackagesData, "get_meta_data")
    @patch.object(PackagesData, "get_json_data")
    def test_dry_run_does_not_write_file(self, mock_json, mock_meta):
        mock_json.return_value = [make_pyladies_package()]
        mock_meta.return_value = [{"name": "CiteLang"}]
        handler = make_handler(no_dry_run=False)
        with patch("builtins.open", mock_open()) as m:
            handler.get_packages_data()
        m.assert_not_called()

    @patch.object(PackagesData, "get_meta_data")
    @patch.object(PackagesData, "get_json_data")
    def test_dry_run_logs_would_write_message(self, mock_json, mock_meta, caplog):
        import logging
        mock_json.return_value = [make_pyladies_package()]
        mock_meta.return_value = [{"name": "CiteLang"}]
        handler = make_handler(no_dry_run=False)
        with caplog.at_level(logging.INFO):
            handler.get_packages_data()
        assert any("[DRY RUN]" in msg for msg in caplog.messages)

    @patch.object(PackagesData, "get_meta_data")
    @patch.object(PackagesData, "get_json_data")
    def test_no_dry_run_logs_success(self, mock_json, mock_meta, caplog):
        import logging
        mock_json.return_value = [make_pyladies_package()]
        mock_meta.return_value = [{"name": "CiteLang"}]
        handler = make_handler(no_dry_run=True)
        handler.json_file = "metadata/test_packages.json"
        with patch("builtins.open", mock_open()):
            with caplog.at_level(logging.INFO):
                handler.get_packages_data()
        assert any("test_packages.json" in msg for msg in caplog.messages)
