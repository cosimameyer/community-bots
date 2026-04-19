# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access
# pylint: disable=unused-argument,attribute-defined-outside-init,too-few-public-methods
"""
Tests for src/promote_anniversaries.py

Covers:
- Date matching logic
- Text-building helpers (whitespace padding, DID resolution)
- Post construction for Mastodon (plain string) and Bluesky (TextBuilder facets)
- Platform routing in send_post
- Mastodon and Bluesky sender methods, including the fixed bugs
- Configuration loading from environment variables
- Main entry-point flow: dry run, live run, None-client guard
"""

import json
import os
from datetime import datetime
from unittest.mock import MagicMock, mock_open, patch

import runpy

import pytest

import promote_anniversaries as pa
from promote_anniversaries import PromoteAnniversary


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

BASE_CONFIG_MASTODON = {
    "platform": "mastodon",
    "images": "test_images",
    "password": "pw",
    "username": "user@example.social",
    "client_name": "rladies_bot",
    "api_base_url": "https://botsin.space",
    "mastodon_visibility": "public",
    "client_id": "cid",
    "client_secret": "csecret",
    "access_token": "atoken",
    "client_cred_file": "cred.secret",
}

BASE_CONFIG_BLUESKY = {
    "platform": "bluesky",
    "images": "test_images",
    "password": "pw",
    "username": "user.bsky.social",
    "client_name": "rladies_bot",
    "api_base_url": "https://bsky.social",
}


def make_handler(platform="mastodon", config=None, no_dry_run=False):
    """Return a PromoteAnniversary handler with sensible defaults for unit tests."""
    base = BASE_CONFIG_MASTODON if platform == "mastodon" else BASE_CONFIG_BLUESKY
    cfg = {**base, **(config or {})}
    return PromoteAnniversary(config_dict=cfg, no_dry_run=no_dry_run)


# Canonical test event — all fields present.
SAMPLE_EVENT = {
    "date": "08-30",
    "name": "Ada Lovelace",
    "description_mastodon": "The first programmer.",
    "description_bluesky": "The first programmer.",
    "wiki_link": "https://en.wikipedia.org/wiki/Ada_Lovelace",
    "img": "ada-lovelace.png",
    "alt": "Illustration of Ada Lovelace",
}

# Event without image — tests optional-image paths.
SAMPLE_EVENT_NO_IMG = {k: v for k, v in SAMPLE_EVENT.items() if k not in ("img", "alt")}

# Event with a Bluesky handle — exercises the @mention facet path.
SAMPLE_EVENT_BLUESKY_HANDLE = {**SAMPLE_EVENT, "bluesky": "@ada.bsky.social"}

# Event with inline hashtags in the Bluesky description — tests facet splitting.
SAMPLE_EVENT_INLINE_TAGS = {
    **SAMPLE_EVENT,
    "description_bluesky": "Pioneer of #computing and #algorithms.",
}


# ---------------------------------------------------------------------------
# cfg property
# ---------------------------------------------------------------------------

class TestCfgProperty:
    def test_raises_runtime_error_when_config_dict_is_none(self):
        """Accessing cfg without config_dict should raise a descriptive RuntimeError
        rather than an AttributeError, so callers get actionable feedback."""
        handler = PromoteAnniversary(config_dict=None)
        with pytest.raises(RuntimeError, match="config_dict is not set"):
            _ = handler.cfg

    def test_returns_config_dict_when_set(self):
        """cfg must be a transparent proxy — same object, no copy."""
        handler = make_handler()
        assert handler.cfg is handler.config_dict


# ---------------------------------------------------------------------------
# is_matching_current_date
# ---------------------------------------------------------------------------

