"""Promote blog posts"""
import logging
import os
import pickle
import posixpath
import shutil
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from atproto import Client, client_utils, models
import google.generativeai as genai

import feedparser
import requests
from bs4 import BeautifulSoup
from mastodon import Mastodon
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky

import config

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def download_image(url, config_dict):
    """
    Downloads an image from the given URL and saves it locally, 
    organizing files by domain name.

    :param url: string - URL to the image
    :return: string - Path to the saved image
    """
    try:
        # Parse the URL components
        if config_dict["platform"] == "bluesky":
            domain = urlsplit(url).path
            filename = posixpath.basename(domain)
        elif config_dict["platform"] == "mastodon":
            domain = urlsplit(url).netloc
            filename = posixpath.basename(urlsplit(url).path)

        # Create folder structure based on the domain name
        domain_dir = Path(config_dict['images']) / domain
        domain_dir.mkdir(parents=True, exist_ok=True)

        # Full file path for the image
        file_path = domain_dir / filename

        if file_path.is_file():
            logger.info("Image already downloaded: %s", file_path)
            return str(file_path)

        # Set user-agent headers for the request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'
        }

        # Download the image
        logger.info("Downloading image from %s...", url)
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()  # Raises an exception for HTTP errors

        # Save the image to the designated path
        with open(file_path, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)

        logger.info("Image successfully downloaded: %s", file_path)
        return str(file_path)

    except requests.exceptions.RequestException as e:
        logger.error("Failed to download image from %s: %e", url, e)
        return None
    except OSError as e:
        logger.error("File system error while saving image: %s", e)
        return None
    finally:
        response.close() if 'response' in locals() else None


def parse_pub_date(entry):
    """Method to parse the publication date"""
    date_formats = [
        "%a, %d %b %Y %H:%M:%S %z",  # Format 1
        "%a, %d %b %Y %H:%M:%S %Z",  # Format 2
        "%Y-%m-%d",                  # Format 3
        "%Y-%m-%dT%H:%M:%S.%f%Z"     # Format 4
    ]

    pub_date_str = entry.get('pub_date', '')

    for date_format in date_formats:
        try:
            pub_date = datetime.strptime(
                pub_date_str, date_format).replace(tzinfo=None)
            return pub_date  # Return as soon as a valid format is found
        except ValueError:
            logger.info("Failed to parse date with format: %s", date_format)

    # If none of the formats match, use the current date as a fallback
    logger.warning("No matching date format found. Using current date.")
    return datetime.now()  # Fallback value

def define_tags(config_dict, entry):
    if config_dict["client_name"] == 'pyladies_bot':
        tags = '#pyladies #python '
    elif config_dict["client_name"] == 'rladies_bot':
        tags = '#rladies #rstats '
    else:
        logger.info("Bot name not found")
        tags = ''
    
    pub_date = parse_pub_date(entry)

    age_of_post = datetime.now() - pub_date

    if age_of_post.days > 730:
        tags += '#oldiebutgoodie '

    if len(entry['tags']) > 0:
        for tag in entry['tags']:
            if tag.lower() in ['pyladies', 'python', 'rstats', 'rladies']:
                pass
            else:
                tags += f'#{tag.replace(" ", "").replace("-", "").lower()} '

    return tags
    
def get_bluesky_did(platform_user_handle):
    
    url = f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle={platform_user_handle.lstrip('@')}"
    try:
        # Send a GET request to the URL
        response = requests.get(url)
        
        # Check if the request was successful
        if response.status_code == 200:
            # Parse the JSON response
            data = response.json()
            
            # Extract the 'did' field
            did = data.get("did")
            
            # Output the 'did' field
            if did:
                return did
            else:
                logger.info("The 'did' field was not found in the response.")
        else:
            logger.info(f"Failed to retrieve data. Status code: {response.status_code}")

    except requests.RequestException as e:
        logger.info("An error occurred:", e)
        
