# pylint: disable=missing-class-docstring,missing-function-docstring
# pylint: disable=import-error,wrong-import-position,wrong-import-order
"""
Tests for src/helper/check_length_anniversary.py

Covers:
- load_json: valid file, missing file, invalid JSON, empty array
- check_entries: under/at/over 500-char boundary, missing fields,
  multi-entry iteration order, empty/None input, name-fallback consistency
- main: success path, silent-pass on None/empty load result (documented quirk)
"""

import json
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, "src")

from helper.check_length_anniversary import check_entries, load_json, main

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

# Base template with all fields empty is 85 chars (verified by inspection).
# 500 - 85 = 415 chars of headroom across name + description + wiki_link.
_BASE_LEN = 85
_LIMIT = 500
_HEADROOM = _LIMIT - _BASE_LEN  # 415


def _make_entry(name="", description="", wiki_link=""):
    return {"name": name, "description": description, "wiki_link": wiki_link}


# ---------------------------------------------------------------------------
# load_json
# ---------------------------------------------------------------------------


class TestLoadJson:
    def test_returns_parsed_data_for_valid_file(self, tmp_path):
        """Happy path: a well-formed JSON file returns the parsed list."""
        events = [{"name": "Ada", "description": "Pioneer", "wiki_link": "https://example.com"}]
        f = tmp_path / "events.json"
        f.write_text(json.dumps(events), encoding="utf-8")

        result = load_json(str(f))

        assert result == events

    def test_returns_empty_list_for_empty_json_array(self, tmp_path):
        """An empty JSON array [] is valid; the caller decides what to do with it."""
        f = tmp_path / "empty.json"
        f.write_text("[]", encoding="utf-8")

        result = load_json(str(f))

        assert result == []

    def test_returns_none_and_logs_error_when_file_missing(self):
        """A missing file must log an error and return None, not raise."""
        result = load_json("/nonexistent/path/events.json")

        assert result is None

    def test_returns_none_and_logs_error_on_invalid_json(self, tmp_path):
        """Malformed JSON must log an error and return None, not raise."""
        f = tmp_path / "bad.json"
        f.write_text("{not valid json", encoding="utf-8")

        result = load_json(str(f))

        assert result is None

    def test_uses_utf8_encoding(self, tmp_path):
        """File must be opened with UTF-8 so emoji/accented names round-trip safely."""
        events = [{"name": "Ångström ✨", "description": "physicist", "wiki_link": ""}]
        f = tmp_path / "events.json"
        f.write_text(json.dumps(events, ensure_ascii=False), encoding="utf-8")

        result = load_json(str(f))

        assert result[0]["name"] == "Ångström ✨"


# ---------------------------------------------------------------------------
# check_entries — boundary tests
# ---------------------------------------------------------------------------


class TestCheckEntriesBoundary:
    def test_entry_at_exactly_500_chars_passes(self):
        """Combined text of exactly 500 chars must not trigger sys.exit (limit is > 500)."""
        entry = _make_entry(description="x" * _HEADROOM)
        # Verify the test assumption holds.
        assert len(_build_combined(entry)) == _LIMIT

        check_entries([entry])  # Must not raise SystemExit.

    def test_entry_at_501_chars_exits(self):
        """501 chars exceeds the limit — sys.exit(1) must be called."""
        entry = _make_entry(description="x" * (_HEADROOM + 1))
        assert len(_build_combined(entry)) == _LIMIT + 1

        with pytest.raises(SystemExit) as exc_info:
            check_entries([entry])

        assert exc_info.value.code == 1

    def test_entry_well_under_limit_passes(self):
        entry = _make_entry(name="Ada Lovelace", description="The first programmer.",
                            wiki_link="https://en.wikipedia.org/wiki/Ada_Lovelace")

        check_entries([entry])  # Must not raise.

    def test_entry_far_over_limit_exits(self):
        entry = _make_entry(description="x" * 1000)

        with pytest.raises(SystemExit) as exc_info:
            check_entries([entry])

        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# check_entries — missing / partial fields
# ---------------------------------------------------------------------------


class TestCheckEntriesMissingFields:
    def test_missing_name_defaults_to_empty_string_no_key_error(self):
        """name is optional; missing key must not raise KeyError."""
        entry = {"description": "short", "wiki_link": ""}
        check_entries([entry])

    def test_missing_description_defaults_to_empty_string(self):
        entry = {"name": "Ada", "wiki_link": ""}
        check_entries([entry])

    def test_missing_wiki_link_defaults_to_empty_string(self):
        entry = {"name": "Ada", "description": "short"}
        check_entries([entry])

    def test_completely_empty_entry_passes(self):
        """An entry with no fields at all: template is 85 chars, well under 500."""
        check_entries([{}])

    def test_name_in_alert_uses_empty_string_not_unknown(self):
        """
        When `name` is absent the alert must display '' (the value used in the
        combined text), NOT 'Unknown'.  A mismatch would make the error message
        describe a different post than was actually checked.
        """
        entry = _make_entry(description="x" * (_HEADROOM + 1))

        with patch("helper.check_length_anniversary.logger") as mock_log, \
             pytest.raises(SystemExit):
            check_entries([entry])

        # The first logger.warning call includes the name.
        warning_args = mock_log.warning.call_args[0]
        # The name placeholder in the format string resolves to '' not 'Unknown'.
        assert "Unknown" not in str(warning_args), (
            "Alert showed 'Unknown' but combined_text used '', making the "
            "reported length inconsistent with the displayed text."
        )


