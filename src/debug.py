""" This script aims at making debugging easier """
import os
from dotenv import load_dotenv

from promote_blog_post import PromoteBlogPost
from get_rss_data import RSSData
from boost_tags import BoostTags
from promote_anniversaries import PromoteAnniversary
from boost_mentions import BoostMentions

load_dotenv()


class DebugBots():
    """
    Class to handle debugging of all modules.
    """
    def __init__(self):
        self.bot = 'pyladies'  # 'pyladies' or 'rladies'
        self.what_to_debug = 'blog'  # 'blog' or 'boost_tags' or 'rss' or 'anniversary
        self.platform = 'bluesky'  # 'bluesky' or 'mastodon'
        self.no_dry_run = True

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
            if self.platform == "bluesky":
                return {"archive": "pyladies_archive_directory_bluesky",
                        "counter": "pyladies_counter_bluesky.txt",
                        "pickle_file": "pyladies_meta_data.pkl",
                        "client_name": "pyladies_self.bot",
                        "images": "pyladies_images",
                        "api_base_url": self.platform,
                        "mastodon": None,
                        "gen_ai_support": True,
                        "gemini_model_name": "gemini-1.5-flash",
                        "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
                        "username": os.getenv("PYLADIES_BSKY_USERNAME"),
                        "self.platform": self.platform}
            return {"archive": "pyladies_archive_directory",
                    "counter": "pyladies_counter.txt",
                    "pickle_file": "pyladies_meta_data.pkl",
                    "client_name": "pyladies_self.bot",
                    "mastodon": None}
        elif self.bot == 'rladies':
            if self.platform == "bluesky":
                return {"archive": "rladies_archive_directory_bluesky",
                        "counter": "rladies_counter_bluesky.txt",
                        "pickle_file": "rladies_meta_data.pkl",
                        "client_name": "rladies_self.bot",
                        "images": "rladies_images",
                        "api_base_url": self.platform,
                        "mastodon": None,
                        "password": os.getenv("RLADIES_BSKY_PASSWORD"),
                        "username": os.getenv("RLADIES_BSKY_USERNAME"),
                        "self.platform": self.platform}

    def get_config_boost(self):
        """Method to generate config for boosting tags"""
        if self.bot == 'pyladies':
            return {"client_name": "pyladies_self.bot",
                    "mastodon": None}
        elif self.bot == 'rladies':
            if self.platform == "bluesky":
                return {"client_name": "rladies_self.bot",
                        "api_base_url": self.platform,
                        "mastodon": None,
                        "password": os.getenv("PASSWORD"),
                        "username": os.getenv("USERNAME"),
                        "self.platform": self.platform,
                        "tags": "rladies"}

    def get_config_rss(self):
        """Method for generating config for extracting RSS info"""
        if self.bot == 'pyladies':
            return {
                "api_base_url": "https://github.com/cosimameyer/awesome-pyladies-blogs/tree/main/blogs",
                "github_raw_url": "https://raw.githubusercontent.com/cosimameyer/awesome-pyladies-blogs/main/blogs",
                "pickle_file": "pyladies_meta_data.pkl"
            }
        elif self.bot == 'rladies':
            return {
                "api_base_url": "https://github.com/rladies/awesome-rladies-blogs/tree/main/blogs",
                "github_raw_url": "https://raw.githubusercontent.com/rladies/awesome-rladies-blogs/main/blogs",
                "pickle_file": "rladies_meta_data.pkl"
            }

    def get_config_anniversary(self):
        """
        Method to get all required parameters for the config_dict for the
        promote_anniversaries approach.
        """
        if self.bot == 'pyladies':
            if self.platform == "bluesky":
                return {"client_name": "pyladies_self.bot",
                        "api_base_url": self.platform,
                        "mastodon": None,
                        "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
                        "username": os.getenv("PYLADIES_BSKY_USERNAME"),
                        "images": "anniversary_images",
                        "self.platform": self.platform}
            return {'client_name': 'pyladies_self.bot',
                    'mastodon': None}
        elif self.bot == 'rladies':
            if self.platform == "bluesky":
                return {"client_name": "rladies_self.bot",
                        "api_base_url": self.platform,
                        "mastodon": None,
                        "password": os.getenv("RLADIES_BSKY_PASSWORD"),
                        "username": os.getenv("RLADIES_BSKY_USERNAME"),
                        "images": "anniversary_images",
                        "self.platform": self.platform}

if __name__ == "__main__":
    debug_bots = DebugBots()
    debug_bots.start_debug()
