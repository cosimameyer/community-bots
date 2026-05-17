# pylint: disable=missing-class-docstring,missing-function-docstring,import-error
"""
Tests for src/helper/login_bluesky.py

Covers:
- Happy path: correct Client.login args, client returned
- Regression guards: Client() constructed with no args; profile.handle read from login return value
- Login return value: server-confirmed handle used in success log
- Error propagation: Client() and client.login() exceptions bubble up after all retries
- Retry behaviour: succeeds on 2nd/3rd attempt; warning logged per failure; fresh Client per attempt
- Edge cases: missing required config keys raise KeyError; empty-string credentials forwarded
- Logging: login and success messages are emitted with correct content
"""

import logging
from unittest.mock import MagicMock, call, patch

import pytest

from helper.login_bluesky import login_bluesky, BlueskyConfig


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

VALID_CONFIG: BlueskyConfig = {
    "username": "test_bot.bsky.social",
    "password": "hunter2",
}


def _make_mock_client(handle="test_bot.bsky.social"):
    """Return a mock atproto Client whose .login() returns a profile stub."""
    client = MagicMock()
    profile = MagicMock()
    profile.handle = handle
    client.login.return_value = profile
    return client


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_returns_client():
    mock_client = _make_mock_client()
    with patch("helper.login_bluesky.Client", return_value=mock_client):
        result = login_bluesky(VALID_CONFIG)

    assert result is mock_client


def test_login_called_with_correct_args():
    mock_client = _make_mock_client()
    with patch("helper.login_bluesky.Client", return_value=mock_client):
        login_bluesky(VALID_CONFIG)

    mock_client.login.assert_called_once_with(
        "test_bot.bsky.social",
        "hunter2",
    )


def test_client_instantiated_with_no_args():
    # Regression guard: credentials must not be passed to the constructor —
    # only to client.login(). The atproto SDK separates construction from auth.
    with patch("helper.login_bluesky.Client") as mock_cls:
        mock_cls.return_value = _make_mock_client()
        login_bluesky(VALID_CONFIG)

    mock_cls.assert_called_once_with()


# ---------------------------------------------------------------------------
# Login return value — server-confirmed handle
# ---------------------------------------------------------------------------


def test_profile_handle_read_from_login_return_value(caplog):
    # The success log must use profile.handle from the object login() returns,
    # not re-read from config_dict — confirms the server response is consumed.
    mock_client = MagicMock()
    profile = MagicMock()
    profile.handle = "resolved.bsky.social"
    mock_client.login.return_value = profile

    with patch("helper.login_bluesky.Client", return_value=mock_client):
        with caplog.at_level(logging.INFO, logger="helper.login_bluesky"):
            login_bluesky(VALID_CONFIG)

    assert any("resolved.bsky.social" in r.message for r in caplog.records)


