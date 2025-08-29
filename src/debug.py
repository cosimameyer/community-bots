""" This script aims at making debugging easier """
import os
from dotenv import load_dotenv

from promote_blog_post import PromoteBlogPost
from get_rss_data import RSSData
from boost_tags import BoostTags
from promote_anniversaries import PromoteAnniversary
from boost_mentions import BoostMentions

load_dotenv()


class DebugBots:
    """
    A class for debugging various social media bot modules by
    centralizing configuration and execution logic.

    Attributes:
        bot (str): The bot to debug ('rladies' or 'pyladies').
        module_name (str): The module to debug ('blog', 'rss', 'boost_tags',
                           'boost_mentions', 'anniversary').
        platform (str): The social media platform ('bluesky' or 'mastodon').
        no_dry_run (bool): If True, performs the action without a dry run.
    """

    def __init__(self):
        """Initializes DebugBots with default debugging parameters."""
        self.bot = 'rladies'  # 'pyladies' or 'rladies'
        self.module_name = 'blog'  # 'blog', 'boost_tags', 'rss', 'anniversary', 'boost_mentions'
        self.platform = 'bluesky'  # 'bluesky' or 'mastodon'
        self.no_dry_run = False

    def _get_config(self) -> dict:
        """
        Generates a configuration dictionary based on bot, platform,
        and module type.

        Returns:
            dict: The configuration dictionary for the specified bot and module.
        """
        # Centralized configuration data
        config_data = {
            'pyladies': {
                'bluesky': {
                    'blog': {
                        'archive': 'pyladies_archive_directory_bluesky',
                        'counter': 'metadata/pyladies_counter_bluesky.txt',
                        'json_file': 'metadata/pyladies_meta_data.json',
                        'images': 'pyladies_images',
                        'gen_ai_support': True,
                        'gemini_model_name': 'gemini-2.5-flash',
                        'password': os.getenv('PYLADIES_BSKY_PASSWORD'),
                        'username': os.getenv('PYLADIES_BSKY_USERNAME'),
                    },
                    'anniversary': {
                        'password': os.getenv('PYLADIES_BSKY_PASSWORD'),
                        'username': os.getenv('PYLADIES_BSKY_USERNAME'),
                        'images': 'anniversary_images',
                    },
                },
                'mastodon': {
                    'blog': {
                        'archive': 'pyladies_archive_directory',
                        'counter': 'pyladies_counter.txt',
                        'json_file': 'metadata/pyladies_meta_data.json',
                    },
                },
                'rss': {
                    'api_base_url': 'https://github.com/cosimameyer/awesome-pyladies-blogs/tree/main/blogs',
                    'github_raw_url': 'https://raw.githubusercontent.com/cosimameyer/awesome-pyladies-blogs/main/blogs',
                    'json_file': 'pyladies_meta_data.json',
                },
                'shared': {
                    'client_name': 'pyladies_self.bot',
                    'mastodon': None,
                },
            },
            'rladies': {
                'bluesky': {
                    'blog': {
                        'archive': 'rladies_archive_directory_bluesky',
                        'counter': '../metadata/rladies_counter_bluesky.txt',
                        'json_file': '../metadata/rladies_meta_data.json',
                        'images': 'rladies_images',
                        'password': os.getenv('RLADIES_BSKY_PASSWORD'),
                        'username': os.getenv('RLADIES_BSKY_USERNAME'),
                    },
                    'boost_tags': {
                        'password': os.getenv('RLADIES_BSKY_PASSWORD'),
                        'username': os.getenv('RLADIES_BSKY_USERNAME'),
                        'tags': 'rladies',
                    },
                    'boost_mentions': {
                        'password': os.getenv('RLADIES_BSKY_PASSWORD'),
                        'username': os.getenv('RLADIES_BSKY_USERNAME'),
                        'tags': 'rladies',
                    },
                    'anniversary': {
                        'password': os.getenv('RLADIES_BSKY_PASSWORD'),
                        'username': os.getenv('RLADIES_BSKY_USERNAME'),
                        'images': 'anniversary_images',
                    },
                },
                'rss': {
                    'api_base_url': 'https://github.com/rladies/awesome-rladies-blogs/tree/main/blogs',
                    'github_raw_url': 'https://raw.githubusercontent.com/rladies/awesome-rladies-blogs/main/blogs',
                    'json_file': 'rladies_meta_data.json',
                },
                'shared': {
                    'client_name': 'rladies_self.bot',
                    'mastodon': None,
                },
            },
        }

        # Initialize config with shared data
        config = config_data.get(self.bot, {}).get('shared', {}).copy()

        # Update with platform-specific and module-specific data
        platform_data = config_data.get(self.bot, {}).get(self.platform, {})
        config.update(platform_data.get(self.module_name, {}))
        config.update(platform_data.get('shared', {}))

        # Add platform if it's bluesky
        if self.platform == 'bluesky':
            config['platform'] = self.platform
            config['api_base_url'] = self.platform

        return config

    def start_debug(self):
        """
        Executes the debugging process for the specified module.

        The method dynamically selects and initializes the correct handler class
        based on the 'module_name' attribute and calls its main method.
        """
        handlers = {
            'blog': PromoteBlogPost,
            'rss': RSSData,
            'boost_tags': BoostTags,
            'boost_mentions': BoostMentions,
            'anniversary': PromoteAnniversary,
        }

        if self.module_name not in handlers:
            raise ValueError(f'Invalid module_name: {self.module_name}')

        config_dict = self._get_config()
        handler_class = handlers[self.module_name]
        handler = handler_class(config_dict, self.no_dry_run)

        # Map module names to their corresponding methods
        method_map = {
            'blog': handler.promote_blog_post,
            'rss': handler.get_rss_data,
            'boost_tags': handler.boost_tags,
            'boost_mentions': handler.boost_mentions,
            'anniversary': handler.promote_anniversary,
        }

        method_to_call = method_map.get(self.module_name)
        if not method_to_call:
            raise NotImplementedError(
                f'Handler for {self.module_name} not implemented.'
            )

        method_to_call()


if __name__ == '__main__':
    debugger = DebugBots()
    debugger.start_debug()