class TestIsMatchingCurrentDate:
    def test_matches_todays_date(self):
        """A date string equal to today's MM-DD must return True."""
        today = datetime.now().strftime("%m-%d")
        assert PromoteAnniversary.is_matching_current_date(today) is True

    def test_does_not_match_a_different_date(self):
        """A date that is not today must return False."""
        today = datetime.now().strftime("%m-%d")
        other = "01-01" if today != "01-01" else "01-02"
        assert PromoteAnniversary.is_matching_current_date(other) is False

    def test_custom_format_is_respected(self):
        """A custom date_format argument must be used for both parsing and comparison."""
        today_reversed = datetime.now().strftime("%d-%m")
        assert PromoteAnniversary.is_matching_current_date(
            today_reversed, date_format="%d-%m"
        ) is True

    def test_empty_string_does_not_match(self):
        """An empty string can never equal today's date."""
        assert PromoteAnniversary.is_matching_current_date("") is False

    def test_full_iso_date_does_not_match_default_mm_dd_format(self):
        """A YYYY-MM-DD string is the wrong format for the default %m-%d comparison."""
        today_iso = datetime.now().strftime("%Y-%m-%d")
        assert PromoteAnniversary.is_matching_current_date(today_iso) is False


# ---------------------------------------------------------------------------
# add_whitespace_if_needed
# ---------------------------------------------------------------------------

class TestAddWhitespaceIfNeeded:
    def test_regular_text_gets_trailing_space(self):
        """Normal text chunks need a space appended so the next token is separated."""
        assert PromoteAnniversary.add_whitespace_if_needed("hello") == "hello "

    def test_text_ending_with_open_paren_is_unchanged(self):
        """No space is appended after '(' — content follows without a gap."""
        assert PromoteAnniversary.add_whitespace_if_needed("see (") == "see ("

    def test_text_ending_with_open_brace_is_unchanged(self):
        assert PromoteAnniversary.add_whitespace_if_needed("data{") == "data{"

    def test_text_ending_with_open_bracket_is_unchanged(self):
        assert PromoteAnniversary.add_whitespace_if_needed("list[") == "list["

    def test_empty_string_gets_space(self):
        """Even an empty chunk gets a space — consistent with all non-bracket endings."""
        assert PromoteAnniversary.add_whitespace_if_needed("") == " "


# ---------------------------------------------------------------------------
# get_bluesky_did
# ---------------------------------------------------------------------------

