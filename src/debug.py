""" This script aims at making debugging easier """
import os
import logging
from dotenv import load_dotenv
import config

from promote_blog_post import PromoteBlogPost
from get_rss_data import RSSData
from boost_tags import BoostTags
from promote_anniversaries import PromoteAnniversary
from boost_mentions import BoostMentions

load_dotenv()
logging.basicConfig(level=logging.INFO)


class DebugBots:
    """
    Class to handle debugging of all modules.
    """
    def __init__(self):
        self.bot = 'rladies'
        self.platform = 'bluesky'
        self.what_to_debug = 'boost_mentions'
        self.no_dry_run = False  # True to actually repost
        # self.bot = 'rladies'  # 'pyladies' or 'rladies'
        # self.what_to_debug = 'blog'  # blog, boost_tags, rss, anniversary, boost_mentions
        # self.platform = 'bluesky'  # 'bluesky' or 'mastodon'
        # self.no_dry_run = False

    def start_debug(self):
        """Start debugging."""
        if self.what_to_debug == 'blog':
            config_dict = self.get_config_blog()
            promote_blog_post_handler = PromoteBlogPost(
                config_dict,
                self.no_dry_run
            )
            promote_blog_post_handler.promote_blog_post()

        elif self.what_to_debug == 'rss':
            config_dict = self.get_config_rss()
            rss_data_handler = RSSData(
                config_dict,
                self.no_dry_run
            )
            rss_data_handler.get_rss_data()

        elif self.what_to_debug == 'boost_tags':
            config_dict = self.get_config_boost()
            boost_tags_handler = BoostTags(
                config_dict,
                self.no_dry_run
            )
            boost_tags_handler.boost_tags()

        elif self.what_to_debug == 'boost_mentions':
            config_dict = self.get_config_boost()
            boost_tags_handler = BoostMentions(
                config_dict,
                self.no_dry_run
            )
            boost_tags_handler.boost_mentions()

        elif self.what_to_debug == 'anniversary':
            config_dict = self.get_config_anniversary()
            promote_anniversary_handler = PromoteAnniversary(
                config_dict,
                self.no_dry_run
            )
            promote_anniversary_handler.promote_anniversary()

    def get_config_blog(self):
        """Method to generate config for promoting blog posts"""
        if self.bot == 'pyladies':
            if self.platform == 'bluesky':
                return {
                    "archive": "pyladies_archive_directory_bluesky",
                    "counter": "metadata/pyladies_counter_bluesky.txt",
                    "json_file": "metadata/pyladies_meta_data.json",
                    "client_name": "pyladies_self.bot",
                    "images": "pyladies_images",
                    "api_base_url": self.platform,
                    "mastodon": None,
                    "gen_ai_support": True,
                    "gemini_model_name": "gemini-2.5-flash",
                    "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("PYLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                }
            return {
                'archive': 'pyladies_archive_directory',
                'counter': 'pyladies_counter.txt',
                'json_file': 'metadata/pyladies_meta_data.json',
                'client_name': 'pyladies_self.bot',
                'mastodon': None,
                'platform': 'mastodon',
            }

        if self.bot == 'rladies':
            if self.platform == 'bluesky':
                return {
                    "archive": "rladies_archive_directory_bluesky",
                    "counter": "../metadata/rladies_counter_bluesky.txt",
                    "json_file": "../metadata/rladies_meta_data.json",
                    "client_name": "rladies_self.bot",
                    "images": "rladies_images",
                    "api_base_url": self.platform,
                    "mastodon": None,
                    "gen_ai_support": True,
                    "gemini_model_name": "gemini-2.5-flash",
                    "password": os.getenv("RLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("RLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                }
            return {
                "archive": "rladies_archive_directory",
                "counter": "../metadata/rladies_counter.txt",
                "json_file": "../metadata/rladies_meta_data.json",
                "client_name": "rladies_self.bot",
                "mastodon": None,
                "platform": "mastodon",
            }

        return None

    def get_config_boost(self):
        """Method to generate config for boosting tags"""
        if self.bot == 'pyladies':
            if self.platform == 'bluesky':
                return {
                    "client_name": "pyladies_bot",
                    "api_base_url": self.platform,
                    "mastodon": None,
                    "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("PYLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                    "tags": "pyladies",
                }
            if self.platform == 'mastodon':
                return {
                    "client_name": "pyladies_bot",
                    "api_base_url": config.API_BASE_URL,
                    "mastodon": None,
                    "password": os.getenv("PYLADIES_MASTODON_PASSWORD"),
                    "username": os.getenv("PYLADIES_MASTODON_USERNAME"),
                    "access_token": os.getenv("PYLADIES_MASTODON_ACCESS_TOKEN"),
                    "client_cred_file": os.getenv("PYLADIES_BOT_CLIENTCRED_SECRET"),
                    "platform": self.platform,
                    "mastodon_visibility": config.MASTODON_VISIBILITY,
                    "tags": "pyladies",
                }

        if self.bot == 'rladies':
            if self.platform == "bluesky":
                return {
                    "client_name": "rladies_bot",
                    "api_base_url": self.platform,
                    "mastodon": None,
                    "password": os.getenv("RLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("RLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                    "tags": "rladies",
                }
            if self.platform == 'mastodon':
                return {
                    "client_name": "rladies_bot",
                    "api_base_url": config.API_BASE_URL,
                    "mastodon": None,
                    "password": os.getenv("RLADIES_MASTODON_PASSWORD"),
                    "username": os.getenv("RLADIES_MASTODON_USERNAME"),
                    "access_token": os.getenv("RLADIES_MASTODON_ACCESS_TOKEN"),
                    "client_cred_file": os.getenv("RLADIES_BOT_CLIENTCRED_SECRET"),
                    "platform": self.platform,
                    "mastodon_visibility": config.MASTODON_VISIBILITY,
                    "tags": "rladies",
                }

        return None

    def get_config_anniversary(self):
        """Method to get config for promoting anniversaries"""
        if self.bot == 'pyladies':
            if self.platform == 'bluesky':
                return {
                    'client_name': 'pyladies_self.bot',
                    'api_base_url': self.platform,
                    'mastodon': None,
                    'password': os.getenv('PYLADIES_BSKY_PASSWORD'),
                    'username': os.getenv('PYLADIES_BSKY_USERNAME'),
                    'images': 'anniversary_images',
                    'platform': self.platform,
                }
            return {'client_name': 'pyladies_self.bot', 'mastodon': None, 'platform': 'mastodon'}

        if self.bot == 'rladies':
            if self.platform == 'bluesky':
                return {
                    'client_name': 'rladies_self.bot',
                    'api_base_url': self.platform,
                    'mastodon': None,
                    'password': os.getenv('RLADIES_BSKY_PASSWORD'),
                    'username': os.getenv('RLADIES_BSKY_USERNAME'),
                    'images': 'anniversary_images',
                    'platform': self.platform,
                }
            if self.platform == 'mastodon':
                return {
                    'client_name': 'rladies_self.bot',
                    'api_base_url': config.API_BASE_URL,
                    'mastodon': None,
                    'password': os.getenv('RLADIES_MASTODON_PASSWORD'),
                    'username': os.getenv('RLADIES_MASTODON_USERNAME'),
                    'access_token': os.getenv('RLADIES_MASTODON_ACCESS_TOKEN'),
                    'client_cred_file': os.getenv('RLADIES_BOT_CLIENTCRED_SECRET'),
                    'images': 'anniversary_images',
                    'platform': self.platform,
                    'mastodon_visibility': config.MASTODON_VISIBILITY,
                }
            return {'client_name': 'rladies_self.bot', 'mastodon': None}

        return None

if __name__ == '__main__':
    debug_bots = DebugBots()
    debug_bots.start_debug()
