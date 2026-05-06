# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access
# pylint: disable=unused-argument,attribute-defined-outside-init,too-few-public-methods
# pylint: disable=too-many-arguments,import-outside-toplevel
"""
Tests for src/boost_tags.py

Covers:
- cfg property: raises RuntimeError when config_dict is None
- set_up_config_dict: Bluesky/Mastodon key population, setdefault semantics
  (pre-set values preserved), TAGS_TO_BOOST parsing, missing/unknown platform errors
- _boost_tags_mastodon: raises NotImplementedError
- _boost_tags_bluesky: repost happy path, dedup via seen_cids, dry-run mode,
  max_boosts_per_run cap, tag normalisation, facet-first extraction, text
  fallback with punctuation stripping, AtProtocolError handling,
  InvokeTimeoutError at login/timeline/search
- boost_tags: platform routing and logging
"""

import logging
import os
from unittest.mock import MagicMock, patch

import pytest

from boost_tags import BoostTags

try:
    from atproto.exceptions import AtProtocolError
    from atproto_client.exceptions import InvokeTimeoutError
except ImportError:  # pragma: no cover
    import boost_tags as _bt
    AtProtocolError = _bt.AtProtocolError  # type: ignore[attr-defined]
    InvokeTimeoutError = _bt.InvokeTimeoutError  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

BASE_BLUESKY_CONFIG = {
    "platform": "bluesky",
    "password": "pw",
    "username": "bot.bsky.social",
    "client_name": "rladies_bot",
    "api_base_url": "https://bsky.social",
    "tags": ["rstats"],
    "max_boosts_per_run": 5,
}

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
    "tags": ["rstats"],
    "max_boosts_per_run": 5,
}


def make_handler(config=None, no_dry_run=True):
    """Return a BoostTags instance pre-loaded with a config dict."""
    return BoostTags(config_dict=dict(config) if config else None, no_dry_run=no_dry_run)


def _bluesky_post(
    *,
    cid="cid-abc",
    uri="at://uri-abc",
    handle="someone.bsky.social",
    text="#rstats great post",
    facets=None,
):
    """Build a minimal Bluesky post stub."""
    post = MagicMock()
    post.cid = cid
    post.uri = uri
    post.author.handle = handle
    post.record.text = text
    post.record.facets = facets
    return post


def _facet_with_tag(tag: str):
    """Build a mock ATProto facet whose single feature carries the given tag."""
    feature = MagicMock(spec=["tag"])
    feature.tag = tag
    facet = MagicMock()
    facet.features = [feature]
    return facet


def _make_bluesky_client(*, seen_cids=None, posts_by_tag=None):
    """
    Build a mock Bluesky client.

    seen_cids    – CIDs already in the timeline (treated as already-seen).
    posts_by_tag – mapping of normalised tag string → list of post stubs.
    """
    seen_cids = seen_cids or []
    posts_by_tag = posts_by_tag or {}

    client = MagicMock()

    feed_items = []
    for cid in seen_cids:
        item = MagicMock()
        item.post.cid = cid
        feed_items.append(item)
    client.get_timeline.return_value.feed = feed_items

    def _search(params):
        tag = params.get("q", "")
        response = MagicMock()
        response.posts = posts_by_tag.get(tag, [])
        return response

    client.app.bsky.feed.search_posts.side_effect = _search
    return client


# ---------------------------------------------------------------------------
# cfg property
# ---------------------------------------------------------------------------


class TestCfgProperty:
    def test_raises_when_config_dict_is_none(self):
        # Accessing cfg before set_up_config_dict must raise, not silently return None
        handler = BoostTags(config_dict=None)
        with pytest.raises(RuntimeError, match="config_dict is not set"):
            _ = handler.cfg

    def test_returns_dict_when_set(self):
        handler = BoostTags(config_dict={"key": "value"})
        assert handler.cfg == {"key": "value"}


# ---------------------------------------------------------------------------
# set_up_config_dict
# ---------------------------------------------------------------------------