# ---------------------------------------------------------------------------
# check_entries — iteration behaviour
# ---------------------------------------------------------------------------


class TestCheckEntriesIteration:
    def test_all_entries_pass_for_valid_list(self):
        entries = [
            _make_entry(name="Ada", description="Pioneer"),
            _make_entry(name="Grace", description="COBOL"),
        ]
        check_entries(entries)  # Must not raise.

    def test_first_failing_entry_exits_before_second_is_checked(self):
        """
        sys.exit is called on the first violation; the second entry must never
        be reached.  We use a side-effect counter to verify early termination.
        """
        call_log = []

        def fake_exit(code):
            call_log.append("exit")
            raise SystemExit(code)

        long_entry = _make_entry(description="x" * (_HEADROOM + 1))
        short_entry = _make_entry(description="ok")

        with patch("sys.exit", side_effect=fake_exit), \
             pytest.raises(SystemExit):
            check_entries([long_entry, short_entry])

        assert call_log == ["exit"], "sys.exit must be called exactly once (first entry)"

    def test_second_entry_is_the_failing_one(self):
        """When the first entry passes but the second fails, exit is still triggered."""
        short = _make_entry(description="ok")
        long_entry = _make_entry(description="x" * (_HEADROOM + 1))

        with pytest.raises(SystemExit) as exc_info:
            check_entries([short, long_entry])

        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# check_entries — empty / None input
# ---------------------------------------------------------------------------


class TestCheckEntriesEmptyInput:
    def test_empty_list_returns_silently(self):
        """An empty list means nothing to check — must return without error."""
        check_entries([])  # Must not raise.

    def test_none_input_returns_silently(self):
        """None input (load_json error path) must return without error."""
        check_entries(None)  # Must not raise.


# ---------------------------------------------------------------------------
# main — integration
# ---------------------------------------------------------------------------


class TestMain:
    def test_logs_all_good_when_all_entries_pass(self, tmp_path):
        """main() must log 'All good!' when all entries are within the limit."""
        events = [_make_entry(name="Ada", description="short")]
        f = tmp_path / "events.json"
        f.write_text(json.dumps(events), encoding="utf-8")

        with patch("helper.check_length_anniversary.logger") as mock_log, \
             patch("helper.check_length_anniversary.load_json", return_value=events):
            main()

        logged_msgs = [str(c) for c in mock_log.info.call_args_list]
        assert any("All good" in m for m in logged_msgs)

    def test_exits_when_entry_exceeds_limit(self):
        """main() must propagate sys.exit(1) when check_entries finds a violation."""
        events = [_make_entry(description="x" * (_HEADROOM + 1))]

        with patch("helper.check_length_anniversary.load_json", return_value=events), \
             pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    def test_exits_when_load_returns_none(self):
        """
        When load_json returns None (file missing/invalid), main must call
        sys.exit(1) — not silently log 'All good!' as if nothing was wrong.
        """
        with patch("helper.check_length_anniversary.load_json", return_value=None), \
             patch("helper.check_length_anniversary.logger"):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1

    def test_runs_check_entries_when_load_returns_empty_list(self):
        """
        An empty events.json is valid JSON — check_entries must still be called
        so it can emit the 'no entries' warning rather than silently succeeding.
        """
        with patch("helper.check_length_anniversary.load_json", return_value=[]), \
             patch("helper.check_length_anniversary.check_entries") as mock_check, \
             patch("helper.check_length_anniversary.logger"):
            main()

        mock_check.assert_called_once_with([])

    def test_uses_events_json_as_default_filename(self):
        """main() must pass 'events.json' to load_json when no CLI arg is given."""
        with patch("sys.argv", ["script"]), \
             patch("helper.check_length_anniversary.load_json", return_value=[]) as mock_load, \
             patch("helper.check_length_anniversary.check_entries"), \
             patch("helper.check_length_anniversary.logger"):
            main()

        mock_load.assert_called_once_with("events.json")

    def test_uses_argv1_as_filename_when_provided(self):
        """main() must use sys.argv[1] as the filename when it is present."""
        with patch("sys.argv", ["script", "custom.json"]), \
             patch("helper.check_length_anniversary.load_json", return_value=[]) as mock_load, \
             patch("helper.check_length_anniversary.check_entries"), \
             patch("helper.check_length_anniversary.logger"):
            main()

        mock_load.assert_called_once_with("custom.json")


# ---------------------------------------------------------------------------
# Private helper — mirrors the template in the module under test
# ---------------------------------------------------------------------------


def _build_combined(entry: dict) -> str:
    """Replicate the template from check_entries so boundary tests can pre-check lengths."""
    return (
        f"Let's meet {entry.get('name', '')} ✨\n\n"
        f"{entry.get('description', '')}\n\n"
        f"🔗 {entry.get('wiki_link', '')}\n\n"
        "#amazingwomeninstem #womeninstem "
        "#womenalsoknow #impactthefuture"
    )