def build_post_mastodon(basis_text, platform_user_handle, tags, entry, config_dict):
    platform_user_handle = check_platform_handle(platform_user_handle)
    
    if platform_user_handle:
        basis_text += f" ({platform_user_handle}) "
    if config_dict["gen_ai_support"]:
        summarized_blog_post = summarize_text(entry, config_dict)
        if summarized_blog_post:
            basis_text.text('\n\n📖 ')
            basis_text.text(summarized_blog_post)    
    basis_text += f'\n\n🔗 {entry["link"]}\n\n{tags}'
    
    logger.info("*****************************")
    logger.info(basis_text)
    logger.info("*****************************")

    return basis_text


def generate_text_to_summarize(entry):
    text = f"Title: {entry['title']}\nSummary: {entry['summary']}"
    if len(text.split())>700:
        words = text.split()[:700]
        return ' '.join(words)
    return text 


def clean_response(response):
    return ' '.join(response.text.replace("\n", " ").split())


def summarize_text(entry, config_dict):
    text = generate_text_to_summarize(entry)
    model = genai.GenerativeModel(config_dict["gemini_model_name"])
    prompt_parts = ["Summarize the content of the post in maximum 60 characters.",
                    "Be as concise as possible and be engaging.",
                    "Don't repeat the title.",
                    text]
    response = model.generate_content(prompt_parts)
    response_cleaned = clean_response(response)
    safety_ratings = response.candidates[0].safety_ratings
    if all(rating.probability.name == "NEGLIGIBLE" for rating in safety_ratings):
        return response_cleaned
    return ''

def check_platform_handle(platform_user_handle):
    if len(platform_user_handle)>1 and not platform_user_handle.startswith('@'):
        return f"@{platform_user_handle}"
    return platform_user_handle
    
def build_post_bluesky(basis_text, platform_user_handle, tags, entry, config_dict):
    
    text_builder = client_utils.TextBuilder()
    text_builder.text(basis_text)
    
    platform_user_handle = check_platform_handle(platform_user_handle)
    
    if platform_user_handle:
        did = get_bluesky_did(platform_user_handle)
        text_builder.mention(f" ({platform_user_handle})", did)
    if config_dict["gen_ai_support"]:
        summarized_blog_post = summarize_text(entry, config_dict)
        if summarized_blog_post:
            text_builder.text('\n\n📖 ')
            text_builder.text(summarized_blog_post)    
    text_builder.text('\n\n🔗 ')
    text_builder.link(entry["link"], entry["link"])
    text_builder.text('\n\n')
    for tag in tags.split("#"):
        tag_clean = tag.strip()
        if tag_clean:
            text_builder.tag(f"#{tag_clean} ", tag_clean)
    return text_builder

def build_post(entry, feed, config_dict):
    """Take the entry dict and build a post"""
    
    tags = define_tags(config_dict, entry)
    platform = config_dict.get("platform")
    platform_user_handle = feed.get(platform)
    
    basis_text = f'📝 "{entry["title"]}"\n\n👤 {feed["name"]}'
    
    if config_dict["platform"] == "mastodon":
        return build_post_mastodon(basis_text, platform_user_handle, tags, entry, config_dict)
    elif config_dict["platform"] == "bluesky":
        return build_post_bluesky(basis_text, platform_user_handle, tags, entry, config_dict)

def send_post_to_mastodon(en, client, post_txt, config_dict):
    if en['media_content']:
        try:
            logger.info("Uploading media to mastodon")
            filename = download_image(en['media_content'], config_dict)
            media_upload_mastodon = client.media_post(filename)

            if 'alt_text' in en:
                logger.info("adding description")
                client.media_update(media_upload_mastodon,
                                    description=en['alt_text'])

            logger.info("ready to post")
            client.status_post(post_txt, media_ids=media_upload_mastodon)

            logger.info("Posted 🎉")
            return 'success'
        except Exception as e:
            logger.exception(
                "Urg, media could not be printed for %s. Exception: %s", en['link'], e)
            client.status_post(post_txt)
            logger.info("Posted post without image.")
            return 'failed'
    else:
        try:
            client.status_post(post_txt)
            logger.info("Posted 🎉")
            return 'success'
        except Exception as e:
            logger.exception("Urg, exception %s for %s", e, en['link'])
            return 'failed'

def send_post_to_bluesky(en, client, post_txt, embed_external):
    try:
        if embed_external:
            client.send_post(text=post_txt, embed=embed_external)
        else:
            client.send_post(text=post_txt)
        logger.info("Posted 🎉")
        return 'success'
    except Exception as e:
        logger.exception("Urg, exception %s for %s", e, en['link'])
        return 'failed'