class TestSetUpConfigDict:
    def test_missing_platform_raises_value_error(self):
        # A completely absent PLATFORM env var must fail loudly
        handler = BoostTags(config_dict=None)
        with patch.dict(os.environ, {}, clear=True), \
             pytest.raises(ValueError, match="PLATFORM environment variable is not set"):
            handler.set_up_config_dict()

    def test_unknown_platform_raises_value_error(self):
        # An unsupported PLATFORM value must raise rather than silently do nothing
        handler = BoostTags(config_dict=None)
        with patch.dict(os.environ, {"PLATFORM": "twitter"}, clear=True), \
             pytest.raises(ValueError, match="Unknown platform"):
            handler.set_up_config_dict()

    def test_bluesky_populates_api_base_url(self):
        env = {"PLATFORM": "bluesky", "PASSWORD": "pw",
               "USERNAME": "u", "CLIENT_NAME": "bot"}
        handler = BoostTags(config_dict=None)
        with patch.dict(os.environ, env, clear=True):
            handler.set_up_config_dict()

        assert handler.config_dict["api_base_url"] == "https://bsky.social"

    def test_mastodon_populates_required_keys(self):
        env = {
            "PLATFORM": "mastodon",
            "PASSWORD": "secret",
            "USERNAME": "user@social",
            "CLIENT_NAME": "rladies_bot",
            "ACCESS_TOKEN": "tok",
            "BOT_CLIENTCRED_SECRET": "cred.secret",
        }
        handler = BoostTags(config_dict=None)
        with patch.dict(os.environ, env, clear=True), \
             patch("boost_tags.config") as mock_cfg:
            mock_cfg.MASTODON_VISIBILITY = "public"
            mock_cfg.API_BASE_URL = "https://botsin.space"
            handler.set_up_config_dict()

        assert handler.config_dict["mastodon_visibility"] == "public"
        assert handler.config_dict["api_base_url"] == "https://botsin.space"
        assert handler.config_dict["access_token"] == "tok"
        assert handler.config_dict["client_cred_file"] == "cred.secret"
        assert handler.config_dict["timeline_depth_limit"] == 40

    def test_pre_set_keys_are_not_overwritten(self):
        # setdefault semantics: values already in config_dict must survive
        cfg = {
            "platform": "bluesky",
            "api_base_url": "https://custom.endpoint",
            "password": "pw",
            "username": "u",
            "client_name": "bot",
        }
        handler = BoostTags(config_dict=cfg)
        with patch.dict(os.environ, {}, clear=True):
            handler.set_up_config_dict()

        assert handler.config_dict["api_base_url"] == "https://custom.endpoint"

    def test_empty_tags_to_boost_produces_empty_list(self):
        # "".split(",") yields [""]; the filter must drop that blank entry
        env = {"PLATFORM": "bluesky", "TAGS_TO_BOOST": ""}
        handler = BoostTags(config_dict=None)
        with patch.dict(os.environ, env, clear=True):
            handler.set_up_config_dict()

        assert handler.config_dict["tags"] == []

    def test_tags_to_boost_parsed_and_whitespace_stripped(self):
        env = {"PLATFORM": "bluesky", "TAGS_TO_BOOST": " rstats , rladies , python "}
        handler = BoostTags(config_dict=None)
        with patch.dict(os.environ, env, clear=True):
            handler.set_up_config_dict()

        assert handler.config_dict["tags"] == ["rstats", "rladies", "python"]

    def test_max_boosts_per_run_defaults_to_5(self):
        env = {"PLATFORM": "bluesky"}
        handler = BoostTags(config_dict=None)
        with patch.dict(os.environ, env, clear=True):
            handler.set_up_config_dict()

        assert handler.config_dict["max_boosts_per_run"] == 5

    def test_config_dict_none_initialised_to_dict(self):
        # Starting from None must produce a populated dict, not crash
        env = {"PLATFORM": "bluesky", "PASSWORD": "pw",
               "USERNAME": "u", "CLIENT_NAME": "bot"}
        handler = BoostTags(config_dict=None)
        with patch.dict(os.environ, env, clear=True):
            handler.set_up_config_dict()

        assert isinstance(handler.config_dict, dict)

    def test_platform_from_env_is_lowercased(self):
        env = {"PLATFORM": "BLUESKY"}
        handler = BoostTags(config_dict=None)
        with patch.dict(os.environ, env, clear=True):
            handler.set_up_config_dict()

        assert handler.config_dict["platform"] == "bluesky"


# ---------------------------------------------------------------------------
# _boost_tags_mastodon
# ---------------------------------------------------------------------------


class TestBoostTagsMastodon:
    def test_raises_not_implemented_error(self):
        # Mastodon must fail loudly so a misconfigured bot is never silent
        handler = make_handler(config=BASE_MASTODON_CONFIG)
        with pytest.raises(NotImplementedError, match="Mastodon tag boosting"):
            handler._boost_tags_mastodon()


