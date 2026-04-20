# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access
# pylint: disable=unused-argument,attribute-defined-outside-init,too-few-public-methods
# pylint: disable=too-many-arguments,import-outside-toplevel
"""
Tests for src/boost_mentions.py

Covers:
- cfg property: raises RuntimeError when config_dict is None
- set_up_config_dict: Mastodon and Bluesky key population, setdefault
  semantics (pre-set values are preserved), unknown/None platform raises
- _boost_mentions_mastodon: reblogged-skip guard, own-account guard,
  live boost (reblog + favourite), dry-run path, exception handling
- _boost_mentions_bluesky: CID-dedup skip, live repost, non-mention skip,
  dry-run path, update_seen gating, exception handling
- boost_mentions: platform routing and logging
"""

import logging
import os
from unittest.mock import MagicMock, call, patch

import pytest

from boost_mentions import BoostMentions


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

BASE_MASTODON_CONFIG = {
    "platform": "mastodon",
    "password": "pw",
    "username": "bot@example.social",
    "client_name": "rladies_bot",
    "api_base_url": "https://botsin.space",
    "mastodon_visibility": "public",
    "access_token": "atoken",
    "client_cred_file": "cred.secret",
    "timeline_depth_limit": 40,
}

BASE_BLUESKY_CONFIG = {
    "platform": "bluesky",
    "password": "pw",
    "username": "bot.bsky.social",
    "client_name": "rladies_bot",
    "api_base_url": "bluesky",
}


def make_handler(config=None, no_dry_run=True):
    """Return a BoostMentions instance pre-loaded with a config dict."""
    return BoostMentions(config_dict=dict(config), no_dry_run=no_dry_run)


def _mastodon_notification(
    *,
    reblogged=False,
    own_account=False,
    bot_acct="bot@example.social",
    username="someone",
    url="https://example.social/@someone/1",
    status_id="123",
):
    """Build a minimal Mastodon notification stub."""
    notif = MagicMock()
    notif.status.reblogged = reblogged
    notif.status.account.acct = bot_acct if own_account else "other@example.social"
    notif.status.url = url
    notif.status.id = status_id
    notif.account.username = username
    return notif


def _bluesky_notification(*, reason="mention", cid="cid-abc", uri="at://uri-abc",
                           is_read=False):
    """Build a minimal Bluesky notification stub."""
    notif = MagicMock()
    notif.reason = reason
    notif.cid = cid
    notif.uri = uri
    notif.is_read = is_read
    return notif


# ---------------------------------------------------------------------------
# cfg property
# ---------------------------------------------------------------------------


class TestCfgProperty:
    def test_raises_when_config_dict_is_none(self):
        # cfg must not silently return None — it guards against uninitialized use
        handler = BoostMentions(config_dict=None)
        with pytest.raises(RuntimeError, match="config_dict is not set"):
            _ = handler.cfg

    def test_returns_dict_when_set(self):
        handler = BoostMentions(config_dict={"key": "value"})
        assert handler.cfg == {"key": "value"}


# ---------------------------------------------------------------------------
# set_up_config_dict
# ---------------------------------------------------------------------------