class TestGetBlueskyDid:
    def test_returns_did_on_successful_200_response(self):
        """A 200 response with a 'did' key must return the DID string."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"did": "did:plc:abc123"}

        with patch("promote_anniversaries.requests.get", return_value=mock_response):
            result = PromoteAnniversary.get_bluesky_did("ada.bsky.social")

        assert result == "did:plc:abc123"

    def test_returns_none_on_non_200_status(self):
        """A non-200 response means the handle could not be resolved."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("promote_anniversaries.requests.get", return_value=mock_response):
            result = PromoteAnniversary.get_bluesky_did("unknown.bsky.social")

        assert result is None

    def test_returns_none_on_network_exception(self):
        """A network error must be swallowed and return None, not crash the caller."""
        with patch("promote_anniversaries.requests") as mock_req:
            mock_req.RequestException = Exception
            mock_req.get.side_effect = Exception("connection refused")
            result = PromoteAnniversary.get_bluesky_did("ada.bsky.social")

        assert result is None

    def test_strips_leading_at_symbol_before_api_call(self):
        """Handles stored as '@user.bsky.social' must have '@' stripped in the URL."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"did": "did:plc:abc123"}

        with patch("promote_anniversaries.requests.get", return_value=mock_response) as mock_get:
            PromoteAnniversary.get_bluesky_did("@ada.bsky.social")

        url_called = mock_get.call_args[0][0]
        assert "@" not in url_called
        assert "ada.bsky.social" in url_called


# ---------------------------------------------------------------------------
# download_image
# ---------------------------------------------------------------------------

class TestDownloadImage:
    def test_skips_http_request_when_file_already_cached(self, tmp_path):
        """If the image file is on disk, no HTTP request should be made."""
        handler = make_handler(config={"images": str(tmp_path)})
        (tmp_path / "ada.png").touch()

        with patch("promote_anniversaries.requests.get") as mock_get:
            result = handler.download_image("https://example.com/ada.png")

        mock_get.assert_not_called()
        assert result == str(tmp_path / "ada.png")

    def test_downloads_and_streams_to_disk_when_file_missing(self, tmp_path):
        """A missing file must trigger an HTTP GET that streams content to disk."""
        handler = make_handler(config={"images": str(tmp_path)})

        with patch("promote_anniversaries.requests.get"), \
             patch("promote_anniversaries.shutil.copyfileobj") as mock_copy:
            result = handler.download_image("https://example.com/ada.png")

        mock_copy.assert_called_once()
        assert result == str(tmp_path / "ada.png")

    def test_returns_correct_local_path_for_deep_url(self, tmp_path):
        """The basename of the URL path is used as the local filename."""
        handler = make_handler(config={"images": str(tmp_path)})

        with patch("promote_anniversaries.requests.get"), \
             patch("promote_anniversaries.shutil.copyfileobj"):
            result = handler.download_image(
                "https://raw.githubusercontent.com/org/repo/main/images/ada-lovelace.png"
            )

        assert result == str(tmp_path / "ada-lovelace.png")


# ---------------------------------------------------------------------------
# build_post — Mastodon
# ---------------------------------------------------------------------------

class TestBuildPostMastodon:
    def test_returns_plain_string(self):
        """Mastodon posts must be plain strings, not TextBuilder objects."""
        handler = make_handler(platform="mastodon")
        assert isinstance(handler.build_post(SAMPLE_EVENT), str)

    def test_contains_event_name(self):
        handler = make_handler(platform="mastodon")
        assert "Ada Lovelace" in handler.build_post(SAMPLE_EVENT)

    def test_contains_mastodon_description(self):
        handler = make_handler(platform="mastodon")
        assert "The first programmer." in handler.build_post(SAMPLE_EVENT)

    def test_contains_wiki_link(self):
        handler = make_handler(platform="mastodon")
        assert "https://en.wikipedia.org/wiki/Ada_Lovelace" in handler.build_post(SAMPLE_EVENT)

    def test_appends_all_three_shared_hashtags(self):
        """All campaign hashtags must appear in the Mastodon post as raw text."""
        handler = make_handler(platform="mastodon")
        result = handler.build_post(SAMPLE_EVENT)
        assert "#amazingwomenintech" in result
        assert "#womenalsoknow" in result
        assert "#impactthefuture" in result


# ---------------------------------------------------------------------------
# build_post — Bluesky
# ---------------------------------------------------------------------------

class TestBuildPostBluesky:
    def test_returns_textbuilder_instance(self):
        """Bluesky posts must return a TextBuilder, not a plain string."""
        handler = make_handler(platform="bluesky")
        tb = MagicMock()
        with patch("promote_anniversaries.client_utils.TextBuilder", return_value=tb):
            result = handler.build_post(SAMPLE_EVENT)
        assert result is tb

    def test_uses_mention_facet_when_bluesky_handle_present(self):
        """When the event has a Bluesky handle, the opener must use a @mention facet."""
        handler = make_handler(platform="bluesky")
        tb = MagicMock()
        did = "did:plc:abc123"

        with patch("promote_anniversaries.client_utils.TextBuilder", return_value=tb), \
             patch.object(handler, "get_bluesky_did", return_value=did):
            handler.build_post(SAMPLE_EVENT_BLUESKY_HANDLE)

        tb.mention.assert_called_once_with(SAMPLE_EVENT_BLUESKY_HANDLE["bluesky"], did)

    def test_uses_plain_text_when_no_bluesky_handle(self):
        """Without a Bluesky handle the name is emitted as plain text — no mention facet."""
        handler = make_handler(platform="bluesky")
        tb = MagicMock()

        with patch("promote_anniversaries.client_utils.TextBuilder", return_value=tb):
            handler.build_post(SAMPLE_EVENT)

        tb.mention.assert_not_called()
        text_calls = [str(c) for c in tb.text.call_args_list]
        assert any("Ada Lovelace" in c for c in text_calls)

    def test_last_shared_tag_has_no_trailing_space(self):
        """
        The final footer tag must NOT end with a space.
        A trailing space on the last tag creates a rendering artifact in Bluesky posts.
        """
        handler = make_handler(platform="bluesky")
        tb = MagicMock()

        with patch("promote_anniversaries.client_utils.TextBuilder", return_value=tb):
            # SAMPLE_EVENT has no inline hashtags, so tag() is called only for footer tags.
            handler.build_post(SAMPLE_EVENT)

        tag_calls = tb.tag.call_args_list
        assert len(tag_calls) == 3, "Expected exactly 3 shared footer tag calls"
        last_display = tag_calls[-1][0][0]
        assert not last_display.endswith(" "), (
            f"Last tag display text '{last_display}' must not end with a space"
        )

    def test_non_last_shared_tags_have_trailing_space(self):
        """Tags before the last one need a trailing space to visually separate them."""
        handler = make_handler(platform="bluesky")
        tb = MagicMock()

        with patch("promote_anniversaries.client_utils.TextBuilder", return_value=tb):
            handler.build_post(SAMPLE_EVENT)

        tag_calls = tb.tag.call_args_list
        for c in tag_calls[:-1]:
            display = c[0][0]
            assert display.endswith(" "), (
                f"Non-last tag '{display}' should end with a space"
            )

    def test_inline_description_hashtags_become_tag_facets(self):
        """Hashtags inside description_bluesky must be emitted as .tag() facets."""
        handler = make_handler(platform="bluesky")
        tb = MagicMock()

        with patch("promote_anniversaries.client_utils.TextBuilder", return_value=tb):
            handler.build_post(SAMPLE_EVENT_INLINE_TAGS)

        tag_names = [c[0][1] for c in tb.tag.call_args_list]
        assert "computing" in tag_names
        assert "algorithms" in tag_names

    def test_raises_value_error_for_unsupported_platform(self):
        """An unknown platform must raise ValueError — silent failure would mean lost posts."""
        handler = make_handler(config={"platform": "twitter"})
        with pytest.raises(ValueError, match="Unsupported platform"):
            handler.build_post(SAMPLE_EVENT)


# ---------------------------------------------------------------------------
# send_post — routing
# ---------------------------------------------------------------------------

class TestSendPost:
    def test_routes_mastodon_to_mastodon_sender(self):
        handler = make_handler(platform="mastodon")
        client = MagicMock()

        with patch.object(handler, "build_post", return_value="post text"), \
             patch.object(handler, "send_post_to_mastodon") as mock_sender:
            handler.send_post(SAMPLE_EVENT, client)

        mock_sender.assert_called_once_with(SAMPLE_EVENT, client, "post text")

    def test_bluesky_with_img_builds_embed_and_routes_to_bluesky_sender(self):
        """When 'img' is present the embed must be built and forwarded."""
        handler = make_handler(platform="bluesky")
        client = MagicMock()
        embed = MagicMock()

        with patch.object(handler, "build_post", return_value=MagicMock()), \
             patch.object(handler, "build_embed_external", return_value=embed) as mock_embed, \
             patch.object(handler, "send_post_to_bluesky") as mock_sender:
            handler.send_post(SAMPLE_EVENT, client)

        mock_embed.assert_called_once_with(SAMPLE_EVENT, client)
        embed_arg = mock_sender.call_args[0][3]
        assert embed_arg is embed

    def test_bluesky_without_img_skips_build_embed_external(self):
        """
        Critical fix: when 'img' is absent, build_embed_external must NOT be called.
        It accesses event['img'] directly and would raise KeyError.
        embed_external must be None in this case.
        """
        handler = make_handler(platform="bluesky")
        client = MagicMock()

        with patch.object(handler, "build_post", return_value=MagicMock()), \
             patch.object(handler, "build_embed_external") as mock_embed, \
             patch.object(handler, "send_post_to_bluesky") as mock_sender:
            handler.send_post(SAMPLE_EVENT_NO_IMG, client)

        mock_embed.assert_not_called()
        embed_arg = mock_sender.call_args[0][3]
        assert embed_arg is None


# ---------------------------------------------------------------------------
# send_post_to_mastodon
# ---------------------------------------------------------------------------

class TestSendPostToMastodon:
    def test_uploads_media_and_posts_with_image(self):
        """When 'img' is present the file is uploaded and attached to the status."""
        handler = make_handler(platform="mastodon")
        client = MagicMock()
        media = MagicMock()
        client.media_post.return_value = media

        with patch.object(handler, "download_image", return_value="/tmp/ada.png"):
            handler.send_post_to_mastodon(SAMPLE_EVENT, client, "post text")

        client.media_post.assert_called_once_with("/tmp/ada.png")
        client.status_post.assert_called_once_with("post text", media_ids=[media])

    def test_media_ids_is_always_a_list(self):
        """
        Critical fix: Mastodon.py's status_post requires media_ids to be a list.
        Passing a bare media dict causes the API call to silently fail or raise.
        """
        handler = make_handler(platform="mastodon")
        client = MagicMock()
        client.media_post.return_value = MagicMock()

        with patch.object(handler, "download_image", return_value="/tmp/ada.png"):
            handler.send_post_to_mastodon(SAMPLE_EVENT, client, "post text")

        _, kwargs = client.status_post.call_args
        assert isinstance(kwargs["media_ids"], list), (
            "media_ids must be a list, not a bare media dict"
        )

    def test_falls_back_to_text_only_on_media_upload_failure(self):
        """A failed media upload must not kill the post — fall back to text-only."""
        handler = make_handler(platform="mastodon")
        client = MagicMock()
        client.media_post.side_effect = Exception("S3 error")

        with patch.object(handler, "download_image", return_value="/tmp/ada.png"):
            handler.send_post_to_mastodon(SAMPLE_EVENT, client, "post text")

        client.status_post.assert_called_once_with("post text")

    def test_posts_text_only_when_no_img_in_event(self):
        """If the event has no 'img', skip media entirely and post plain text."""
        handler = make_handler(platform="mastodon")
        client = MagicMock()

        handler.send_post_to_mastodon(SAMPLE_EVENT_NO_IMG, client, "post text")

        client.media_post.assert_not_called()
        client.status_post.assert_called_once_with("post text")


# ---------------------------------------------------------------------------
# send_post_to_bluesky
# ---------------------------------------------------------------------------

class TestSendPostToBluesky:
    def test_calls_client_send_post_with_text_and_embed(self):
        handler = make_handler(platform="bluesky")
        client = MagicMock()
        post_txt = MagicMock()
        post_txt.build_text.return_value = "preview"
        embed = MagicMock()

        handler.send_post_to_bluesky(SAMPLE_EVENT, client, post_txt, embed)

        client.send_post.assert_called_once_with(text=post_txt, embed=embed)

    def test_uses_public_build_api_for_preview_logging(self):
        """
        Critical fix: preview must use post_txt.build_text(), not the private _buffer.
        _buffer is an atproto internal subject to change without notice.
        """
        handler = make_handler(platform="bluesky")
        client = MagicMock()
        post_txt = MagicMock()
        post_txt.build_text.return_value = "preview text"

        handler.send_post_to_bluesky(SAMPLE_EVENT, client, post_txt, None)

        post_txt.build_text.assert_called()

    def test_handles_send_exception_without_raising(self):
        """A failed send must be logged, not re-raised, so one bad post can't crash the run."""
        handler = make_handler(platform="bluesky")
        client = MagicMock()
        client.send_post.side_effect = Exception("network error")
        post_txt = MagicMock()
        post_txt.build_text.return_value = "preview"

        # Must complete without raising.
        handler.send_post_to_bluesky(SAMPLE_EVENT, client, post_txt, None)


