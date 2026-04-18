# pylint: disable=missing-class-docstring,missing-function-docstring,protected-access
# pylint: disable=unused-argument,attribute-defined-outside-init,too-few-public-methods
"""
Tests for src/debug.py

Covers:
- __init__: default attribute values
- get_config_blog: all bot/platform combos, unknown bot/platform return None
- get_config_boost: all bot/platform combos, correct tags, unknown bot returns None
- get_config_rss: pyladies, rladies, unknown bot returns None
- get_config_anniversary: all bot/platform combos, unknown bot returns None
- start_debug: routes to the correct handler for each what_to_debug value;
  unknown value is a no-op
- client_name values match what consuming modules expect ('pyladies_bot' / 'rladies_bot')
- credentials are sourced from env vars, not hardcoded
"""

from unittest.mock import MagicMock, patch

from debug import DebugBots


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_debug(bot='pyladies', platform='bluesky', what_to_debug='blog', no_dry_run=False):
    d = DebugBots()
    d.bot = bot
    d.platform = platform
    d.what_to_debug = what_to_debug
    d.no_dry_run = no_dry_run
    return d


# ---------------------------------------------------------------------------
# __init__ defaults
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_bot(self):
        assert DebugBots().bot == 'pyladies'

    def test_default_platform(self):
        assert DebugBots().platform == 'bluesky'

    def test_default_what_to_debug(self):
        assert DebugBots().what_to_debug == 'blog'

    def test_default_no_dry_run_is_false(self):
        # False = dry-run is active by default; nothing is actually posted
        assert DebugBots().no_dry_run is False


# ---------------------------------------------------------------------------
# get_config_blog
# ---------------------------------------------------------------------------

class TestGetConfigBlog:
    def test_pyladies_bluesky_required_keys(self):
        d = make_debug(bot='pyladies', platform='bluesky')
        cfg = d.get_config_blog()
        for key in ('archive', 'counter', 'json_file', 'client_name', 'images',
                    'api_base_url', 'password', 'username', 'platform'):
            assert key in cfg

    def test_pyladies_bluesky_client_name(self):
        cfg = make_debug(bot='pyladies', platform='bluesky').get_config_blog()
        assert cfg['client_name'] == 'pyladies_bot'

    def test_pyladies_bluesky_gen_ai_support(self):
        cfg = make_debug(bot='pyladies', platform='bluesky').get_config_blog()
        assert cfg.get('gen_ai_support') is True
        assert cfg.get('gemini_model_name') == 'gemini-2.5-flash'

    def test_pyladies_bluesky_platform_field_matches(self):
        d = make_debug(bot='pyladies', platform='bluesky')
        cfg = d.get_config_blog()
        assert cfg['platform'] == d.platform

    def test_pyladies_mastodon_client_name(self):
        cfg = make_debug(bot='pyladies', platform='mastodon').get_config_blog()
        assert cfg['client_name'] == 'pyladies_bot'

    def test_pyladies_mastodon_has_access_token_key(self):
        cfg = make_debug(bot='pyladies', platform='mastodon').get_config_blog()
        assert 'access_token' in cfg

    def test_pyladies_unknown_platform_returns_none(self):
        assert make_debug(bot='pyladies', platform='twitter').get_config_blog() is None

    def test_rladies_bluesky_client_name(self):
        cfg = make_debug(bot='rladies', platform='bluesky').get_config_blog()
        assert cfg['client_name'] == 'rladies_bot'

    def test_rladies_bluesky_gen_ai_support(self):
        cfg = make_debug(bot='rladies', platform='bluesky').get_config_blog()
        assert cfg.get('gen_ai_support') is True
        assert cfg.get('gemini_model_name') == 'gemini-2.5-flash'

    def test_rladies_mastodon_client_name(self):
        cfg = make_debug(bot='rladies', platform='mastodon').get_config_blog()
        assert cfg['client_name'] == 'rladies_bot'

    def test_rladies_mastodon_has_access_token_key(self):
        cfg = make_debug(bot='rladies', platform='mastodon').get_config_blog()
        assert 'access_token' in cfg

    def test_rladies_unknown_platform_returns_none(self):
        assert make_debug(bot='rladies', platform='twitter').get_config_blog() is None

    def test_unknown_bot_returns_none(self):
        assert make_debug(bot='unknown').get_config_blog() is None

    def test_pyladies_bluesky_reads_password_from_env(self, monkeypatch):
        monkeypatch.setenv('PYLADIES_BSKY_PASSWORD', 'secret-pw')
        cfg = make_debug(bot='pyladies', platform='bluesky').get_config_blog()
        assert cfg['password'] == 'secret-pw'

    def test_rladies_bluesky_reads_password_from_env(self, monkeypatch):
        monkeypatch.setenv('RLADIES_BSKY_PASSWORD', 'rladies-secret')
        cfg = make_debug(bot='rladies', platform='bluesky').get_config_blog()
        assert cfg['password'] == 'rladies-secret'