class TestSetUpConfigDict:
    def test_mastodon_populates_required_keys(self):
        # All Mastodon-specific keys should be seeded from env / config defaults
        env = {
            "PLATFORM": "mastodon",
            "PASSWORD": "secret",
            "USERNAME": "user@social",
            "CLIENT_NAME": "rladies_bot",
            "ACCESS_TOKEN": "tok",
            "BOT_CLIENTCRED_SECRET": "cred.secret",
        }
        handler = BoostMentions(config_dict=None)
        with patch.dict(os.environ, env, clear=True), \
             patch("boost_mentions.config") as mock_cfg:
            mock_cfg.MASTODON_VISIBILITY = "public"
            mock_cfg.API_BASE_URL = "https://botsin.space"
            handler.set_up_config_dict()

        assert handler.config_dict["platform"] == "mastodon"
        assert handler.config_dict["mastodon_visibility"] == "public"
        assert handler.config_dict["api_base_url"] == "https://botsin.space"
        assert handler.config_dict["access_token"] == "tok"
        assert handler.config_dict["client_cred_file"] == "cred.secret"
        assert handler.config_dict["timeline_depth_limit"] == 40
        assert handler.config_dict["max_boosts_per_run"] == 5

    def test_bluesky_populates_api_base_url(self):
        env = {"PLATFORM": "bluesky", "PASSWORD": "pw",
               "USERNAME": "u", "CLIENT_NAME": "bot"}
        handler = BoostMentions(config_dict=None)
        with patch.dict(os.environ, env, clear=True):
            handler.set_up_config_dict()

        assert handler.config_dict["api_base_url"] == "bluesky"

    def test_unknown_platform_raises_value_error(self):
        # A misconfigured / missing PLATFORM must fail loudly, not silently
        # fall through to Bluesky
        env = {"PLATFORM": "twitter"}
        handler = BoostMentions(config_dict=None)
        with patch.dict(os.environ, env, clear=True), \
             pytest.raises(ValueError, match="Unknown platform"):
            handler.set_up_config_dict()

    def test_none_platform_raises_value_error(self):
        # Missing PLATFORM env var must also raise, not default to Bluesky
        handler = BoostMentions(config_dict=None)
        with patch.dict(os.environ, {}, clear=True), \
             pytest.raises(ValueError, match="Unknown platform"):
            handler.set_up_config_dict()

    def test_pre_set_keys_are_not_overwritten(self):
        # setdefault semantics: caller-supplied values must survive
        cfg = {
            "platform": "mastodon",
            "access_token": "pre-existing-token",
            "password": "pw",
            "username": "u",
            "client_name": "bot",
        }
        handler = BoostMentions(config_dict=cfg)
        with patch("boost_mentions.config") as mock_cfg:
            mock_cfg.MASTODON_VISIBILITY = "public"
            mock_cfg.API_BASE_URL = "https://botsin.space"
            handler.set_up_config_dict()

        assert handler.config_dict["access_token"] == "pre-existing-token"

    def test_initialises_empty_dict_when_none(self):
        # Starting from config_dict=None must produce a populated dict, not crash
        env = {"PLATFORM": "bluesky", "PASSWORD": "pw",
               "USERNAME": "u", "CLIENT_NAME": "bot"}
        handler = BoostMentions(config_dict=None)
        with patch.dict(os.environ, env, clear=True):
            handler.set_up_config_dict()

        assert isinstance(handler.config_dict, dict)


# ---------------------------------------------------------------------------
# _boost_mentions_mastodon
# ---------------------------------------------------------------------------


class TestBoostMentionsMastodon:
    def _make(self, no_dry_run=True):
        return make_handler(config=BASE_MASTODON_CONFIG, no_dry_run=no_dry_run)

    def _run(self, handler, notifications, bot_acct="bot@example.social"):
        account = MagicMock()
        account.acct = bot_acct
        client = MagicMock()
        client.notifications.return_value = notifications
        with patch("boost_mentions.login_mastodon", return_value=(account, client)):
            handler._boost_mentions_mastodon()
        return client

    def test_skips_already_reblogged_notification(self):
        # Prevents double-boosting a post the bot has already reblogged
        handler = self._make()
        notif = _mastodon_notification(reblogged=True)
        client = self._run(handler, [notif])
        client.status_reblog.assert_not_called()
        client.status_favourite.assert_not_called()

    def test_skips_own_account_notification(self):
        # Bot should never boost its own toots
        handler = self._make()
        notif = _mastodon_notification(own_account=True, bot_acct="bot@example.social")
        client = self._run(handler, [notif], bot_acct="bot@example.social")
        client.status_reblog.assert_not_called()

    def test_boosts_valid_mention(self):
        # Happy path: unreblogged mention from another account is reblogged + favourited
        handler = self._make()
        notif = _mastodon_notification(reblogged=False, status_id="42")
        client = self._run(handler, [notif])
        client.status_reblog.assert_called_once_with("42")
        client.status_favourite.assert_called_once_with("42")

    def test_dry_run_does_not_call_api(self):
        # In dry-run mode no network calls must be made
        handler = self._make(no_dry_run=False)
        notif = _mastodon_notification(reblogged=False)
        client = self._run(handler, [notif])
        client.status_reblog.assert_not_called()
        client.status_favourite.assert_not_called()

    def test_dry_run_logs_dry_run_message(self, caplog):
        handler = self._make(no_dry_run=False)
        notif = _mastodon_notification(reblogged=False, username="alice")
        with caplog.at_level(logging.INFO, logger="boost_mentions"):
            self._run(handler, [notif])
        assert "[DRY RUN]" in caplog.text

    def test_exception_logged_as_error_and_loop_continues(self, caplog):
        # A failing boost must be logged at ERROR level and must not abort
        # processing of subsequent notifications
        handler = self._make()
        notif_fail = _mastodon_notification(reblogged=False, status_id="1",
                                            username="alice")
        notif_ok = _mastodon_notification(reblogged=False, status_id="2",
                                          username="bob")

        account = MagicMock()
        account.acct = "bot@example.social"
        client = MagicMock()
        client.notifications.return_value = [notif_fail, notif_ok]
        client.status_reblog.side_effect = [Exception("API down"), None]

        with patch("boost_mentions.login_mastodon", return_value=(account, client)), \
             caplog.at_level(logging.ERROR, logger="boost_mentions"):
            handler._boost_mentions_mastodon()

        assert any(r.levelname == "ERROR" for r in caplog.records)
        # Second notification must still have been attempted
        assert client.status_reblog.call_count == 2

    def test_multiple_valid_notifications_all_boosted(self):
        # Every qualifying notification must be boosted, not just the first
        handler = self._make()
        notifications = [
            _mastodon_notification(reblogged=False, status_id="1"),
            _mastodon_notification(reblogged=False, status_id="2"),
        ]
        client = self._run(handler, notifications)
        assert client.status_reblog.call_count == 2
        client.status_reblog.assert_has_calls([call("1"), call("2")])

    def test_empty_notifications_list(self):
        # No notifications must not raise
        handler = self._make()
        client = self._run(handler, [])
        client.status_reblog.assert_not_called()

    def test_flood_limit_caps_boosts(self):
        # At most max_boosts_per_run posts should be boosted in one run
        cfg = dict(BASE_MASTODON_CONFIG)
        cfg["max_boosts_per_run"] = 2
        handler = make_handler(config=cfg)
        notifications = [
            _mastodon_notification(reblogged=False, status_id=str(i))
            for i in range(5)
        ]
        client = self._run(handler, notifications)
        assert client.status_reblog.call_count == 2

    def test_flood_limit_logs_stop_message(self, caplog):
        cfg = dict(BASE_MASTODON_CONFIG)
        cfg["max_boosts_per_run"] = 1
        handler = make_handler(config=cfg)
        notifications = [
            _mastodon_notification(reblogged=False, status_id="1"),
            _mastodon_notification(reblogged=False, status_id="2"),
        ]
        with caplog.at_level(logging.INFO, logger="boost_mentions"):
            self._run(handler, notifications)
        assert "max boosts per run" in caplog.text.lower()