# ---------------------------------------------------------------------------
# build_embed_external
# ---------------------------------------------------------------------------

class TestBuildEmbedExternal:
    def test_downloads_image_from_correct_url_and_uploads_blob(self):
        """The embed builder must derive the URL from base_path + event['img']
        and upload the raw bytes as a Bluesky blob."""
        handler = make_handler(platform="bluesky")
        client = MagicMock()
        img_bytes = b"fake image bytes"

        with patch.object(handler, "download_image", return_value="/tmp/ada.png") as mock_dl, \
             patch("builtins.open", mock_open(read_data=img_bytes)):
            handler.build_embed_external(SAMPLE_EVENT, client)

        expected_url = f"{handler.base_path}/{SAMPLE_EVENT['img']}"
        mock_dl.assert_called_once_with(expected_url)
        client.upload_blob.assert_called_once_with(img_bytes)

    def test_embed_external_title_identifies_the_person(self):
        """The External embed title must be 'Image of <name>'."""
        handler = make_handler(platform="bluesky")
        client = MagicMock()

        with patch.object(handler, "download_image", return_value="/tmp/ada.png"), \
             patch("builtins.open", mock_open(read_data=b"img")), \
             patch("promote_anniversaries.models") as mock_models:
            handler.build_embed_external(SAMPLE_EVENT, client)

        external_kwargs = mock_models.AppBskyEmbedExternal.External.call_args.kwargs
        assert external_kwargs["title"] == f"Image of {SAMPLE_EVENT['name']}"
        assert external_kwargs["description"] == SAMPLE_EVENT["alt"]