# ---------------------------------------------------------------------------
# get_config_boost
# ---------------------------------------------------------------------------

class TestGetConfigBoost:
    def test_pyladies_bluesky_tags(self):
        cfg = make_debug(bot='pyladies', platform='bluesky').get_config_boost()
        assert cfg['tags'] == 'pyladies'

    def test_pyladies_bluesky_client_name(self):
        cfg = make_debug(bot='pyladies', platform='bluesky').get_config_boost()
        assert cfg['client_name'] == 'pyladies_bot'

    def test_pyladies_mastodon_tags(self):
        cfg = make_debug(bot='pyladies', platform='mastodon').get_config_boost()
        assert cfg['tags'] == 'pyladies'

    def test_pyladies_mastodon_has_access_token_key(self):
        cfg = make_debug(bot='pyladies', platform='mastodon').get_config_boost()
        assert 'access_token' in cfg

    def test_rladies_bluesky_tags(self):
        cfg = make_debug(bot='rladies', platform='bluesky').get_config_boost()
        assert cfg['tags'] == 'rladies'

    def test_rladies_bluesky_client_name(self):
        cfg = make_debug(bot='rladies', platform='bluesky').get_config_boost()
        assert cfg['client_name'] == 'rladies_bot'

    def test_rladies_bluesky_uses_prefixed_env_vars(self, monkeypatch):
        # Guard against regression to generic PASSWORD/USERNAME
        monkeypatch.setenv('RLADIES_BSKY_PASSWORD', 'rladies-pw')
        monkeypatch.setenv('RLADIES_BSKY_USERNAME', 'rladies-user')
        cfg = make_debug(bot='rladies', platform='bluesky').get_config_boost()
        assert cfg['password'] == 'rladies-pw'
        assert cfg['username'] == 'rladies-user'

    def test_rladies_mastodon_tags(self):
        cfg = make_debug(bot='rladies', platform='mastodon').get_config_boost()
        assert cfg['tags'] == 'rladies'

    def test_rladies_mastodon_has_access_token_key(self):
        cfg = make_debug(bot='rladies', platform='mastodon').get_config_boost()
        assert 'access_token' in cfg

    def test_unknown_bot_returns_none(self):
        assert make_debug(bot='unknown').get_config_boost() is None

    def test_pyladies_unknown_platform_returns_none(self):
        assert make_debug(bot='pyladies', platform='twitter').get_config_boost() is None

    def test_rladies_unknown_platform_returns_none(self):
        assert make_debug(bot='rladies', platform='twitter').get_config_boost() is None


# ---------------------------------------------------------------------------
# get_config_rss
# ---------------------------------------------------------------------------

class TestGetConfigRss:
    def test_pyladies_json_file(self):
        cfg = make_debug(bot='pyladies').get_config_rss()
        assert cfg['json_file'] == 'metadata/pyladies_meta_data.json'

    def test_pyladies_has_github_raw_url(self):
        cfg = make_debug(bot='pyladies').get_config_rss()
        assert 'github_raw_url' in cfg
        assert cfg['github_raw_url'].startswith('https://')

    def test_pyladies_has_api_base_url(self):
        cfg = make_debug(bot='pyladies').get_config_rss()
        assert 'api_base_url' in cfg

    def test_rladies_json_file(self):
        cfg = make_debug(bot='rladies').get_config_rss()
        assert cfg['json_file'] == '../metadata/rladies_meta_data.json'

    def test_rladies_has_github_raw_url(self):
        cfg = make_debug(bot='rladies').get_config_rss()
        assert 'github_raw_url' in cfg
        assert cfg['github_raw_url'].startswith('https://')

    def test_unknown_bot_returns_none(self):
        assert make_debug(bot='unknown').get_config_rss() is None

    def test_pyladies_and_rladies_urls_differ(self):
        pyladies_url = make_debug(bot='pyladies').get_config_rss()['github_raw_url']
        rladies_url = make_debug(bot='rladies').get_config_rss()['github_raw_url']
        assert pyladies_url != rladies_url


# ---------------------------------------------------------------------------
# get_config_anniversary
# ---------------------------------------------------------------------------

