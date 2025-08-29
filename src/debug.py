""" A script to make debugging easier for various social media bot modules. """
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
        module_name (str): The module to debug ('blog', 'rss', 'boost_tags', 'boost_mentions', 'anniversary').
        platform (str): The social media platform ('bluesky' or 'mastodon').
        no_dry_run (bool): If True, performs the action without a dry run.
    """

    def __init__(self):
        """Initializes DebugBots with default debugging parameters."""
        self.bot = 'rladies'  # 'pyladies' or 'rladies'
        self.module_name = 'blog'  # 'blog' or 'boost_tags' or 'rss' or 'anniversary' or 'boost_mentions'
        self.platform = 'bluesky'  # 'bluesky' or 'mastodon'
        self.no_dry_run = False

    def _get_config(self, module_type: str) -> dict:
        """
        Generates a configuration dictionary based on bot, platform, and module type.

        Args:
            module_type (str): The type of module to get the config for.

        Returns:
            dict: The configuration dictionary for the specified bot and module.

        Raises:
            ValueError: If an invalid bot or platform is specified.
        """
        base_configs = {
            'pyladies': {
                'client_name': 'pyladies_self.bot',
                'mastodon': None,
            },
            'rladies': {
                'client_name': 'rladies_self.bot',
                'mastodon': None,
            },
        }

        platform_configs = {
            'bluesky': {
                'pyladies': {
                    'password': os.getenv('PYLADIES_BSKY_PASSWORD'),
                    'username': os.getenv('PYLADIES_BSKY_USERNAME'),
                },
                'rladies': {
                    'password': os.getenv('RLADIES_BSKY_PASSWORD'),
                    'username': os.getenv('RLADIES_BSKY_USERNAME'),
                },
            }
        }

        module_configs = {
            'blog': {
                'pyladies': {
                    'archive': 'pyladies_archive_directory_bluesky' if self.platform == 'bluesky' else 'pyladies_archive_directory',
                    'counter': 'metadata/pyladies_counter_bluesky.txt' if self.platform == 'bluesky' else 'pyladies_counter.txt',
                    'json_file': 'metadata/pyladies_meta_data.json',
                    'images': 'pyladies_images',
                    'gen_ai_support': True,
                    'gemini_model_name': 'gemini-2.5-flash',
                },
                'rladies': {
                    'archive': 'rladies_archive_directory_bluesky' if self.platform == 'bluesky' else 'rladies_archive_directory',
                    'counter': '../metadata/rladies_counter_bluesky.txt' if self.platform == 'bluesky' else 'rladies_counter.txt',
                    'json_file': '../metadata/rladies_meta_data.json',
                    'images': 'rladies_images',
                },
            },
            'boost_tags': {
                'rladies': {
                    'tags': 'rladies',
                },
            },
            'rss': {
                'pyladies': {
                    'api_base_url': 'https://github.com/cosimameyer/awesome-pyladies-blogs/tree/main/blogs',
                    'github_raw_url': 'https://raw.githubusercontent.com/cosimameyer/awesome-pyladies-blogs/main/blogs',
                    'json_file': 'pyladies_meta_data.json',
                },
                'rladies': {
                    'api_base_url': 'https://github.com/rladies/awesome-rladies-blogs/tree/main/blogs',
                    'github_raw_url': 'https://raw.githubusercontent.com/rladies/awesome-rladies-blogs/main/blogs',
                    'json_file': 'rladies_meta_data.json',
                },
            },
            'anniversary': {
                'pyladies': {
                    'images': 'anniversary_images',
                },
                'rladies': {
                    'images': 'anniversary_images',
                },
            },
        }

        config = base_configs.get(self.bot, {})
        config.update(module_configs.get(module_type, {}).get(self.bot, {}))

        if self.platform == 'bluesky':
            config.update({'api_base_url': self.platform, 'platform': self.platform})
            platform_specifics = platform_configs.get(self.platform, {}).get(self.bot, {})
            config.update(platform_specifics)

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

        handler_class = handlers.get(self.module_name)
        if not handler_class:
            raise ValueError(f'Invalid module_name: {self.module_name}')

        config_dict = self._get_config(self.module_name)
        handler = handler_class(config_dict, self.no_dry_run)

        # Call the appropriate method based on the module name
        method_map = {
            'blog': handler.promote_blog_post,
            'rss': handler.get_rss_data,
            'boost_tags': handler.boost_tags,
            'boost_mentions': handler.boost_mentions,
            'anniversary': handler.promote_anniversary,
        }

        method_to_call = method_map.get(self.module_name)
        if not method_to_call:
            raise NotImplementedError(f'Handler for {self.module_name} not implemented.')

        method_to_call()


if __name__ == '__main__':
    debugger = DebugBots()
    debugger.start_debug()