# ---------------------------------------------------------------------------
# _setup_config_from_env
# ---------------------------------------------------------------------------

class TestSetupConfigFromEnv:
    @patch.dict(os.environ, {
        "PLATFORM": "mastodon",
        "IMAGES": "images/",
        "PASSWORD": "pw",
        "USERNAME": "user",
        "CLIENT_NAME": "rladies_bot",
        "CLIENT_ID": "cid",
        "CLIENT_SECRET": "csec",
        "ACCESS_TOKEN": "atoken",
        "BOT_CLIENTCRED_SECRET": "cred",
    })
    def test_mastodon_api_base_url_comes_from_config_module(self):
        """Mastodon's api_base_url must come from config.API_BASE_URL (the instance URL)."""
        import config as cfg_module
        handler = PromoteAnniversary(config_dict=None, no_dry_run=True)
        handler._setup_config_from_env()
        assert handler.config_dict["api_base_url"] == cfg_module.API_BASE_URL

    @patch.dict(os.environ, {
        "PLATFORM": "bluesky",
        "IMAGES": "images/",
        "PASSWORD": "pw",
        "USERNAME": "user",
        "CLIENT_NAME": "rladies_bot",
    })
    def test_bluesky_api_base_url_is_https_bsky_social(self):
        """
        Critical fix: Bluesky's api_base_url must be 'https://bsky.social', not
        the literal string 'bluesky'. The field name implies a real URL and it
        appears verbatim in log output.
        """
        handler = PromoteAnniversary(config_dict=None, no_dry_run=True)
        handler._setup_config_from_env()
        assert handler.config_dict["api_base_url"] == "https://bsky.social"

    @patch.dict(os.environ, {
        "PLATFORM": "bluesky",
        "IMAGES": "images/",
        "PASSWORD": "pw",
        "USERNAME": "user",
        "CLIENT_NAME": "rladies_bot",
    })
    def test_bluesky_config_does_not_include_mastodon_keys(self):
        """Mastodon-specific keys (access_token, client_secret) must not appear
        in a Bluesky config — they would indicate a leaked or incorrect config."""
        handler = PromoteAnniversary(config_dict=None, no_dry_run=True)
        handler._setup_config_from_env()
        assert "access_token" not in handler.config_dict
        assert "client_secret" not in handler.config_dict