class TestGetConfigAnniversary:
    def test_pyladies_bluesky_client_name(self):
        cfg = make_debug(bot='pyladies', platform='bluesky').get_config_anniversary()
        assert cfg['client_name'] == 'pyladies_bot'

    def test_pyladies_bluesky_has_images(self):
        cfg = make_debug(bot='pyladies', platform='bluesky').get_config_anniversary()
        assert 'images' in cfg

    def test_pyladies_mastodon_client_name(self):
        cfg = make_debug(bot='pyladies', platform='mastodon').get_config_anniversary()
        assert cfg['client_name'] == 'pyladies_bot'

    def test_pyladies_mastodon_has_access_token_key(self):
        cfg = make_debug(bot='pyladies', platform='mastodon').get_config_anniversary()
        assert 'access_token' in cfg

    def test_pyladies_unknown_platform_returns_none(self):
        assert make_debug(bot='pyladies', platform='twitter').get_config_anniversary() is None

    def test_rladies_bluesky_client_name(self):
        cfg = make_debug(bot='rladies', platform='bluesky').get_config_anniversary()
        assert cfg['client_name'] == 'rladies_bot'

    def test_rladies_mastodon_client_name(self):
        cfg = make_debug(bot='rladies', platform='mastodon').get_config_anniversary()
        assert cfg['client_name'] == 'rladies_bot'

    def test_rladies_mastodon_has_access_token_key(self):
        cfg = make_debug(bot='rladies', platform='mastodon').get_config_anniversary()
        assert 'access_token' in cfg

    def test_rladies_unknown_platform_returns_none(self):
        assert make_debug(bot='rladies', platform='twitter').get_config_anniversary() is None

    def test_unknown_bot_returns_none(self):
        assert make_debug(bot='unknown').get_config_anniversary() is None

    def test_platform_field_matches_instance_platform(self):
        d = make_debug(bot='rladies', platform='bluesky')
        cfg = d.get_config_anniversary()
        assert cfg['platform'] == d.platform


# ---------------------------------------------------------------------------
# start_debug routing
# ---------------------------------------------------------------------------

class TestStartDebug:
    @patch('debug.PromoteBlogPost')
    def test_blog_invokes_promote_blog_post(self, mock_cls):
        d = make_debug(what_to_debug='blog')
        d.get_config_blog = MagicMock(return_value={'client_name': 'pyladies_bot'})
        d.start_debug()
        mock_cls.assert_called_once()
        mock_cls.return_value.promote_blog_post.assert_called_once()

    @patch('debug.RSSData')
    def test_rss_invokes_rss_data(self, mock_cls):
        d = make_debug(what_to_debug='rss')
        d.get_config_rss = MagicMock(return_value={'json_file': 'x.json'})
        d.start_debug()
        mock_cls.assert_called_once()
        mock_cls.return_value.get_rss_data.assert_called_once()

    @patch('debug.BoostTags')
    def test_boost_tags_invokes_boost_tags(self, mock_cls):
        d = make_debug(what_to_debug='boost_tags')
        d.get_config_boost = MagicMock(return_value={'client_name': 'pyladies_bot'})
        d.start_debug()
        mock_cls.assert_called_once()
        mock_cls.return_value.boost_tags.assert_called_once()

    @patch('debug.BoostMentions')
    def test_boost_mentions_invokes_boost_mentions(self, mock_cls):
        d = make_debug(what_to_debug='boost_mentions')
        d.get_config_boost = MagicMock(return_value={'client_name': 'rladies_bot'})
        d.start_debug()
        mock_cls.assert_called_once()
        mock_cls.return_value.boost_mentions.assert_called_once()

    @patch('debug.PromoteAnniversary')
    def test_anniversary_invokes_promote_anniversary(self, mock_cls):
        d = make_debug(what_to_debug='anniversary')
        d.get_config_anniversary = MagicMock(return_value={'client_name': 'rladies_bot'})
        d.start_debug()
        mock_cls.assert_called_once()
        mock_cls.return_value.promote_anniversary.assert_called_once()

    @patch('debug.PromoteBlogPost')
    @patch('debug.RSSData')
    @patch('debug.BoostTags')
    @patch('debug.BoostMentions')
    @patch('debug.PromoteAnniversary')
    def test_unknown_what_to_debug_is_noop(self, mock_ann, mock_bm, mock_bt, mock_rss, mock_bp):
        d = make_debug(what_to_debug='nonexistent')
        d.start_debug()
        mock_bp.assert_not_called()
        mock_rss.assert_not_called()
        mock_bt.assert_not_called()
        mock_bm.assert_not_called()
        mock_ann.assert_not_called()

    @patch('debug.PromoteBlogPost')
    def test_start_debug_passes_no_dry_run_to_handler(self, mock_cls):
        d = make_debug(what_to_debug='blog', no_dry_run=True)
        d.get_config_blog = MagicMock(return_value={'client_name': 'pyladies_bot'})
        d.start_debug()
        _, kwargs = mock_cls.call_args
        args = mock_cls.call_args[0]
        assert True in args or kwargs.get('no_dry_run') is True

    @patch('debug.BoostMentions')
    @patch('debug.BoostTags')
    def test_boost_mentions_uses_get_config_boost_not_anniversary(self, mock_bt, mock_bm):
        # boost_mentions and boost_tags share get_config_boost — verify no cross-wiring
        d = make_debug(what_to_debug='boost_mentions')
        d.get_config_boost = MagicMock(return_value={'client_name': 'rladies_bot'})
        d.get_config_anniversary = MagicMock()
        d.start_debug()
        d.get_config_boost.assert_called_once()
        d.get_config_anniversary.assert_not_called()