def build_embed_external(en, client, config_dict):
    if en['media_content']:
        filename = download_image(en['media_content'], config_dict)
        with open(filename, 'rb') as f:
            img_data = f.read()

        thumb = client.upload_blob(img_data)

        return models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=en['title'],
                description=en['title'],
                uri=en['link'],
                thumb=thumb.blob,
            )
        )
    return None

def send_post(en, feed, config_dict, client):
    """Turn the dict into post text and send the post"""
    result = None
    logger.info(f"Preparing the post on {config_dict['client_name']} ({config_dict['platform']}) ...")
    
    post_txt = build_post(en, feed, config_dict)    
    if config_dict["platform"] == "mastodon":
        result = send_post_to_mastodon(en, client, post_txt, config_dict)
    elif config_dict["platform"] == "bluesky":
        embed_external = build_embed_external(en, client, config_dict)
        result = send_post_to_bluesky(en, client, post_txt, embed_external)
    return result


def load_feed(feed_path, d):
    """Method to load RSS feed"""
    full_fpd = feedparser.parse(feed_path)
    return d + full_fpd.entries


def get_rss_feed_archive(feed):
    """Method to get RSS feed archive content"""
    archive_path = Path(feed['ARCHIVE'][0])
    archive_file = archive_path / 'file.pkl'

    if archive_path.exists():
        try:
            with archive_file.open('rb') as fp:
                rss_feed_archive = pickle.load(fp)
        except (FileNotFoundError, pickle.UnpicklingError):
            rss_feed_archive = {'link': []}
    else:
        if any(domain in feed['ARCHIVE'][0] for domain in ["www.youtube.com", "medium.com"]):
            archive_path = archive_path / \
                feed['name'].lower().replace(' ', '-')

        archive_path.mkdir(parents=True, exist_ok=True)
        rss_feed_archive = {'link': []}

    return rss_feed_archive


def get_number_of_archive_entries(d, rss_feed_archive):
    """ 
    Calculate the number of entries in the feed and archive, ensuring archive 
    structure is correct.
    """
    number_of_entries_feed = len(d)

    if 'link' in rss_feed_archive and isinstance(rss_feed_archive['link'], list):
        number_of_entries_archive = len(set(rss_feed_archive['link']))
    else:
        # Fix the archive structure if 'link' key is missing or incorrect
        rss_feed_archive = {'link': list(set(rss_feed_archive))}
        number_of_entries_archive = len(rss_feed_archive['link'])

    return rss_feed_archive, number_of_entries_archive, number_of_entries_feed


def get_folder_path(feed, ARCHIVE):
    """Method to identify folder path"""

    def adjust_archive_path(base_path, domain, feed_name):
        """
        Helper function to clean up path construction for YouTube and Medium
        """
        feed_name_slug = feed_name.lower().replace(' ', '-')
        if "www.youtube.com" in domain or "medium.com" in domain:
            return base_path / feed_name_slug / feed_name_slug
        return base_path

    rss_feeds = feed.get('rss_feed', [])
    archive_paths = []

    if len(rss_feeds) > 1:
        for rss_feed in rss_feeds:
            domain = urlsplit(rss_feed).netloc
            folder_path = Path(ARCHIVE) / domain
            archive_paths.append(str(folder_path))

    elif len(rss_feeds) == 1:
        domain = urlsplit(rss_feeds[0]).netloc
        folder_path = Path(ARCHIVE) / domain
        folder_path = adjust_archive_path(folder_path, domain, feed['name'])
        archive_paths.append(str(folder_path))

    feed['ARCHIVE'] = archive_paths
    return feed