# ---------------------------------------------------------------------------
# _boost_tags_bluesky
# ---------------------------------------------------------------------------


class TestBoostTagsBluesky:
    def _run(self, handler, client):
        with patch("boost_tags.login_bluesky", return_value=client), \
             patch("boost_tags.time.sleep"):
            handler._boost_tags_bluesky()
        return client

    def test_reposts_matching_post(self):
        # Happy path: a post that matches the tag and is not in seen_cids gets reposted
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        post = _bluesky_post(cid="new-cid", text="#rstats great post")
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_called_once_with(uri=post.uri, cid="new-cid")

    def test_skips_own_posts(self):
        # The bot must never repost its own posts
        cfg = {**BASE_BLUESKY_CONFIG, "username": "bot.bsky.social"}
        handler = make_handler(config=cfg)
        post = _bluesky_post(cid="own-cid", text="#rstats", handle="bot.bsky.social")
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_not_called()

    def test_skips_own_posts_case_insensitive(self):
        # Handle comparison must be case-insensitive
        cfg = {**BASE_BLUESKY_CONFIG, "username": "Bot.Bsky.Social"}
        handler = make_handler(config=cfg)
        post = _bluesky_post(cid="own-cid", text="#rstats", handle="bot.bsky.social")
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_not_called()

    def test_skips_post_already_in_seen_cids(self):
        # A post already in the timeline must never be reposted
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        post = _bluesky_post(cid="already-seen", text="#rstats hello")
        client = _make_bluesky_client(
            seen_cids=["already-seen"],
            posts_by_tag={"rstats": [post]},
        )
        self._run(handler, client)
        client.repost.assert_not_called()

    def test_seen_cids_updated_prevents_duplicate_repost(self):
        # The same post appearing under two different tags must only be reposted once
        cfg = {**BASE_BLUESKY_CONFIG, "tags": ["rstats", "rladies"]}
        handler = make_handler(config=cfg)
        post = _bluesky_post(cid="shared-cid", text="#rstats #rladies")
        client = _make_bluesky_client(
            posts_by_tag={"rstats": [post], "rladies": [post]}
        )
        self._run(handler, client)
        assert client.repost.call_count == 1

    def test_dry_run_does_not_call_repost(self):
        handler = make_handler(config=BASE_BLUESKY_CONFIG, no_dry_run=False)
        post = _bluesky_post(cid="cid-1", text="#rstats hello")
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_not_called()

    def test_dry_run_logs_dry_run_message(self, caplog):
        handler = make_handler(config=BASE_BLUESKY_CONFIG, no_dry_run=False)
        post = _bluesky_post(cid="cid-1", text="#rstats hello")
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        with caplog.at_level(logging.INFO, logger="boost_tags"):
            self._run(handler, client)
        assert "[DRY RUN]" in caplog.text

    def test_dry_run_updates_seen_cids_to_prevent_double_log(self):
        # Even in dry-run mode, seen_cids must be updated so the same post is
        # not logged twice when it appears under multiple tags
        cfg = {**BASE_BLUESKY_CONFIG, "tags": ["rstats", "rladies"]}
        handler = make_handler(config=cfg, no_dry_run=False)
        post = _bluesky_post(cid="shared-cid", text="#rstats #rladies")
        client = _make_bluesky_client(
            posts_by_tag={"rstats": [post], "rladies": [post]}
        )
        with patch("boost_tags.login_bluesky", return_value=client), \
             patch("boost_tags.time.sleep") as mock_sleep:
            handler._boost_tags_bluesky()
        # sleep is only called once (one qualifying post, not two)
        assert mock_sleep.call_count == 1

    def test_atprotoerror_logged_as_error_and_loop_continues(self, caplog):
        # A failing repost must be logged at ERROR and must not abort subsequent posts
        cfg = {**BASE_BLUESKY_CONFIG, "tags": ["rstats"]}
        handler = make_handler(config=cfg)
        post_fail = _bluesky_post(cid="cid-1", text="#rstats")
        post_ok   = _bluesky_post(cid="cid-2", text="#rstats")
        client = _make_bluesky_client(posts_by_tag={"rstats": [post_fail, post_ok]})
        client.repost.side_effect = [AtProtocolError("rate limit"), MagicMock()]

        with patch("boost_tags.login_bluesky", return_value=client), \
             patch("boost_tags.time.sleep"), \
             caplog.at_level(logging.ERROR, logger="boost_tags"):
            handler._boost_tags_bluesky()

        assert any(r.levelname == "ERROR" for r in caplog.records)
        assert client.repost.call_count == 2

    def test_max_boosts_per_run_caps_reposts(self):
        cfg = {**BASE_BLUESKY_CONFIG, "max_boosts_per_run": 2}
        handler = make_handler(config=cfg)
        posts = [_bluesky_post(cid=f"cid-{i}", text="#rstats") for i in range(5)]
        client = _make_bluesky_client(posts_by_tag={"rstats": posts})
        self._run(handler, client)
        assert client.repost.call_count == 2

    def test_max_boosts_per_run_respected_across_tags(self):
        # The cap applies globally across all tags, not per-tag
        cfg = {**BASE_BLUESKY_CONFIG, "tags": ["rstats", "rladies"], "max_boosts_per_run": 2}
        handler = make_handler(config=cfg)
        rstats_posts  = [_bluesky_post(cid=f"r-{i}", text="#rstats")  for i in range(3)]
        rladies_posts = [_bluesky_post(cid=f"l-{i}", text="#rladies") for i in range(3)]
        client = _make_bluesky_client(
            posts_by_tag={"rstats": rstats_posts, "rladies": rladies_posts}
        )
        self._run(handler, client)
        assert client.repost.call_count == 2

    def test_max_boosts_logs_stop_message(self, caplog):
        cfg = {**BASE_BLUESKY_CONFIG, "tags": ["rstats", "rladies"], "max_boosts_per_run": 1}
        handler = make_handler(config=cfg)
        posts = [_bluesky_post(cid="cid-1", text="#rstats")]
        client = _make_bluesky_client(posts_by_tag={"rstats": posts})
        with caplog.at_level(logging.INFO, logger="boost_tags"):
            self._run(handler, client)
        assert "max boosts per run" in caplog.text.lower()

    def test_tag_normalised_lowercased_and_hash_stripped(self):
        # Tags like "#RStats" or "  RStats  " must be normalised before matching
        cfg = {**BASE_BLUESKY_CONFIG, "tags": ["#RStats"]}
        handler = make_handler(config=cfg)
        post = _bluesky_post(cid="cid-1", text="#rstats great")
        # The search_posts mock must match the normalised key "rstats"
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_called_once()

    def test_facets_used_for_tag_extraction(self):
        # Structured ATProto facets are the primary source of tags
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        facet = _facet_with_tag("rstats")
        # Text has NO "#rstats" — relies purely on facets
        post = _bluesky_post(cid="cid-1", text="no hashtag here", facets=[facet])
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_called_once()

    def test_falls_back_to_text_when_no_facets(self):
        # When facets is None/empty the code must fall back to text parsing
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        post = _bluesky_post(cid="cid-1", text="#rstats fallback post", facets=None)
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_called_once()

    def test_text_parsing_strips_trailing_punctuation(self):
        # Tags like "#rstats." or "#rstats," (common on social media) must still match
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        post = _bluesky_post(cid="cid-1", text="#rstats. Nice work!", facets=None)
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_called_once()

    def test_post_not_reposted_if_tag_absent_from_post(self):
        # search_posts can return posts that don't actually contain the tag — skip them
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        post = _bluesky_post(cid="cid-1", text="no relevant hashtag here", facets=None)
        client = _make_bluesky_client(posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_not_called()

    def test_empty_tags_list_makes_no_search_calls(self):
        cfg = {**BASE_BLUESKY_CONFIG, "tags": []}
        handler = make_handler(config=cfg)
        client = _make_bluesky_client()
        self._run(handler, client)
        client.app.bsky.feed.search_posts.assert_not_called()

    def test_invoke_timeout_on_login_returns_early(self, caplog):
        # A timeout during login must log an error and return, not raise
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        with patch("boost_tags.login_bluesky", side_effect=InvokeTimeoutError), \
             patch("boost_tags.time.sleep"), \
             caplog.at_level(logging.ERROR, logger="boost_tags"):
            handler._boost_tags_bluesky()
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_invoke_timeout_on_login_makes_no_search_calls(self):
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        client = MagicMock()
        with patch("boost_tags.login_bluesky", side_effect=InvokeTimeoutError), \
             patch("boost_tags.time.sleep"):
            handler._boost_tags_bluesky()
        client.app.bsky.feed.search_posts.assert_not_called()

    def test_invoke_timeout_on_timeline_returns_early(self, caplog):
        # A timeout fetching the timeline must abort without searching any tags
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        client = MagicMock()
        client.get_timeline.side_effect = InvokeTimeoutError
        with patch("boost_tags.login_bluesky", return_value=client), \
             patch("boost_tags.time.sleep"), \
             caplog.at_level(logging.ERROR, logger="boost_tags"):
            handler._boost_tags_bluesky()
        client.app.bsky.feed.search_posts.assert_not_called()
        assert any(r.levelname == "ERROR" for r in caplog.records)

    def test_invoke_timeout_on_search_skips_tag_and_continues(self):
        # A timeout on one tag's search must skip it and continue to the next tag
        cfg = {**BASE_BLUESKY_CONFIG, "tags": ["rstats", "rladies"]}
        handler = make_handler(config=cfg)
        rladies_post = _bluesky_post(cid="cid-rladies", text="#rladies great")

        client = MagicMock()
        client.get_timeline.return_value.feed = []

        def _search(params):
            if params["q"] == "rstats":
                raise InvokeTimeoutError
            response = MagicMock()
            response.posts = [rladies_post]
            return response

        client.app.bsky.feed.search_posts.side_effect = _search

        with patch("boost_tags.login_bluesky", return_value=client), \
             patch("boost_tags.time.sleep"):
            handler._boost_tags_bluesky()

        # "rstats" timed out, "rladies" should still have been reposted
        client.repost.assert_called_once_with(uri=rladies_post.uri, cid="cid-rladies")

    def test_time_sleep_called_between_reposts(self):
        # sleep(0.1) must be called once per qualifying post to avoid hammering the API
        cfg = {**BASE_BLUESKY_CONFIG, "max_boosts_per_run": 10}
        handler = make_handler(config=cfg)
        posts = [_bluesky_post(cid=f"cid-{i}", text="#rstats") for i in range(3)]
        client = _make_bluesky_client(posts_by_tag={"rstats": posts})

        with patch("boost_tags.login_bluesky", return_value=client), \
             patch("boost_tags.time.sleep") as mock_sleep:
            handler._boost_tags_bluesky()

        assert mock_sleep.call_count == 3

    def test_empty_feed_still_processes_tags(self):
        # An empty timeline (no seen_cids) must not crash and must process tags normally
        handler = make_handler(config=BASE_BLUESKY_CONFIG)
        post = _bluesky_post(cid="fresh-cid", text="#rstats")
        client = _make_bluesky_client(seen_cids=[], posts_by_tag={"rstats": [post]})
        self._run(handler, client)
        client.repost.assert_called_once()


# ---------------------------------------------------------------------------
# boost_tags (orchestration)
# ---------------------------------------------------------------------------


class TestBoostTags:
    def test_routes_to_bluesky(self):
        handler = BoostTags(config_dict=None)
        with patch.object(handler, "set_up_config_dict"), \
             patch.object(handler, "_boost_tags_mastodon") as mock_mastodon, \
             patch.object(handler, "_boost_tags_bluesky") as mock_bluesky:
            handler.config_dict = dict(BASE_BLUESKY_CONFIG)
            handler.boost_tags()

        mock_bluesky.assert_called_once()
        mock_mastodon.assert_not_called()

    def test_routes_to_mastodon(self):
        handler = BoostTags(config_dict=None)
        with patch.object(handler, "set_up_config_dict"), \
             patch.object(handler, "_boost_tags_mastodon") as mock_mastodon, \
             patch.object(handler, "_boost_tags_bluesky") as mock_bluesky:
            handler.config_dict = dict(BASE_MASTODON_CONFIG)
            handler.boost_tags()

        mock_mastodon.assert_called_once()
        mock_bluesky.assert_not_called()

    def test_logs_client_name_and_api_base_url(self, caplog):
        handler = BoostTags(config_dict=None)
        with patch.object(handler, "set_up_config_dict"), \
             patch.object(handler, "_boost_tags_bluesky"), \
             caplog.at_level(logging.INFO, logger="boost_tags"):
            handler.config_dict = dict(BASE_BLUESKY_CONFIG)
            handler.boost_tags()

        assert "rladies_bot" in caplog.text
        assert "https://bsky.social" in caplog.text

    def test_calls_set_up_config_dict(self):
        handler = BoostTags(config_dict=None)
        with patch.object(handler, "set_up_config_dict") as mock_setup, \
             patch.object(handler, "_boost_tags_bluesky"):
            handler.config_dict = dict(BASE_BLUESKY_CONFIG)
            handler.boost_tags()

        mock_setup.assert_called_once()
