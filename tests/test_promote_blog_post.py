# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access
# pylint: disable=unused-argument,attribute-defined-outside-init,too-few-public-methods
"""
Tests for src/promote_blog_post.py
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from promote_blog_post import PromoteBlogPost


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

class FeedEntry:
    """
    Minimal feedparser entry stub.
    Supports both attribute access (entry.title) and
    membership tests ('category' in entry) — matching feedparser's behaviour.
    """
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    def __contains__(self, item):
        return item in self.__dict__


BASE_CONFIG = {
    "platform": "bluesky",
    "archive": "test_archive",
    "images": "test_images",
    "counter": "metadata/test_counter.txt",
    "json_file": "metadata/test_meta.json",
    "client_name": "pyladies_bot",
    "api_base_url": "bluesky",
    "gen_ai_support": False,
    "password": "pw",
    "username": "user",
    "mastodon": None,
}


def make_handler(config=None, no_dry_run=False):
    """Return a PromoteBlogPost with sensible defaults for unit tests."""
    cfg = {**BASE_CONFIG, **(config or {})}
    return PromoteBlogPost(config_dict=cfg, no_dry_run=no_dry_run)


def make_entry(
    title="Test Post",
    link="https://example.com/post1",
    published="Mon, 01 Jan 2024 12:00:00 +0000",
    tags=None,
    summary="<p>Summary text</p>",
):
    """Build a minimal RSS entry stub that mirrors a feedparser entry."""
    return FeedEntry(
        title=title,
        link=link,
        published=published,
        tags=[FeedEntry(term=t) for t in (tags or [])],
        summary=summary,
    )


def make_feed_config(entries, archived_links=None):
    """Build a feed_config dict as _process_feed receives it."""
    return {
        "rss_feed_archive": {"link": list(archived_links or [])},
        "number_of_entries_feed": len(entries),
        "feed": {"name": "Test Author", "ARCHIVE": ["/tmp/test_archive/example.com"]},
        "d": entries,
    }


# ---------------------------------------------------------------------------
# _ensure_metadata_prefix
# ---------------------------------------------------------------------------

class TestEnsureMetadataPrefix:
    def test_adds_prefix_when_absent(self):
        assert PromoteBlogPost._ensure_metadata_prefix("counter.txt") == "metadata/counter.txt"

    def test_leaves_existing_prefix_intact(self):
        result = PromoteBlogPost._ensure_metadata_prefix("metadata/counter.txt")
        assert result == "metadata/counter.txt"

    def test_empty_string_gets_prefix(self):
        # Edge: empty string should still receive the prefix
        assert PromoteBlogPost._ensure_metadata_prefix("") == "metadata/"

    def test_custom_prefix_not_matched(self):
        # "data/counter.txt" does NOT start with "metadata/" so prefix is added
        result = PromoteBlogPost._ensure_metadata_prefix("data/counter.txt")
        assert result == "metadata/data/counter.txt"


# ---------------------------------------------------------------------------
# parse_pub_date
# ---------------------------------------------------------------------------

class TestParsePubDate:
    def setup_method(self):
        self.handler = make_handler()

    def _make_entry(self, pub_date_str):
        return {"pub_date": pub_date_str}

    def test_rfc2822_with_offset(self):
        entry = self._make_entry("Mon, 01 Jan 2024 12:00:00 +0000")
        result = self.handler.parse_pub_date(entry)
        assert result == datetime(2024, 1, 1, 12, 0, 0)

    def test_rfc2822_with_timezone_name(self):
        entry = self._make_entry("Mon, 01 Jan 2024 12:00:00 GMT")
        result = self.handler.parse_pub_date(entry)
        assert result == datetime(2024, 1, 1, 12, 0, 0)

    def test_iso_date_format(self):
        entry = self._make_entry("2024-06-15")
        result = self.handler.parse_pub_date(entry)
        assert result == datetime(2024, 6, 15)

    def test_fallback_to_today_on_unknown_format(self):
        entry = self._make_entry("not-a-valid-date")
        before = datetime.now()
        result = self.handler.parse_pub_date(entry)
        after = datetime.now()
        # Fallback should be approximately now
        assert before <= result <= after

    def test_missing_pub_date_key_falls_back(self):
        entry = {}  # no pub_date key
        result = self.handler.parse_pub_date(entry)
        assert isinstance(result, datetime)


# ---------------------------------------------------------------------------
# define_tags
# ---------------------------------------------------------------------------

class TestDefineTags:
    def _entry(self, pub_date_str, tags=None):
        return {
            "pub_date": pub_date_str,
            "tags": tags or [],
        }

    def test_pyladies_bot_base_tags(self):
        handler = make_handler({"client_name": "pyladies_bot"})
        recent = datetime.now().strftime("%Y-%m-%d")
        entry = self._entry(recent)
        result = handler.define_tags(entry)
        assert "#pyladies" in result
        assert "#python" in result

    def test_rladies_bot_base_tags(self):
        handler = make_handler({"client_name": "rladies_bot"})
        recent = datetime.now().strftime("%Y-%m-%d")
        entry = self._entry(recent)
        result = handler.define_tags(entry)
        assert "#rladies" in result
        assert "#rstats" in result

    def test_oldiebutgoodie_added_for_old_posts(self):
        handler = make_handler({"client_name": "pyladies_bot"})
        old_date = (datetime.now() - timedelta(days=800)).strftime("%Y-%m-%d")
        entry = self._entry(old_date)
        result = handler.define_tags(entry)
        assert "#oldiebutgoodie" in result

    def test_oldiebutgoodie_not_added_for_recent_posts(self):
        handler = make_handler({"client_name": "pyladies_bot"})
        recent = datetime.now().strftime("%Y-%m-%d")
        entry = self._entry(recent)
        result = handler.define_tags(entry)
        assert "#oldiebutgoodie" not in result

    def test_reserved_tags_not_duplicated(self):
        # "pyladies" is already in base tags — should not appear twice
        handler = make_handler({"client_name": "pyladies_bot"})
        recent = datetime.now().strftime("%Y-%m-%d")
        entry = self._entry(recent, tags=["pyladies"])
        result = handler.define_tags(entry)
        assert result.count("#pyladies") == 1

    def test_custom_tags_included(self):
        handler = make_handler({"client_name": "pyladies_bot"})
        recent = datetime.now().strftime("%Y-%m-%d")
        entry = self._entry(recent, tags=["datascience", "ml"])
        result = handler.define_tags(entry)
        assert "#datascience" in result
        assert "#ml" in result

    def test_unknown_client_name_returns_empty_base(self):
        handler = make_handler({"client_name": "unknown_bot"})
        recent = datetime.now().strftime("%Y-%m-%d")
        entry = self._entry(recent)
        result = handler.define_tags(entry)
        # No base tags for unknown bot
        assert "#pyladies" not in result
        assert "#rladies" not in result


# ---------------------------------------------------------------------------
# check_platform_handle
# ---------------------------------------------------------------------------

class TestCheckPlatformHandle:
    def test_adds_at_when_missing(self):
        result = PromoteBlogPost.check_platform_handle("user.bsky.social")
        assert result == "@user.bsky.social"

    def test_leaves_at_intact(self):
        result = PromoteBlogPost.check_platform_handle("@user.bsky.social")
        assert result == "@user.bsky.social"

    def test_empty_string_passthrough(self):
        # Empty handle should pass through unchanged (len <= 1)
        result = PromoteBlogPost.check_platform_handle("")
        assert result == ""

    def test_single_char_passthrough(self):
        result = PromoteBlogPost.check_platform_handle("x")
        assert result == "x"


# ---------------------------------------------------------------------------
# get_number_of_archive_entries
# ---------------------------------------------------------------------------

class TestGetNumberOfArchiveEntries:
    def test_correct_counts_returned(self):
        d = [object()] * 5
        archive = {"link": ["a", "b", "c"]}
        _, n_archive, n_feed = PromoteBlogPost.get_number_of_archive_entries(
            d, archive
        )
        assert n_feed == 5
        assert n_archive == 3

    def test_duplicate_archive_links_deduplicated(self):
        d = [object()] * 3
        archive = {"link": ["a", "a", "b"]}
        _, n_archive, _ = PromoteBlogPost.get_number_of_archive_entries(d, archive)
        assert n_archive == 2  # deduplicated

    def test_malformed_archive_repaired(self):
        # Archive missing "link" key — should be repaired
        d = [object()]
        archive = {"url": ["a", "b"]}  # wrong key
        result_archive, _, _ = PromoteBlogPost.get_number_of_archive_entries(
            d, archive
        )
        assert "link" in result_archive
        assert isinstance(result_archive["link"], list)

    def test_empty_archive(self):
        d = [object()] * 3
        archive = {"link": []}
        _, n_archive, n_feed = PromoteBlogPost.get_number_of_archive_entries(d, archive)
        assert n_archive == 0
        assert n_feed == 3

    def test_empty_feed(self):
        d = []
        archive = {"link": ["a", "b"]}
        _, n_archive, n_feed = PromoteBlogPost.get_number_of_archive_entries(d, archive)
        assert n_feed == 0
        assert n_archive == 2


# ---------------------------------------------------------------------------
# adjust_archive_path
# ---------------------------------------------------------------------------

class TestAdjustArchivePath:
    def test_standard_domain_unchanged(self):
        base = Path("/archive/example.com")
        result = PromoteBlogPost.adjust_archive_path(base, "example.com", "Author Name")
        assert result == base

    def test_youtube_domain_appends_slug(self):
        base = Path("/archive/www.youtube.com")
        result = PromoteBlogPost.adjust_archive_path(base, "www.youtube.com", "Author Name")
        assert result == base / "author-name" / "author-name"

    def test_medium_domain_appends_slug(self):
        base = Path("/archive/medium.com")
        result = PromoteBlogPost.adjust_archive_path(base, "medium.com", "Some Author")
        assert result == base / "some-author" / "some-author"

    def test_slug_replaces_spaces_with_hyphens(self):
        base = Path("/archive/www.youtube.com")
        result = PromoteBlogPost.adjust_archive_path(base, "www.youtube.com", "Jane Doe")
        assert "jane-doe" in str(result)


# ---------------------------------------------------------------------------
# generate_text_to_summarize
# ---------------------------------------------------------------------------

class TestGenerateTextToSummarize:
    def test_short_text_returned_unchanged(self):
        entry = {"title": "Short title", "summary": "Brief summary."}
        result = PromoteBlogPost.generate_text_to_summarize(entry)
        assert "Short title" in result
        assert "Brief summary." in result

    def test_long_text_truncated_to_700_words(self):
        long_summary = " ".join(["word"] * 1000)
        entry = {"title": "Title", "summary": long_summary}
        result = PromoteBlogPost.generate_text_to_summarize(entry)
        assert len(result.split()) <= 700

    def test_exactly_700_words_not_truncated(self):
        # Title adds ~2 words; fill remaining with summary words
        title = "T"  # 1 word after "Title: "
        summary_words = ["word"] * 697
        entry = {"title": title, "summary": " ".join(summary_words)}
        result = PromoteBlogPost.generate_text_to_summarize(entry)
        assert len(result.split()) <= 700


# ---------------------------------------------------------------------------
# clean_response
# ---------------------------------------------------------------------------

class TestCleanResponse:
    def test_collapses_newlines_and_spaces(self):
        response = MagicMock()
        response.text = "Hello\n\nworld   here"
        result = PromoteBlogPost.clean_response(response)
        assert result == "Hello world here"

    def test_leading_trailing_whitespace_stripped(self):
        response = MagicMock()
        response.text = "  trimmed  "
        result = PromoteBlogPost.clean_response(response)
        assert result == "trimmed"


# ---------------------------------------------------------------------------
# build_post_mastodon
# ---------------------------------------------------------------------------

class TestBuildPostMastodon:
    def test_returns_string_not_textbuilder(self):
        handler = make_handler({"platform": "mastodon", "gen_ai_support": False})
        entry = {"title": "T", "link": "https://x.com", "pub_date": "2024-01-01",
                 "tags": [], "summary": "", "media_content": []}
        result = handler.build_post_mastodon("base text", "", "#tag", entry)
        assert isinstance(result, str)

    def test_gen_ai_summary_appended_with_concat(self):
        # Verifies fix: basis_text += ... (not .text())
        handler = make_handler({"platform": "mastodon", "gen_ai_support": True,
                                "gemini_model_name": "gemini-2.5-flash"})
        entry = {"title": "T", "link": "https://x.com", "pub_date": "2024-01-01",
                 "tags": [], "summary": "content", "media_content": []}
        with patch.object(handler, "summarize_text", return_value="AI summary"):
            result = handler.build_post_mastodon("base text", "", "#tag", entry)
        assert "AI summary" in result
        assert isinstance(result, str)

    def test_no_gen_ai_no_summary(self):
        handler = make_handler({"platform": "mastodon", "gen_ai_support": False})
        entry = {"title": "T", "link": "https://x.com", "pub_date": "2024-01-01",
                 "tags": [], "summary": "", "media_content": []}
        with patch.object(handler, "summarize_text") as mock_sum:
            handler.build_post_mastodon("base", "", "#tag", entry)
        mock_sum.assert_not_called()

    def test_platform_handle_included(self):
        handler = make_handler({"platform": "mastodon", "gen_ai_support": False})
        entry = {"title": "T", "link": "https://x.com", "pub_date": "2024-01-01",
                 "tags": [], "summary": "", "media_content": []}
        result = handler.build_post_mastodon("base", "@author@example.social", "#tag", entry)
        assert "@author@example.social" in result


# ---------------------------------------------------------------------------
# build_post — platform routing
# ---------------------------------------------------------------------------

class TestBuildPost:
    def test_returns_none_for_unknown_platform(self):
        handler = make_handler({"platform": "twitter"})
        entry = {"title": "T", "link": "https://x.com", "pub_date": "2024-01-01",
                 "tags": [], "summary": "", "media_content": []}
        feed = {"name": "Author", "twitter": None, "mastodon": None, "bluesky": None}
        result = handler.build_post(entry, feed)
        assert result is None

    def test_routes_to_mastodon_builder(self):
        handler = make_handler({"platform": "mastodon", "gen_ai_support": False})
        entry = {"title": "T", "link": "https://x.com", "pub_date": "2024-01-01",
                 "tags": [], "summary": "", "media_content": []}
        feed = {"name": "Author", "mastodon": None}
        with patch.object(handler, "build_post_mastodon", return_value="post") as m:
            handler.build_post(entry, feed)
        m.assert_called_once()

    def test_routes_to_bluesky_builder(self):
        handler = make_handler({"platform": "bluesky", "gen_ai_support": False})
        entry = {"title": "T", "link": "https://x.com", "pub_date": "2024-01-01",
                 "tags": [], "summary": "", "media_content": []}
        feed = {"name": "Author", "bluesky": None}
        with patch.object(handler, "build_post_bluesky", return_value=MagicMock()) as m:
            handler.build_post(entry, feed)
        m.assert_called_once()


# ---------------------------------------------------------------------------
# _process_feed — the core posting loop
# ---------------------------------------------------------------------------

class TestProcessFeedInner:
    @patch("promote_blog_post.time.sleep")
    def test_dry_run_increments_count_without_posting(self, mock_sleep):
        handler = make_handler(no_dry_run=False)
        entries = [make_entry(link="https://example.com/new")]
        feed_config = make_feed_config(entries)

        with patch.object(handler, "send_post") as mock_send:
            result = handler._process_feed(None, 0, feed_config)

        assert result == 1
        mock_send.assert_not_called()

    def test_dry_run_does_not_modify_archive(self):
        handler = make_handler(no_dry_run=False)
        entries = [make_entry(link="https://example.com/new")]
        feed_config = make_feed_config(entries)
        original_archive = list(feed_config["rss_feed_archive"]["link"])

        handler._process_feed(None, 0, feed_config)

        assert feed_config["rss_feed_archive"]["link"] == original_archive

    @patch("promote_blog_post.time.sleep")
    def test_production_posts_and_saves_archive(self, mock_sleep):
        handler = make_handler(no_dry_run=True)
        entries = [make_entry(link="https://example.com/new")]
        feed_config = make_feed_config(entries)

        with patch.object(handler, "send_post", return_value="success"), \
             patch.object(handler, "_save_rss_feed_archive") as mock_save:
            result = handler._process_feed(MagicMock(), 0, feed_config)

        assert result == 1
        mock_save.assert_called_once()

    @patch("promote_blog_post.time.sleep")
    def test_stops_after_one_post_per_feed(self, mock_sleep):
        handler = make_handler(no_dry_run=True)
        entries = [
            make_entry(link="https://example.com/post1"),
            make_entry(link="https://example.com/post2"),
            make_entry(link="https://example.com/post3"),
        ]
        feed_config = make_feed_config(entries)

        with patch.object(handler, "send_post", return_value="success") as mock_send, \
             patch.object(handler, "_save_rss_feed_archive"):
            handler._process_feed(MagicMock(), 0, feed_config)

        assert mock_send.call_count == 1

    @patch("promote_blog_post.time.sleep")
    def test_skips_already_archived_links(self, mock_sleep):
        handler = make_handler(no_dry_run=True)
        existing_link = "https://example.com/old"
        entries = [make_entry(link=existing_link)]
        feed_config = make_feed_config(entries, archived_links=[existing_link])

        with patch.object(handler, "send_post") as mock_send:
            result = handler._process_feed(MagicMock(), 0, feed_config)

        mock_send.assert_not_called()
        assert result == 0

    @patch("promote_blog_post.time.sleep")
    def test_count_fails_stops_loop_and_archive_not_saved(self, mock_sleep):
        handler = make_handler(no_dry_run=True)
        entries = [
            make_entry(link="https://example.com/post1"),
            make_entry(link="https://example.com/post2"),
        ]
        feed_config = make_feed_config(entries)

        with patch.object(handler, "send_post", return_value="failed"), \
             patch.object(handler, "_save_rss_feed_archive") as mock_save:
            result = handler._process_feed(MagicMock(), 0, feed_config)

        # count_post unchanged because result was never 'success'
        assert result == 0
        mock_save.assert_not_called()

    @patch("promote_blog_post.time.sleep")
    def test_archive_not_saved_when_no_dry_run_false(self, mock_sleep):
        handler = make_handler(no_dry_run=False)
        entries = [make_entry(link="https://example.com/new")]
        feed_config = make_feed_config(entries)

        with patch.object(handler, "_save_rss_feed_archive") as mock_save:
            handler._process_feed(None, 0, feed_config)

        mock_save.assert_not_called()

    @patch("promote_blog_post.time.sleep")
    def test_count_post_passed_through_correctly(self, mock_sleep):
        # Starting count_post at 1 should still allow one more post (up to cap in outer loop)
        handler = make_handler(no_dry_run=True)
        entries = [make_entry(link="https://example.com/post1")]
        feed_config = make_feed_config(entries)

        with patch.object(handler, "send_post", return_value="success"), \
             patch.object(handler, "_save_rss_feed_archive"):
            result = handler._process_feed(MagicMock(), 1, feed_config)

        assert result == 2


# ---------------------------------------------------------------------------
# _save_rss_feed_archive
# ---------------------------------------------------------------------------

class TestSaveRssFeedArchive:
    def test_writes_utf8_json(self, tmp_path):
        handler = make_handler()
        archive_dir = tmp_path / "example.com"
        archive_dir.mkdir()
        feed = {"name": "Test", "ARCHIVE": [str(archive_dir)]}
        archive_data = {"link": ["https://example.com/a"]}

        handler._save_rss_feed_archive(feed, archive_data)

        written = json.loads((archive_dir / "file.json").read_text(encoding="utf-8"))
        assert written == archive_data

    def test_overwrites_existing_file(self, tmp_path):
        handler = make_handler()
        archive_dir = tmp_path / "example.com"
        archive_dir.mkdir()
        (archive_dir / "file.json").write_text('{"link": ["old"]}', encoding="utf-8")

        feed = {"name": "Test", "ARCHIVE": [str(archive_dir)]}
        new_data = {"link": ["https://example.com/new"]}

        handler._save_rss_feed_archive(feed, new_data)

        written = json.loads((archive_dir / "file.json").read_text(encoding="utf-8"))
        assert written["link"] == ["https://example.com/new"]


# ---------------------------------------------------------------------------
# get_rss_feed_archive
# ---------------------------------------------------------------------------

class TestGetRssFeedArchive:
    def test_returns_empty_archive_when_dir_missing(self, tmp_path):
        feed = {
            "name": "Author",
            "ARCHIVE": [str(tmp_path / "nonexistent" / "example.com")],
        }
        result = PromoteBlogPost.get_rss_feed_archive(feed)
        assert result == {"link": []}

    def test_creates_missing_directory(self, tmp_path):
        target = tmp_path / "new_dir" / "example.com"
        feed = {"name": "Author", "ARCHIVE": [str(target)]}
        PromoteBlogPost.get_rss_feed_archive(feed)
        assert target.exists()

    def test_returns_empty_archive_on_corrupt_json(self, tmp_path):
        archive_dir = tmp_path / "example.com"
        archive_dir.mkdir()
        (archive_dir / "file.json").write_bytes(b"not valid json{{{")
        feed = {"name": "Author", "ARCHIVE": [str(archive_dir)]}
        result = PromoteBlogPost.get_rss_feed_archive(feed)
        assert result == {"link": []}

    def test_loads_valid_archive(self, tmp_path):
        archive_dir = tmp_path / "example.com"
        archive_dir.mkdir()
        data = {"link": ["https://example.com/a", "https://example.com/b"]}
        (archive_dir / "file.json").write_text(json.dumps(data), encoding="utf-8")
        feed = {"name": "Author", "ARCHIVE": [str(archive_dir)]}
        result = PromoteBlogPost.get_rss_feed_archive(feed)
        assert result == data


# ---------------------------------------------------------------------------
# process_feeds — outer loop, 2-post cap, counter rotation
# ---------------------------------------------------------------------------

class TestProcessFeeds:
    def _make_feeds(self, names):
        return [
            {
                "name": n,
                "rss_feed": [f"https://{n.lower().replace(' ', '')}.com/feed"],
                "bluesky": None,
                "mastodon": None,
            }
            for n in names
        ]

    @patch("promote_blog_post.time.sleep")
    def test_caps_at_two_posts_per_run(self, mock_sleep):
        handler = make_handler(no_dry_run=True)
        feeds = self._make_feeds(["Alice", "Bob", "Carol"])

        call_count = 0
        def fake_process_feed(feed, count_post, client):
            nonlocal call_count
            call_count += 1
            return count_post + 1  # each call "posts" one item

        with patch.object(handler, "process_feed", side_effect=fake_process_feed), \
             patch.object(handler, "update_counter"):
            handler.process_feeds(feeds, "Alice", 0, MagicMock())

        assert call_count <= 2

    @patch("promote_blog_post.time.sleep")
    def test_last_feed_wraps_counter_to_feeds_index_1(self, mock_sleep):
        handler = make_handler(no_dry_run=True)
        feeds = self._make_feeds(["Alice", "Bob", "Carol"])

        def fake_process(feed, count_post, client):
            return count_post  # nothing posted → stays 0

        captured_counter = []

        with patch.object(handler, "process_feed", side_effect=fake_process), \
             patch.object(
                 handler, "update_counter",
                 side_effect=captured_counter.append
             ):
            # counter_name matches last feed → wrap-around path
            handler.process_feeds(feeds, "Carol", 0, MagicMock())

        assert "Bob" in captured_counter  # wraps to feeds[1]

    @patch("promote_blog_post.time.sleep")
    def test_single_feed_wrap_uses_feeds_0(self, mock_sleep):
        handler = make_handler(no_dry_run=True)
        feeds = self._make_feeds(["OnlyFeed"])

        def fake_process(feed, count_post, client):
            return count_post  # nothing posted

        captured_counter = []
        with patch.object(handler, "process_feed", side_effect=fake_process), \
             patch.object(
                 handler, "update_counter",
                 side_effect=captured_counter.append
             ):
            handler.process_feeds(feeds, "OnlyFeed", 0, MagicMock())

        assert "OnlyFeed" in captured_counter


# ---------------------------------------------------------------------------
# get_config — genai.configure called in both code paths
# ---------------------------------------------------------------------------

class TestGetConfig:
    @patch("promote_blog_post.genai")
    def test_genai_configure_called_with_passed_config(self, mock_genai):
        """
        Critical: genai.configure must be called even when config_dict is
        passed directly (e.g. from debug.py) — not only via the env-var path.
        """
        cfg = {**BASE_CONFIG, "gen_ai_support": True, "gemini_api_key": "test-key"}
        handler = PromoteBlogPost(config_dict=cfg, no_dry_run=False)
        handler.get_config()
        mock_genai.configure.assert_called_once_with(api_key="test-key")

    @patch("promote_blog_post.genai")
    @patch.dict(os.environ, {
        "PLATFORM": "bluesky",
        "ARCHIVE_DIRECTORY": "test_archive",
        "IMAGES": "test_images",
        "COUNTER": "test_counter.txt",
        "PASSWORD": "pw",
        "USERNAME": "user",
        "CLIENT_NAME": "test_bot",
        "JSON_FILE": "test_meta.json",
        "GEMINI_API_KEY": "env-key",
    })
    def test_genai_configure_called_via_env_path(self, mock_genai):
        """genai.configure must be called on the GitHub Actions env-var path."""
        handler = PromoteBlogPost(config_dict=None, no_dry_run=True)
        handler.get_config()
        mock_genai.configure.assert_called_with(api_key="env-key")

    @patch("promote_blog_post.genai")
    def test_genai_not_called_when_gen_ai_support_false(self, mock_genai):
        cfg = {**BASE_CONFIG, "gen_ai_support": False}
        handler = PromoteBlogPost(config_dict=cfg, no_dry_run=False)
        handler.get_config()
        mock_genai.configure.assert_not_called()

    def test_metadata_prefix_applied_to_counter_and_json(self):
        cfg = {**BASE_CONFIG, "counter": "my_counter.txt", "json_file": "my_meta.json"}
        handler = PromoteBlogPost(config_dict=cfg, no_dry_run=False)
        with patch("promote_blog_post.genai"):
            handler.get_config()
        assert handler.config_dict["counter"].startswith("metadata/")
        assert handler.config_dict["json_file"].startswith("metadata/")


# ---------------------------------------------------------------------------
# promote_blog_post dry-run outer loop — 2-post cap enforced
# ---------------------------------------------------------------------------

class TestPromoteBlogPostDryRunCap:
    @patch("promote_blog_post.time.sleep")
    def test_dry_run_stops_at_two_posts(self, mock_sleep):
        feeds = [
            {"name": f"Author{i}", "rss_feed": [f"https://author{i}.com/feed"],
             "bluesky": None, "mastodon": None}
            for i in range(5)
        ]
        handler = make_handler(no_dry_run=False)

        def fake_process(feed, count_post, client):
            return count_post + 1

        with patch.object(handler, "read_metadata_json", return_value=feeds), \
             patch.object(handler, "read_counter_name", return_value=""), \
             patch.object(handler, "process_feed", side_effect=fake_process) as mock_pf:
            handler.promote_blog_post()

        total_increments = sum(
            1 for c in mock_pf.call_args_list
        )
        assert total_increments <= 2


# ---------------------------------------------------------------------------
# _get_media_content
# ---------------------------------------------------------------------------

class TestGetMediaContent:
    def test_youtube_link_builds_thumbnail_url(self):
        entry = FeedEntry(
            link="https://www.youtube.com/watch?v=abc123",
            id="yt:video:abc123",
            summary="",
        )
        result = PromoteBlogPost._get_media_content(entry)
        assert "hqdefault.jpg" in result.get("media_content", "")
        assert "abc123" in result["media_content"]

    def test_media_content_field_extracted(self):
        entry = FeedEntry(
            link="https://example.com/post",
            media_content=[{"url": "https://example.com/img.png"}],
            summary="",
        )
        result = PromoteBlogPost._get_media_content(entry)
        assert result.get("media_content") == "https://example.com/img.png"

    def test_image_extracted_from_html_summary(self):
        entry = FeedEntry(
            link="https://example.com/post",
            summary='<p><img src="https://example.com/img.jpg" alt="alt text"/></p>',
        )
        result = PromoteBlogPost._get_media_content(entry)
        assert result.get("media_content") == "https://example.com/img.jpg"
        assert result.get("alt_text") == "alt text"

    def test_no_media_returns_empty_dict(self):
        entry = FeedEntry(
            link="https://example.com/post",
            summary="<p>No images here</p>",
        )
        result = PromoteBlogPost._get_media_content(entry)
        assert not result
