""" This script aims at making debugging easier """
import os
import logging
from dotenv import load_dotenv
import config

from promote_blog_post import PromoteBlogPost
from get_rss_data import RSSData
from get_packages_data import PackagesData
from promote_package import PromotePackage
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
        self.bot = 'pyladies'  # 'pyladies' or 'rladies'
        self.what_to_debug = 'package'  # 'blog', 'boost_tags', 'rss', 'anniversary', 'boost_mentions', 'packages', 'package'
        self.platform = 'bluesky'  # 'bluesky' or 'mastodon'
        self.no_dry_run = False  # True to actually post

    def start_debug(self):
        """Start debugging."""
        logger = logging.getLogger(__name__)

        if self.what_to_debug == 'blog':
            config_dict = self.get_config_blog()
            if config_dict is None:
                logger.error(
                    "No config for bot=%r platform=%r — check bot/platform settings.",
                    self.bot, self.platform
                )
                return
            promote_blog_post_handler = PromoteBlogPost(
                config_dict,
                self.no_dry_run
            )
            promote_blog_post_handler.promote_blog_post()

        elif self.what_to_debug == 'rss':
            config_dict = self.get_config_rss()
            if config_dict is None:
                logger.error(
                    "No config for bot=%r platform=%r — check bot/platform settings.",
                    self.bot, self.platform
                )
                return
            rss_data_handler = RSSData(
                config_dict,
                self.no_dry_run
            )
            rss_data_handler.get_rss_data()

        elif self.what_to_debug == 'boost_tags':
            config_dict = self.get_config_boost()
            if config_dict is None:
                logger.error(
                    "No config for bot=%r platform=%r — check bot/platform settings.",
                    self.bot, self.platform
                )
                return
            boost_tags_handler = BoostTags(
                config_dict,
                self.no_dry_run
            )
            boost_tags_handler.boost_tags()

        elif self.what_to_debug == 'boost_mentions':
            config_dict = self.get_config_boost()
            if config_dict is None:
                logger.error(
                    "No config for bot=%r platform=%r — check bot/platform settings.",
                    self.bot, self.platform
                )
                return
            boost_mentions_handler = BoostMentions(
                config_dict,
                self.no_dry_run
            )
            boost_mentions_handler.boost_mentions()

        elif self.what_to_debug == 'anniversary':
            config_dict = self.get_config_anniversary()
            if config_dict is None:
                logger.error(
                    "No config for bot=%r platform=%r — check bot/platform settings.",
                    self.bot, self.platform
                )
                return
            promote_anniversary_handler = PromoteAnniversary(
                config_dict,
                self.no_dry_run
            )
            promote_anniversary_handler.promote_anniversary()

        elif self.what_to_debug == 'packages':
            config_dict = self.get_config_packages()
            if config_dict is None:
                logger.error(
                    "No config for bot=%r — check bot settings.",
                    self.bot
                )
                return
            packages_data_handler = PackagesData(
                config_dict,
                self.no_dry_run
            )
            packages_data_handler.get_packages_data()

        elif self.what_to_debug == 'package':
            config_dict = self.get_config_package()
            if config_dict is None:
                logger.error(
                    "No config for bot=%r platform=%r — check bot/platform settings.",
                    self.bot, self.platform
                )
                return
            promote_package_handler = PromotePackage(
                config_dict,
                self.no_dry_run
            )
            promote_package_handler.promote_package()

    def get_config_blog(self):
        """Method to generate config for promoting blog posts"""
        if self.bot == 'pyladies':
            if self.platform == 'bluesky':
                return {
                    "archive": "pyladies_archive_directory_bluesky",
                    "counter": "metadata/pyladies_counter_bluesky.txt",
                    "json_file": "metadata/pyladies_meta_data.json",
                    "client_name": "pyladies_bot",
                    "images": "pyladies_images",
                    "api_base_url": self.platform,
                    "mastodon": None,
                    "gen_ai_support": True,
                    "gemini_model_name": "gemini-2.5-flash",
                    "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("PYLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                }
            if self.platform == 'mastodon':
                return {
                    "archive": "pyladies_archive_directory",
                    "counter": "metadata/pyladies_counter.txt",
                    "json_file": "metadata/pyladies_meta_data.json",
                    "client_name": "pyladies_bot",
                    "images": "pyladies_images",
                    "api_base_url": config.API_BASE_URL,
                    "mastodon": None,
                    "password": os.getenv("PYLADIES_MASTODON_PASSWORD"),
                    "username": os.getenv("PYLADIES_MASTODON_USERNAME"),
                    "access_token": os.getenv("PYLADIES_MASTODON_ACCESS_TOKEN"),
                    "client_cred_file": os.getenv("PYLADIES_BOT_CLIENTCRED_SECRET"),
                    "mastodon_visibility": config.MASTODON_VISIBILITY,
                    "platform": self.platform,
                }

        if self.bot == 'rladies':
            if self.platform == 'bluesky':
                return {
                    "archive": "rladies_archive_directory_bluesky",
                    "counter": "../metadata/rladies_counter_bluesky.txt",
                    "json_file": "../metadata/rladies_meta_data.json",
                    "client_name": "rladies_bot",
                    "images": "rladies_images",
                    "api_base_url": self.platform,
                    "mastodon": None,
                    "gen_ai_support": True,
                    "gemini_model_name": "gemini-2.5-flash",
                    "password": os.getenv("RLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("RLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                }
            if self.platform == 'mastodon':
                return {
                    "archive": "rladies_archive_directory",
                    "counter": "../metadata/rladies_counter.txt",
                    "json_file": "../metadata/rladies_meta_data.json",
                    "client_name": "rladies_bot",
                    "images": "rladies_images",
                    "api_base_url": config.API_BASE_URL,
                    "mastodon": None,
                    "password": os.getenv("RLADIES_MASTODON_PASSWORD"),
                    "username": os.getenv("RLADIES_MASTODON_USERNAME"),
                    "access_token": os.getenv("RLADIES_MASTODON_ACCESS_TOKEN"),
                    "client_cred_file": os.getenv("RLADIES_BOT_CLIENTCRED_SECRET"),
                    "mastodon_visibility": config.MASTODON_VISIBILITY,
                    "platform": self.platform,
                }

        return None

    def get_config_boost(self):
        """Method to generate config for boosting tags"""
        if self.bot == 'pyladies':
            if self.platform == 'bluesky':
                return {
                    "client_name": "pyladies_bot",
                    "mastodon": None,
                    "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("PYLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                    "tags": ["pyladies"],
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
                    "tags": ["pyladies"],
                }

        if self.bot == 'rladies':
            if self.platform == "bluesky":
                return {
                    "client_name": "rladies_bot",
                    "mastodon": None,
                    "password": os.getenv("RLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("RLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                    "tags": ["rladies"],
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
                    "tags": ["rladies"],
                }

        return None

    def get_config_rss(self):
        """Method to generate config for fetching RSS data"""
        if self.bot == 'pyladies':
            return {
                "json_file": "metadata/pyladies_meta_data.json",
                "api_base_url": (
                    "https://github.com/cosimameyer/"
                    "awesome-pyladies-blogs/tree/main/blogs"
                ),
                "github_raw_url": (
                    "https://raw.githubusercontent.com/cosimameyer/"
                    "awesome-pyladies-blogs/main/blogs"
                ),
            }
        if self.bot == 'rladies':
            return {
                "json_file": "metadata/rladies_meta_data.json",
                "api_base_url": (
                    "https://github.com/rladies/"
                    "awesome-rladies-blogs/tree/main/blogs"
                ),
                "github_raw_url": (
                    "https://raw.githubusercontent.com/rladies/"
                    "awesome-rladies-blogs/main/blogs"
                ),
            }
        return None

    def get_config_anniversary(self):
        """Method to get config for promoting anniversaries"""
        if self.bot == 'pyladies':
            if self.platform == 'bluesky':
                return {
                    'client_name': 'pyladies_bot',
                    'api_base_url': self.platform,
                    'mastodon': None,
                    'password': os.getenv('PYLADIES_BSKY_PASSWORD'),
                    'username': os.getenv('PYLADIES_BSKY_USERNAME'),
                    'images': 'anniversary_images',
                    'platform': self.platform,
                }
            if self.platform == 'mastodon':
                return {
                    'client_name': 'pyladies_bot',
                    'api_base_url': config.API_BASE_URL,
                    'mastodon': None,
                    'password': os.getenv('PYLADIES_MASTODON_PASSWORD'),
                    'username': os.getenv('PYLADIES_MASTODON_USERNAME'),
                    'access_token': os.getenv('PYLADIES_MASTODON_ACCESS_TOKEN'),
                    'client_cred_file': os.getenv('PYLADIES_BOT_CLIENTCRED_SECRET'),
                    'images': 'anniversary_images',
                    'platform': self.platform,
                    'mastodon_visibility': config.MASTODON_VISIBILITY,
                }

        if self.bot == 'rladies':
            if self.platform == 'bluesky':
                return {
                    'client_name': 'rladies_bot',
                    'api_base_url': self.platform,
                    'mastodon': None,
                    'password': os.getenv('RLADIES_BSKY_PASSWORD'),
                    'username': os.getenv('RLADIES_BSKY_USERNAME'),
                    'images': 'anniversary_images',
                    'platform': self.platform,
                }
            if self.platform == 'mastodon':
                return {
                    'client_name': 'rladies_bot',
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

        return None

    def get_config_packages(self):
        """Method to generate config for fetching package metadata."""
        if self.bot == 'pyladies':
            return {
                "base_url": (
                    "https://github.com/cosimameyer/"
                    "awesome-pyladies-creations/tree/main/data/packages"
                ),
                "github_raw_url": (
                    "https://raw.githubusercontent.com/cosimameyer/"
                    "awesome-pyladies-creations/main/data/packages"
                ),
                "json_file": "../metadata/pyladies_packages_meta_data.json",
            }
        if self.bot == 'rladies':
            return {
                "base_url": (
                    "https://github.com/rladies/"
                    "awesome-rladies-creations/tree/main/data/packages"
                ),
                "github_raw_url": (
                    "https://raw.githubusercontent.com/rladies/"
                    "awesome-rladies-creations/main/data/packages"
                ),
                "json_file": "../metadata/rladies_packages_meta_data.json",
            }
        return None

    def get_config_package(self):
        """Method to generate config for promoting packages."""
        if self.bot == 'pyladies':
            if self.platform == 'bluesky':
                return {
                    "counter": "../metadata/pyladies_packages_counter_bluesky.txt",
                    "json_file": "../metadata/pyladies_packages_meta_data.json",
                    "client_name": "pyladies_bot",
                    "api_base_url": self.platform,
                    "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("PYLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                }
            if self.platform == 'mastodon':
                return {
                    "counter": "../metadata/pyladies_packages_counter_mastodon.txt",
                    "json_file": "../metadata/pyladies_packages_meta_data.json",
                    "client_name": "pyladies_bot",
                    "api_base_url": config.API_BASE_URL,
                    "password": os.getenv("PYLADIES_MASTODON_PASSWORD"),
                    "username": os.getenv("PYLADIES_MASTODON_USERNAME"),
                    "access_token": os.getenv("PYLADIES_MASTODON_ACCESS_TOKEN"),
                    "client_cred_file": os.getenv("PYLADIES_BOT_CLIENTCRED_SECRET"),
                    "mastodon_visibility": config.MASTODON_VISIBILITY,
                    "platform": self.platform,
                }

        if self.bot == 'rladies':
            if self.platform == 'bluesky':
                return {
                    "counter": "../metadata/rladies_packages_counter_bluesky.txt",
                    "json_file": "../metadata/rladies_packages_meta_data.json",
                    "client_name": "rladies_bot",
                    "api_base_url": self.platform,
                    "password": os.getenv("RLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("RLADIES_BSKY_USERNAME"),
                    "platform": self.platform,
                }
            if self.platform == 'mastodon':
                return {
                    "counter": "../metadata/rladies_packages_counter_mastodon.txt",
                    "json_file": "../metadata/rladies_packages_meta_data.json",
                    "client_name": "rladies_bot",
                    "api_base_url": config.API_BASE_URL,
                    "password": os.getenv("RLADIES_MASTODON_PASSWORD"),
                    "username": os.getenv("RLADIES_MASTODON_USERNAME"),
                    "access_token": os.getenv("RLADIES_MASTODON_ACCESS_TOKEN"),
                    "client_cred_file": os.getenv("RLADIES_BOT_CLIENTCRED_SECRET"),
                    "mastodon_visibility": config.MASTODON_VISIBILITY,
                    "platform": self.platform,
                }

        return None

if __name__ == '__main__':
    debug_bots = DebugBots()
    debug_bots.start_debug()