# ---------------------------------------------------------------------------
# promote_anniversary — main entry point
# ---------------------------------------------------------------------------

class TestPromoteAnniversary:
    def _today_event(self):
        return {**SAMPLE_EVENT, "date": datetime.now().strftime("%m-%d")}

    def _off_day_event(self):
        today = datetime.now().strftime("%m-%d")
        other = "01-01" if today != "01-01" else "01-02"
        return {**SAMPLE_EVENT, "date": other}

    def test_dry_run_without_config_dict_completes_without_error(self):
        """
        Critical fix: dry run mode (no_dry_run=False) must work even when
        config_dict is None. Previously the None guard fired for both live
        and dry runs, making dry run completely non-functional without config.
        """
        handler = PromoteAnniversary(config_dict=None, no_dry_run=False)
        events = [self._today_event()]

        with patch("builtins.open"), patch("json.load", return_value=events):
            # Must complete without raising or logging an error.
            handler.promote_anniversary()

    def test_dry_run_never_calls_send_post(self):
        """In dry run mode, matching events must be logged but never sent."""
        handler = PromoteAnniversary(config_dict=None, no_dry_run=False)
        events = [self._today_event()]

        with patch("builtins.open"), \
             patch("json.load", return_value=events), \
             patch.object(handler, "send_post") as mock_send:
            handler.promote_anniversary()

        mock_send.assert_not_called()

    def test_live_run_calls_send_post_for_matching_event(self):
        """In live run mode a matching event must trigger send_post exactly once."""
        handler = make_handler(platform="mastodon", no_dry_run=True)
        client = MagicMock()
        event = self._today_event()

        with patch.object(handler, "_connect_client", return_value=client), \
             patch("builtins.open"), \
             patch("json.load", return_value=[event]), \
             patch.object(handler, "send_post") as mock_send:
            handler.promote_anniversary()

        mock_send.assert_called_once_with(event, client)

    def test_non_matching_date_skips_send_post(self):
        """An event whose date does not match today must not be posted."""
        handler = make_handler(platform="mastodon", no_dry_run=True)
        client = MagicMock()
        event = self._off_day_event()

        with patch.object(handler, "_connect_client", return_value=client), \
             patch("builtins.open"), \
             patch("json.load", return_value=[event]), \
             patch.object(handler, "send_post") as mock_send:
            handler.promote_anniversary()

        mock_send.assert_not_called()

    def test_none_client_aborts_before_send_post(self):
        """
        Critical fix: if _connect_client() returns None (unsupported platform),
        the run must abort immediately — no event should be sent.
        Previously, None was passed into send_post causing an AttributeError.
        """
        handler = make_handler(platform="bluesky", no_dry_run=True)

        with patch.object(handler, "_connect_client", return_value=None), \
             patch.object(handler, "send_post") as mock_send:
            handler.promote_anniversary()

        mock_send.assert_not_called()

    def test_only_todays_event_is_sent_from_a_mixed_list(self):
        """Multiple events in events.json — only the date-matching one must be posted."""
        handler = make_handler(platform="mastodon", no_dry_run=True)
        client = MagicMock()
        today_event = self._today_event()
        off_event = self._off_day_event()

        with patch.object(handler, "_connect_client", return_value=client), \
             patch("builtins.open"), \
             patch("json.load", return_value=[off_event, today_event, off_event]), \
             patch.object(handler, "send_post") as mock_send:
            handler.promote_anniversary()

        mock_send.assert_called_once_with(today_event, client)

    def test_live_run_with_no_config_calls_setup_from_env(self):
        """When config_dict=None and no_dry_run=True, _setup_config_from_env must
        be called so the bot can load credentials from the environment."""
        handler = PromoteAnniversary(config_dict=None, no_dry_run=True)

        with patch.object(handler, "_setup_config_from_env") as mock_setup:
            # After the no-op mock, config_dict is still None → hits the safety-net
            # error return (lines 73-74) before any further work.
            handler.promote_anniversary()

        mock_setup.assert_called_once()

    def test_live_run_logs_error_and_aborts_when_config_still_none_after_env_setup(self):
        """If _setup_config_from_env somehow leaves config_dict as None (safety-net),
        the method must log an error and return without touching events.json."""
        handler = PromoteAnniversary(config_dict=None, no_dry_run=True)

        with patch.object(handler, "_setup_config_from_env"), \
             patch.object(handler, "send_post") as mock_send:
            handler.promote_anniversary()

        mock_send.assert_not_called()