def process_feed(feed, count_post, PROCESS_IMAGES, NO_DRY_RUN, 
                 config_dict, client):
    """
    Process the RSS feed and generate a post for any entry we haven't yet seen
    """
    logger.info("====================================================")
    logger.info("Begin processing of feeds from %s (%s)",
                feed['name'], feed['rss_feed'])

    feed = get_folder_path(feed, config_dict["archive"])

    d = []

    for feed_path in feed['rss_feed']:
        # if "medium.com" in feed_path:
        #     parsed_url = urlparse(feed_path)
        #     subdomain = parsed_url.hostname.split('.')[0]
        #     feed_path = f"https://medium.com/feed/@{subdomain}"
        # # Load the feed
        try:
            d = load_feed(feed_path, d)
            rss_feed_archive = get_rss_feed_archive(feed)
            # Identify number of entries
            (
                rss_feed_archive,
                number_of_entries_archive,
                number_of_entries_feed
            ) = get_number_of_archive_entries(d, rss_feed_archive)
            # If there are more entries, go through the list:

            feed_config = {
                'rss_feed_archive': rss_feed_archive,
                'number_of_entries_feed': number_of_entries_feed,
                'feed': feed,
                'd': d
            }

            if number_of_entries_feed > number_of_entries_archive:
                count_post = _process_feed(
                    PROCESS_IMAGES,
                    NO_DRY_RUN,
                    config_dict,
                    client,
                    count_post,
                    feed_config
                )
                logger.info("New RSS feeds are successfully loaded and "
                            "processed.")
                return count_post
            logger.info("Maximum number of posts is already posted.")
            return count_post
        except Exception as e:
            logger.info("🚨 Feed for %s not available because %s", feed_path, e)
            return count_post


def _save_rss_feed_archive(feed, rss_feed_archive):
    """ Save RSS feed archive to a file """
    archive_path = os.path.join(feed['ARCHIVE'][0], 'file.pkl')
    with open(archive_path, 'wb') as fp:
        pickle.dump(rss_feed_archive, fp)
    logger.info("Archive for %s updated successfully.", feed['name'])


def _get_media_content(entry):
    """ Extract media content from an RSS entry """
    en = {}
    if 'www.youtube.com' in entry.link:
        en['media_content'] = f"http://img.youtube.com/vi/{entry.id.replace('yt:video:', '')}/hqdefault.jpg"
    elif 'media_content' in entry:
        en['media_content'] = entry.media_content[0]['url']
    else:
        soup = BeautifulSoup(entry.summary, "html.parser")
        img_url = [img['src']
                   for img in soup.find_all('img') if img.has_attr('src')]
        alt_text = [img['alt']
                    for img in soup.find_all('img') if img.has_attr('alt')]
        if img_url:
            en['media_content'] = img_url[0]
        if alt_text:
            en['alt_text'] = alt_text[0] if alt_text else ''
    return en


def _process_feed(PROCESS_IMAGES,
                  NO_DRY_RUN,
                  config_dict,
                  client,
                  count_post,
                  feed_config):
    """ Process RSS feed entries and send posts """
    count = 0
    count_fails = 0
    result = None
    for _, entry in enumerate(feed_config['d']):
        if count >= 1:  # Limit to 1 post per run
            break
        elif count_fails >= 1:
            break

        en = {
            'title': entry.title,
            'link': entry.link,
            'pub_date': entry.published,
            'tags': [tag['term'] for tag in getattr(entry, 'tags', [])],
            'media_content': [],
            'summary': entry.summary
        }

        if not en['tags'] and 'category' in entry:
            en['tags'].append(entry.category)

        if PROCESS_IMAGES:
            en.update(_get_media_content(entry))

        if en['link'] not in feed_config['rss_feed_archive']['link']:
            feed_config['rss_feed_archive']['link'].append(en['link'])
            if NO_DRY_RUN:
                result = send_post(en, feed_config['feed'], config_dict, client)
            if result=='success':
                count_post += 1
                count += 1
                time.sleep(1)
            elif result=='failed':
                count_fails += 1
                time.sleep(1)

    if NO_DRY_RUN:
        if result=='success':
            _save_rss_feed_archive(feed_config['feed'],
                                feed_config['rss_feed_archive'])

    return count_post