def test_success_log_uses_server_confirmed_handle(caplog):
    # The success message must reflect the handle the server returned,
    # not just the input username (handles can resolve to canonical forms).
    mock_client = _make_mock_client(handle="canonical_bot.bsky.social")
    with patch("helper.login_bluesky.Client", return_value=mock_client):
        with caplog.at_level(logging.INFO, logger="helper.login_bluesky"):
            login_bluesky(VALID_CONFIG)

    assert any("canonical_bot.bsky.social" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


def test_client_constructor_exception_propagates():
    with patch("helper.login_bluesky.Client", side_effect=ConnectionError("unreachable")), \
         patch("helper.login_bluesky.time.sleep"):
        with pytest.raises(ConnectionError, match="unreachable"):
            login_bluesky(VALID_CONFIG)


def test_login_exception_propagates():
    mock_client = MagicMock()
    mock_client.login.side_effect = PermissionError("invalid credentials")
    with patch("helper.login_bluesky.Client", return_value=mock_client), \
         patch("helper.login_bluesky.time.sleep"):
        with pytest.raises(PermissionError, match="invalid credentials"):
            login_bluesky(VALID_CONFIG)


# ---------------------------------------------------------------------------
# Retry behaviour
# ---------------------------------------------------------------------------


def test_succeeds_on_second_attempt():
    good_client = _make_mock_client()
    bad_client = MagicMock()
    bad_client.login.side_effect = RuntimeError("transient 403")

    with patch("helper.login_bluesky.Client", side_effect=[bad_client, good_client]), \
         patch("helper.login_bluesky.time.sleep") as mock_sleep:
        result = login_bluesky(VALID_CONFIG)

    assert result is good_client
    mock_sleep.assert_called_once_with(30)


def test_succeeds_on_third_attempt():
    good_client = _make_mock_client()
    bad_client_1 = MagicMock()
    bad_client_1.login.side_effect = RuntimeError("transient 403")
    bad_client_2 = MagicMock()
    bad_client_2.login.side_effect = RuntimeError("transient 403")

    with patch("helper.login_bluesky.Client", side_effect=[bad_client_1, bad_client_2, good_client]), \
         patch("helper.login_bluesky.time.sleep") as mock_sleep:
        result = login_bluesky(VALID_CONFIG)

    assert result is good_client
    mock_sleep.assert_has_calls([call(30), call(60)])


def test_fresh_client_created_on_each_attempt():
    # Each retry must use a new Client() — not reuse a client that failed auth.
    bad = MagicMock()
    bad.login.side_effect = RuntimeError("fail")

    with patch("helper.login_bluesky.Client", side_effect=[bad, bad, bad]) as mock_cls, \
         patch("helper.login_bluesky.time.sleep"):
        with pytest.raises(RuntimeError):
            login_bluesky(VALID_CONFIG)

    assert mock_cls.call_count == 3


def test_warning_logged_per_failed_attempt(caplog):
    bad_client = MagicMock()
    bad_client.login.side_effect = RuntimeError("transient")
    good_client = _make_mock_client()

    with patch("helper.login_bluesky.Client", side_effect=[bad_client, good_client]), \
         patch("helper.login_bluesky.time.sleep"), \
         caplog.at_level(logging.WARNING, logger="helper.login_bluesky"):
        login_bluesky(VALID_CONFIG)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "1/3" in warnings[0].message


# ---------------------------------------------------------------------------
# Missing required config keys / edge cases
# ---------------------------------------------------------------------------


def test_missing_username_raises_key_error():
    bad_config = {"password": "hunter2"}
    with patch("helper.login_bluesky.Client"), \
         patch("helper.login_bluesky.time.sleep"):
        with pytest.raises(KeyError):
            login_bluesky(bad_config)  # type: ignore[arg-type]


def test_missing_password_raises_key_error():
    bad_config = {"username": "test_bot.bsky.social"}
    with patch("helper.login_bluesky.Client"), \
         patch("helper.login_bluesky.time.sleep"):
        with pytest.raises(KeyError):
            login_bluesky(bad_config)  # type: ignore[arg-type]


def test_empty_username_forwarded_to_login():
    # Empty string is a valid (if server-rejected) credential; the function
    # must not filter it locally — delegate to the SDK unchanged.
    config: BlueskyConfig = {"username": "", "password": "hunter2"}
    mock_client = _make_mock_client()
    with patch("helper.login_bluesky.Client", return_value=mock_client):
        login_bluesky(config)

    mock_client.login.assert_called_once_with("", "hunter2")


def test_empty_password_forwarded_to_login():
    config: BlueskyConfig = {"username": "test_bot.bsky.social", "password": ""}
    mock_client = _make_mock_client()
    with patch("helper.login_bluesky.Client", return_value=mock_client):
        login_bluesky(config)

    mock_client.login.assert_called_once_with("test_bot.bsky.social", "")


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_login_info_logged_with_username(caplog):
    mock_client = _make_mock_client()
    with patch("helper.login_bluesky.Client", return_value=mock_client):
        with caplog.at_level(logging.INFO, logger="helper.login_bluesky"):
            login_bluesky(VALID_CONFIG)

    assert any("test_bot.bsky.social" in r.message for r in caplog.records)


def test_exactly_two_log_messages_emitted(caplog):
    mock_client = _make_mock_client()
    with patch("helper.login_bluesky.Client", return_value=mock_client):
        with caplog.at_level(logging.INFO, logger="helper.login_bluesky"):
            login_bluesky(VALID_CONFIG)

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(info_records) == 2


def test_no_success_log_when_login_raises(caplog):
    mock_client = MagicMock()
    mock_client.login.side_effect = RuntimeError("boom")
    with patch("helper.login_bluesky.Client", return_value=mock_client), \
         patch("helper.login_bluesky.time.sleep"):
        with caplog.at_level(logging.INFO, logger="helper.login_bluesky"):
            with pytest.raises(RuntimeError):
                login_bluesky(VALID_CONFIG)

    assert not any("Successfully logged in" in r.message for r in caplog.records)


def test_password_not_in_logs(caplog):
    # Passwords must never appear in log output.
    mock_client = _make_mock_client()
    with patch("helper.login_bluesky.Client", return_value=mock_client):
        with caplog.at_level(logging.DEBUG, logger="helper.login_bluesky"):
            login_bluesky(VALID_CONFIG)

    assert not any("hunter2" in r.message for r in caplog.records)