# ---------------------------------------------------------------------------
# _boost_mentions_bluesky
# ---------------------------------------------------------------------------


class TestBoostMentionsBluesky:
    def _make(self, no_dry_run=True):
        return make_handler(config=BASE_BLUESKY_CONFIG, no_dry_run=no_dry_run)

    def _run(self, handler, notifications):
        client = MagicMock()
        client.get_current_time_iso.return_value = "2024-01-01T00:00:00Z"
        client.app.bsky.notification.list_notifications.return_value.notifications = (
            notifications
        )
        with patch("boost_mentions.login_bluesky", return_value=client):
            handler._boost_mentions_bluesky()
        return client

    def test_reposts_unread_mention(self):
        # An unread mention notification should be reposted
        handler = self._make()
        notif = _bluesky_notification(reason="mention", cid="new-cid", is_read=False)
        client = self._run(handler, [notif])
        client.repost.assert_called_once_with(uri=notif.uri, cid="new-cid")

    def test_skips_already_read_mention(self):
        # is_read=True means update_seen already processed this — skip
        handler = self._make()
        notif = _bluesky_notification(reason="mention", cid="old-cid", is_read=True)
        client = self._run(handler, [notif])
        client.repost.assert_not_called()

    def test_skips_non_mention_notifications(self):
        # Only 'mention' notifications should trigger a repost
        handler = self._make()
        like_notif = _bluesky_notification(reason="like", cid="like-cid")
        follow_notif = _bluesky_notification(reason="follow", cid="follow-cid")
        client = self._run(handler, [like_notif, follow_notif])
        client.repost.assert_not_called()

    def test_dry_run_does_not_repost(self):
        handler = self._make(no_dry_run=False)
        notif = _bluesky_notification(reason="mention", cid="new-cid", is_read=False)
        client = self._run(handler, [notif])
        client.repost.assert_not_called()

    def test_dry_run_does_not_call_update_seen(self):
        # update_seen modifies server state and must be skipped in dry-run mode
        handler = self._make(no_dry_run=False)
        notif = _bluesky_notification(reason="mention", cid="new-cid", is_read=False)
        client = self._run(handler, [notif])
        client.app.bsky.notification.update_seen.assert_not_called()

    def test_dry_run_logs_dry_run_message(self, caplog):
        handler = self._make(no_dry_run=False)
        notif = _bluesky_notification(reason="mention", cid="new-cid", is_read=False)
        with caplog.at_level(logging.INFO, logger="boost_mentions"):
            self._run(handler, [notif])
        assert "[DRY RUN]" in caplog.text

    def test_live_run_calls_update_seen(self):
        # update_seen must be called exactly once after processing, with the
        # timestamp captured before processing (to avoid race conditions)
        handler = self._make(no_dry_run=True)
        client = self._run(handler, [])
        client.app.bsky.notification.update_seen.assert_called_once_with(
            {"seen_at": "2024-01-01T00:00:00Z"}
        )

    def test_exception_logged_as_error_and_loop_continues(self, caplog):
        handler = self._make()
        notif_fail = _bluesky_notification(reason="mention", cid="cid-1", is_read=False)
        notif_ok = _bluesky_notification(reason="mention", cid="cid-2", is_read=False)

        client = MagicMock()
        client.get_current_time_iso.return_value = "2024-01-01T00:00:00Z"
        client.app.bsky.notification.list_notifications.return_value.notifications = [
            notif_fail, notif_ok
        ]
        client.repost.side_effect = [Exception("rate limit"), None]

        with patch("boost_mentions.login_bluesky", return_value=client), \
             caplog.at_level(logging.ERROR, logger="boost_mentions"):
            handler._boost_mentions_bluesky()

        assert any(r.levelname == "ERROR" for r in caplog.records)
        assert client.repost.call_count == 2

    def test_empty_notifications_list(self):
        handler = self._make()
        client = self._run(handler, [])
        client.repost.assert_not_called()

    def test_flood_limit_caps_reposts(self):
        # At most max_boosts_per_run posts should be reposted in one run
        cfg = dict(BASE_BLUESKY_CONFIG)
        cfg["max_boosts_per_run"] = 2
        handler = make_handler(config=cfg)
        notifications = [
            _bluesky_notification(reason="mention", cid=f"cid-{i}", is_read=False)
            for i in range(5)
        ]
        client = self._run(handler, notifications)
        assert client.repost.call_count == 2

    def test_flood_limit_logs_stop_message(self, caplog):
        cfg = dict(BASE_BLUESKY_CONFIG)
        cfg["max_boosts_per_run"] = 1
        handler = make_handler(config=cfg)
        notifications = [
            _bluesky_notification(reason="mention", cid="cid-1", is_read=False),
            _bluesky_notification(reason="mention", cid="cid-2", is_read=False),
        ]
        with caplog.at_level(logging.INFO, logger="boost_mentions"):
            self._run(handler, notifications)
        assert "max boosts per run" in caplog.text.lower()


