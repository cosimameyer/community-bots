# pylint: disable=missing-class-docstring,missing-function-docstring,import-error
"""
Tests for src/helper/login_mastodon.py

Covers:
- Happy path: correct Mastodon constructor args, account and client returned
- Regression guards: create_app and log_in are never called
- Error propagation: Mastodon() and client.me() exceptions bubble up
- Edge cases: missing required config keys raise KeyError
- Logging: login and success messages are emitted with correct content
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from helper.login_mastodon import login_mastodon, MastodonConfig


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

VALID_CONFIG: MastodonConfig = {
    "api_base_url": "https://botsin.space",
    "access_token": "test-token-abc",
}


def _make_mock_client(account=None):
    """Return a mock Mastodon client whose .me() returns *account*."""
    client = MagicMock()
    client.me.return_value = account or {"username": "test_bot", "id": 42}
    return client


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_returns_tuple_of_account_and_client():
    # Arrange
    mock_client = _make_mock_client()
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client):
        # Act
        account, client = login_mastodon(VALID_CONFIG)

    # Assert – both elements are the objects we expect
    assert client is mock_client
    assert account == mock_client.me.return_value


def test_mastodon_constructor_called_with_correct_args():
    # Ensure the client is built from access_token + api_base_url, nothing else.
    mock_client = _make_mock_client()
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client) as mock_cls:
        login_mastodon(VALID_CONFIG)

    mock_cls.assert_called_once_with(
        access_token="test-token-abc",
        api_base_url="https://botsin.space",
    )


def test_account_is_result_of_me():
    # Verify the first return value is exactly what client.me() produces.
    sentinel = {"username": "sentinel_bot", "id": 99}
    mock_client = _make_mock_client(account=sentinel)
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client):
        account, _ = login_mastodon(VALID_CONFIG)

    assert account is sentinel


def test_me_called_exactly_once():
    mock_client = _make_mock_client()
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client):
        login_mastodon(VALID_CONFIG)

    mock_client.me.assert_called_once_with()


# ---------------------------------------------------------------------------
# Regression guards – removed behaviour must stay removed
# ---------------------------------------------------------------------------


def test_create_app_is_never_called():
    # create_app registers a new OAuth app on the server; must not be called
    # on every login (was a bug in the original implementation).
    mock_client = _make_mock_client()
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client) as mock_cls:
        login_mastodon(VALID_CONFIG)

    mock_cls.create_app.assert_not_called()


def test_log_in_is_never_called():
    # Password-based log_in is no longer part of the login flow.
    mock_client = _make_mock_client()
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client):
        login_mastodon(VALID_CONFIG)

    mock_client.log_in.assert_not_called()


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------


def test_mastodon_constructor_exception_propagates():
    # If the Mastodon server is unreachable the exception must not be swallowed.
    with patch(
        "helper.login_mastodon.Mastodon",
        side_effect=ConnectionError("unreachable"),
    ):
        with pytest.raises(ConnectionError, match="unreachable"):
            login_mastodon(VALID_CONFIG)


def test_me_exception_propagates():
    # An invalid / expired token causes client.me() to raise; must propagate.
    mock_client = MagicMock()
    mock_client.me.side_effect = PermissionError("unauthorized")
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client):
        with pytest.raises(PermissionError, match="unauthorized"):
            login_mastodon(VALID_CONFIG)


# ---------------------------------------------------------------------------
# Missing required config keys
# ---------------------------------------------------------------------------


def test_missing_access_token_raises_key_error():
    bad_config = {"api_base_url": "https://botsin.space"}
    with patch("helper.login_mastodon.Mastodon"):
        with pytest.raises(KeyError):
            login_mastodon(bad_config)  # type: ignore[arg-type]


def test_missing_api_base_url_raises_key_error():
    bad_config = {"access_token": "test-token-abc"}
    with patch("helper.login_mastodon.Mastodon"):
        with pytest.raises(KeyError):
            login_mastodon(bad_config)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_login_info_logged_with_api_base_url(caplog):
    # The pre-login log line must reference the instance being connected to.
    mock_client = _make_mock_client()
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client):
        with caplog.at_level(logging.INFO, logger="helper.login_mastodon"):
            login_mastodon(VALID_CONFIG)

    assert any("https://botsin.space" in r.message for r in caplog.records)


def test_success_logged_with_username(caplog):
    # After a successful login the username from account["username"] must appear.
    mock_client = _make_mock_client(account={"username": "my_bot", "id": 1})
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client):
        with caplog.at_level(logging.INFO, logger="helper.login_mastodon"):
            login_mastodon(VALID_CONFIG)

    assert any("@my_bot" in r.message for r in caplog.records)


def test_exactly_two_log_messages_emitted(caplog):
    # One pre-login info and one success info — nothing more, nothing less.
    mock_client = _make_mock_client()
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client):
        with caplog.at_level(logging.INFO, logger="helper.login_mastodon"):
            login_mastodon(VALID_CONFIG)

    info_records = [r for r in caplog.records if r.levelno == logging.INFO]
    assert len(info_records) == 2


def test_no_success_log_when_me_raises(caplog):
    # The success message must not be emitted if me() throws.
    mock_client = MagicMock()
    mock_client.me.side_effect = RuntimeError("boom")
    with patch("helper.login_mastodon.Mastodon", return_value=mock_client):
        with caplog.at_level(logging.INFO, logger="helper.login_mastodon"):
            with pytest.raises(RuntimeError):
                login_mastodon(VALID_CONFIG)

    assert not any("Successfully logged in" in r.message for r in caplog.records)