# ---------------------------------------------------------------------------
# _connect_client
# ---------------------------------------------------------------------------

class TestConnectClient:
    def test_mastodon_calls_login_mastodon_and_returns_client(self):
        """_connect_client must delegate to login_mastodon and return its client."""
        handler = make_handler(platform="mastodon", no_dry_run=True)
        mock_client = MagicMock()

        with patch("promote_anniversaries.login_mastodon", return_value=(MagicMock(), mock_client)):
            result = handler._connect_client()

        assert result is mock_client

    def test_bluesky_calls_login_bluesky_and_returns_client(self):
        """_connect_client must delegate to login_bluesky and return the client directly."""
        handler = make_handler(platform="bluesky", no_dry_run=True)
        mock_client = MagicMock()

        with patch("promote_anniversaries.login_bluesky", return_value=mock_client):
            result = handler._connect_client()

        assert result is mock_client

    def test_unsupported_platform_logs_error_and_returns_none(self):
        """An unrecognised platform must log an error and return None — not raise."""
        handler = make_handler(config={"platform": "twitter"}, no_dry_run=True)
        result = handler._connect_client()
        assert result is None


# ---------------------------------------------------------------------------
# send_post_to_mastodon — text-only fallback also fails
# ---------------------------------------------------------------------------

class TestSendPostToMastodonFallbackFailure:
    def test_text_only_post_exception_is_logged_without_raising(self):
        """If the text-only fallback status_post also raises, the exception must be
        caught and logged — it must never propagate to the caller."""
        handler = make_handler(platform="mastodon")
        client = MagicMock()
        # No 'img' → goes straight to text-only path, which then also fails.
        client.status_post.side_effect = Exception("API down")

        # Must complete without raising.
        handler.send_post_to_mastodon(SAMPLE_EVENT_NO_IMG, client, "post text")