# ---------------------------------------------------------------------------
# boost_mentions (orchestration)
# ---------------------------------------------------------------------------


class TestBoostMentions:
    def test_routes_to_mastodon(self):
        handler = BoostMentions(config_dict=None)
        with patch.object(handler, "set_up_config_dict"), \
             patch.object(handler, "_boost_mentions_mastodon") as mock_mastodon, \
             patch.object(handler, "_boost_mentions_bluesky") as mock_bluesky:
            handler.config_dict = dict(BASE_MASTODON_CONFIG)
            handler.boost_mentions()

        mock_mastodon.assert_called_once()
        mock_bluesky.assert_not_called()

    def test_routes_to_bluesky(self):
        handler = BoostMentions(config_dict=None)
        with patch.object(handler, "set_up_config_dict"), \
             patch.object(handler, "_boost_mentions_mastodon") as mock_mastodon, \
             patch.object(handler, "_boost_mentions_bluesky") as mock_bluesky:
            handler.config_dict = dict(BASE_BLUESKY_CONFIG)
            handler.boost_mentions()

        mock_bluesky.assert_called_once()
        mock_mastodon.assert_not_called()

    def test_logs_client_name_and_url(self, caplog):
        handler = BoostMentions(config_dict=None)
        with patch.object(handler, "set_up_config_dict"), \
             patch.object(handler, "_boost_mentions_bluesky"), \
             caplog.at_level(logging.INFO, logger="boost_mentions"):
            handler.config_dict = dict(BASE_BLUESKY_CONFIG)
            handler.boost_mentions()

        assert "rladies_bot" in caplog.text
        assert "bluesky" in caplog.text

    def test_calls_set_up_config_dict(self):
        handler = BoostMentions(config_dict=None)
        with patch.object(handler, "set_up_config_dict") as mock_setup, \
             patch.object(handler, "_boost_mentions_bluesky"):
            handler.config_dict = dict(BASE_BLUESKY_CONFIG)
            handler.boost_mentions()

        mock_setup.assert_called_once()
