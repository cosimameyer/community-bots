""" This script aims at making debugging easier """
# import sys
import os

# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from promote_blog_post import promote_blog_post
from get_rss_data import get_rss_data
from boost_tags import boost_tags
from promote_anniversaries import promote_anniversary

def get_config_blog(bot, platform):
    """Method to generate config for promoting blog posts"""
    if bot == 'pyladies':
        if platform == "bluesky":
            return {"archive": "pyladies_archive_directory_bluesky",
                    "counter": "pyladies_counter_bluesky.txt",
                    "pickle_file": "pyladies_meta_data.pkl",
                    "client_name": "pyladies_bot",
                    "images": "pyladies_images",
                    "api_base_url": platform,
                    "mastodon": None,
                    "gen_ai_support": True,
                    "gemini_model_name": "gemini-1.5-flash",
                    "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("PYLADIES_BSKY_USERNAME"),
                    "platform": platform}
        return {"archive": "pyladies_archive_directory",
                "counter": "pyladies_counter.txt",
                "pickle_file": "pyladies_meta_data.pkl",
                "client_name": "pyladies_bot",
                "mastodon": None}
    elif bot == 'rladies':
        if platform == "bluesky":
            return {"archive": "rladies_archive_directory_bluesky",
                    "counter": "rladies_counter_bluesky.txt",
                    "pickle_file": "rladies_meta_data.pkl",
                    "client_name": "rladies_bot",
                    "images": "rladies_images",
                    "api_base_url": platform,
                    "mastodon": None,
                    "password": os.getenv("RLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("RLADIES_BSKY_USERNAME"),
                    "platform": platform}

def get_config_boost(bot, platform):
    """Method to generate config for boosting tags"""
    if bot == 'pyladies':
        return {"client_name": "pyladies_bot",
                "mastodon": None}
    elif bot == 'rladies':
        if platform == "bluesky":
            return {"client_name": "rladies_bot",
                    "api_base_url": platform,
                    "mastodon": None,
                    "password": os.getenv("PASSWORD"),
                    "username": os.getenv("USERNAME"),
                    "platform": platform,
                    "tags": "rladies"}

def get_config_rss(bot):
    """Method for generating config for extracting RSS info"""
    if bot == 'pyladies':
        return {"api_base_url": "https://github.com/cosimameyer/awesome-pyladies-blogs/tree/main/blogs",
            "github_raw_url": "https://raw.githubusercontent.com/cosimameyer/awesome-pyladies-blogs/main/blogs",
            "pickle_file": "pyladies_meta_data.pkl"}
    elif bot == 'rladies':
        return {"api_base_url": "https://github.com/rladies/awesome-rladies-blogs/tree/main/blogs",
                "github_raw_url": "https://raw.githubusercontent.com/rladies/awesome-rladies-blogs/main/blogs",
                "pickle_file": "rladies_meta_data.pkl"}

def get_config_anniversary(bot, platform):
    if bot == 'pyladies':
        if platform == "bluesky":
            return {"client_name": "pyladies_bot",
                    "api_base_url": platform,
                    "mastodon": None,
                    "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("PYLADIES_BSKY_USERNAME"),
                    "images": "anniversary_images",
                    "platform": platform}
        return {'client_name': 'pyladies_bot',
                'mastodon': None}
    elif bot == 'rladies':
        if platform == "bluesky":
            return {"client_name": "rladies_bot",
                    "api_base_url": platform,
                    "mastodon": None,
                    "password": os.getenv("RLADIES_BSKY_PASSWORD"),
                    "username": os.getenv("RLADIES_BSKY_USERNAME"),
                    "images": "anniversary_images",
                    "platform": platform}

if __name__ == "__main__":
    # Set config
    BOT = 'pyladies' # ('pyladies' or 'rladies')
    WHAT = 'blog' # ('blog' or 'boost' or 'rss' or 'anniversary)
    PLATFORM = 'bluesky' # ('bluesky' or 'mastodon')
    NO_DRY_RUN = True # False is required for debugging

    if WHAT == 'blog':
        config_dict = get_config_blog(BOT, PLATFORM)
        promote_blog_post(config_dict, NO_DRY_RUN)
    # DEBUG promote_blog_post
    elif WHAT == 'rss':
        config_dict = get_config_rss(BOT)
        get_rss_data(config_dict, NO_DRY_RUN)
        
    elif WHAT == 'boost':
        config_dict = get_config_boost(BOT, PLATFORM)
        boost_tags(config_dict, NO_DRY_RUN)
    
    elif WHAT == 'anniversary':
        config_dict = get_config_anniversary(BOT, PLATFORM)
        promote_anniversary(config_dict, NO_DRY_RUN)
        