# ---------------------------------------------------------------------------
# __main__ block
# ---------------------------------------------------------------------------

class TestMain:
    def test_main_block_runs_in_dry_run_mode_without_error(self):
        """Running the module as __main__ must complete without error.
        __main__ uses no_dry_run=True, so _setup_config_from_env runs for real.
        runpy re-executes the module in a fresh namespace, so class-level
        patches don't survive — instead we patch at the boundary level:
        - os.environ supplies valid values so client_name is never None
        - helper.login_bluesky.Client is mocked (that cached module survives
          runpy) so no real Bluesky connection is attempted
        - builtins.open and json.load are patched so events.json need not exist
        """
        mock_bsky_client = MagicMock()
        mock_bsky_client.login.return_value = MagicMock(handle="test_bot")
        with (
            patch.dict(os.environ, {
                "CLIENT_NAME": "test_bot",
                "PLATFORM": "bluesky",
                "IMAGES": "test_images",
                "PASSWORD": "pw",
                "USERNAME": "user",
            }),
            patch("helper.login_bluesky.Client", return_value=mock_bsky_client),
            patch("builtins.open"),
            patch("json.load", return_value=[]),
        ):
            runpy.run_module("promote_anniversaries", run_name="__main__")
        # Reaching here without exception is the assertion.