def promote_blog_post(config_dict=None, NO_DRY_RUN=True):
    """Core method to promote blog post"""

    PROCESS_IMAGES = False

    if (config_dict is None) and (NO_DRY_RUN):
        config_dict = {
            "platform": os.getenv("PLATFORM"),
            "archive": os.getenv("ARCHIVE_DIRECTORY"),
            "images": os.getenv("IMAGES"),
            "counter": os.getenv("COUNTER"),
            "password": os.getenv("PASSWORD"),
            "username": os.getenv("USERNAME"),
            "client_name": os.getenv("CLIENT_NAME"),
            "pickle_file": os.getenv("PICKLE_FILE"),
            "gen_ai_support": True,
            "gemini_api_key": os.getenv("GEMINI_API_KEY"),
            "gemini_model_name": "gemini-1.5-flash"
        }
        if config_dict["platform"] == "mastodon":
            config_dict["api_base_url"] = config.API_BASE_URL
            config_dict["mastodon_visibility"] = config.MASTODON_VISIBILITY
            config_dict["client_id"] = os.getenv("CLIENT_ID")
            config_dict["client_secret"] = os.getenv("CLIENT_SECRET")
            config_dict["access_token"] = os.getenv("ACCESS_TOKEN")
            config_dict["client_cred_file"] = os.getenv('BOT_CLIENTCRED_SECRET')
        else:
            config_dict["api_base_url"] = "bluesky"
        
        if config_dict["gen_ai_support"]:
            genai.configure(api_key=config_dict["gemini_api_key"])
        
    if NO_DRY_RUN:
        logger.info("")
        logger.info("Initializing %s Bot", config_dict["client_name"])
        logger.info("%s", "=" * (len(config_dict["client_name"]) + 17))
        logger.info(" > Connecting to %s", config_dict["api_base_url"])
        
        if config_dict["platform"] == "mastodon":
            _, client = login_mastodon(config_dict)
        elif config_dict["platform"] == "bluesky":
            client = login_bluesky(config_dict)
    else:
        client = None

    with open(config_dict["pickle_file"], 'rb') as fp:
        logger.info(
            "================================================================")
        FEEDS = pickle.load(fp)
        logger.info('Meta data was successfully loaded')
        logger.info(
            "================================================================")

    # Initiate count to post a maximum of 2 posts per run
    count_post = 0

    with open(config_dict["counter"], 'r') as f:
        feed_name = f.read()

    # Drop empty rss_feeds
    FEEDS = [x for x in FEEDS if x['rss_feed'] != '']

    if NO_DRY_RUN:
        for feed in FEEDS:
            if ((feed_name in (feed['name'], '\n', ''))
                and (len(feed['rss_feed']) > 0)
                    and (feed['rss_feed'] != [None])):
                if (count_post == 0) & (feed['name'] == FEEDS[-1]['name']):
                    count_post = process_feed(feed,
                                            count_post,
                                            PROCESS_IMAGES,
                                            NO_DRY_RUN,
                                            config_dict,
                                            client)

                    # Add the feed_name
                    if feed['name'] == FEEDS[-1]['name']:
                        new_feed = FEEDS[0]
                        count_post = process_feed(new_feed,
                                                count_post,
                                                PROCESS_IMAGES,
                                                NO_DRY_RUN,
                                                config_dict,
                                                client)

                        logger.info(
                            "Successfully promoted blog posts. "
                            "Thank you and see you next time!")
                        feed_name = FEEDS[1]['name']
                        with open(config_dict["counter"], 'w') as txt_file:
                            txt_file.write(feed_name)
                        logger.info(
                            "================================================")
                        break

                elif count_post < 2:
                    count_post = process_feed(feed,
                                            count_post,
                                            PROCESS_IMAGES,
                                            NO_DRY_RUN,
                                            config_dict,
                                            client)

                    # Add the feed_name
                    feed_name = ''
                    if feed['name'] == FEEDS[-1]['name']:
                        with open(config_dict["counter"], 'w') as txt_file:
                            txt_file.write(feed['name'])
                    logger.info(
                        "=================================================================")

                else:
                    logger.info(
                        "Successfully promoted blog posts. "
                        "Thank you and see you next time!")
                    feed_name = feed['name']
                    with open(config_dict["counter"], 'w') as txt_file:
                        txt_file.write(feed_name)
                    break
    else:
        for feed in FEEDS:
            count_post = process_feed(feed,
                                    count_post,
                                    PROCESS_IMAGES,
                                    NO_DRY_RUN,
                                    config_dict,
                                    client)


if __name__ == "__main__":
    promote_blog_post(config_dict=None, NO_DRY_RUN=True)
