"""Promote blog posts"""
import logging
import os
import json
import posixpath
import shutil
import time
from datetime import datetime
from dateutil import parser as dateutil_parser
from pathlib import Path
from urllib.parse import urlsplit
from atproto import client_utils, models
from google import genai

import feedparser
import requests
from bs4 import BeautifulSoup
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky

import config

CONTENT_TYPE_EMOJI = {
    "blog": "📝",
    "youtube": "📺",
    "podcast": "🎙️",
}


class PromoteBlogPost():
    """
    Class to handle promoting blog posts by the community bots.
    """
    def __init__(self, config_dict=None, no_dry_run=True):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

        self.process_images = False
        self.no_dry_run = no_dry_run
        self.config_dict = config_dict

    def get_config(self):
        """
        Get config file
        """
        if (self.config_dict is None) and (self.no_dry_run):
            self.config_dict = {
                "platform": os.getenv("PLATFORM"),
                "archive": os.getenv("ARCHIVE_DIRECTORY"),
                "images": os.getenv("IMAGES"),
                "counter": self._ensure_metadata_prefix(
                    os.getenv("COUNTER", "")
                ),
                "password": os.getenv("PASSWORD"),
                "username": os.getenv("USERNAME"),
                "client_name": os.getenv("CLIENT_NAME"),
                "json_file": self._ensure_metadata_prefix(
                    os.getenv("JSON_FILE", "")
                ),
                "gen_ai_support": bool(os.getenv("GEMINI_API_KEY")),
                "gemini_api_key": os.getenv("GEMINI_API_KEY"),
                "gemini_model_name": "gemini-3.1-flash-lite"
            }
            if self.config_dict["platform"] == "mastodon":
                self.config_dict["api_base_url"] = config.API_BASE_URL
                self.config_dict["mastodon_visibility"] = (
                    config.MASTODON_VISIBILITY
                )
                self.config_dict["client_id"] = os.getenv("CLIENT_ID")
                self.config_dict["client_secret"] = os.getenv("CLIENT_SECRET")
                self.config_dict["access_token"] = os.getenv("ACCESS_TOKEN")
                self.config_dict["client_cred_file"] = os.getenv(
                    'BOT_CLIENTCRED_SECRET'
                )
            else:
                self.config_dict["api_base_url"] = "bluesky"

        else:
            self.config_dict['json_file'] = self._ensure_metadata_prefix(
                self.config_dict.get('json_file')
            )
            self.config_dict['counter'] = self._ensure_metadata_prefix(
                self.config_dict.get('counter')
            )

        if self.config_dict.get('gen_ai_support'):
            self.genai_client = genai.Client(api_key=self.config_dict.get('gemini_api_key'))

    def promote_blog_post(self):
        """Core method to promote blog post"""

        self.get_config()

        client_name = self.config_dict.get('client_name', 'unknown')
        self.logger.info('Initializing %s Bot', client_name)
        self.logger.info("=" * (len(client_name) + 17))
        self.logger.info(
            " > Connecting to %s",
            self.config_dict.get('api_base_url', '')
        )

        if self.no_dry_run:
            if self.config_dict["platform"] == "mastodon":
                _, client = login_mastodon(self.config_dict)
            elif self.config_dict["platform"] == "bluesky":
                client = login_bluesky(self.config_dict)
            else:
                client = None
        else:
            client = None

        feeds = self.read_metadata_json()
        counter_name = self.read_counter_name()

        # Initiate count to post a maximum of 2 posts per run
        count_post = 0

        # Drop empty rss_feeds
        feeds = [x for x in feeds if x['rss_feed']]

        if self.no_dry_run:
            self.process_feeds(feeds, counter_name, count_post, client)
        else:
            for feed in feeds:
                if count_post >= 2:
                    break
                count_post = self.process_feed(
                    feed,
                    count_post,
                    client
                )

    def process_feeds(self, feeds, counter_name, count_post, client):
        """
        Method to handle processing of all feeds.
        """
        n = len(feeds)
        if n == 0:
            return

        start_index = 0
        for i, f in enumerate(feeds):
            if counter_name in (f['name'], '\n', ''):
                start_index = i
                break

        next_index = start_index

        for offset in range(n):
            idx = (start_index + offset) % n
            feed = feeds[idx]

            if len(feed['rss_feed']) == 0 or feed['rss_feed'] == [None]:
                continue

            if count_post >= 2:
                next_index = idx
                self.logger.info(
                    "Successfully promoted blog posts. "
                    "Thank you and see you next time!")
                break

            count_post = self.process_feed(feed, count_post, client)
            next_index = (idx + 1) % n
            self.logger.info("=========================================")
        else:
            if count_post >= 2:
                self.logger.info(
                    "Successfully promoted blog posts. "
                    "Thank you and see you next time!")

        if count_post > 0:
            self.update_counter(feeds[next_index]['name'])
        else:
            self.logger.info(
                "No posts made this run — counter left unchanged."
            )

    def update_counter(self, counter_name):
        """
        Update counter name
        """
        with open(
            self.config_dict["counter"],
            'w',
            encoding='utf-8'
        ) as txt_file:
            txt_file.write(counter_name)

    def read_counter_name(self):
        """
        Read counter name from txt file
        """
        try:
            with open(self.config_dict["counter"], 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def read_metadata_json(self):
        """
        Read metadata JSON file
        """
        with open(self.config_dict["json_file"], 'rb') as fp:
            self.logger.info(
                "============================================="
            )
            feeds = json.load(fp)
            self.logger.info('Meta data was successfully loaded')
            self.logger.info(
                "============================================="
            )
            return feeds

    @staticmethod
    def _ensure_metadata_prefix(value: str, prefix="metadata/") -> str:
        """
        Ensures that a string contains "metadata/" as a proper path segment.
        Handles bare names ("counter.txt" → "metadata/counter.txt") while
        leaving already-prefixed paths intact, including relative ones
        ("../metadata/counter.txt" is returned unchanged).
        """
        if not value:
            return value
        segments = value.replace("\\", "/").split("/")
        if prefix.rstrip("/") in segments:
            return value
        return prefix + value

    def download_image(self, url: str):
        """
        Downloads an image from the given URL and saves it locally,
        organizing files by domain name.
        """
        try:
            filename = ''
            # Parse the URL components
            parsed = urlsplit(url)
            domain = parsed.netloc
            safe_filename = posixpath.basename(parsed.path) or "image"
            if self.config_dict["platform"] == "bluesky":
                filename = safe_filename
            elif self.config_dict["platform"] == "mastodon":
                filename = safe_filename

            # Create folder structure based on the domain name
            domain_dir = Path(self.config_dict['images']) / domain
            domain_dir.mkdir(parents=True, exist_ok=True)

            # Full file path for the image (always under images/domain/)
            file_path = domain_dir / filename

            if file_path.is_file():
                self.logger.info("Image already downloaded: %s", file_path)
                return str(file_path)

            # Set user-agent headers for the request
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) '
                    'Gecko/20100101 Firefox/20.0'
                )
            }

            # Download the image
            self.logger.info("Downloading image from %s...", url)
            response = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=15
            )
            response.raise_for_status()  # Raises an exception for HTTP errors

            # Save the image to the designated path
            with open(file_path, 'wb') as out_file:
                shutil.copyfileobj(response.raw, out_file)

            self.logger.info("Image successfully downloaded: %s", file_path)
            return str(file_path)

        except requests.exceptions.RequestException as e:
            self.logger.error("Failed to download image from %s: %e", url, e)
            return None
        except OSError as e:
            self.logger.error("File system error while saving image: %s", e)
            return None
        finally:
            if 'response' in locals():
                response.close()

    def parse_pub_date(self, entry):
        """Method to parse the publication date"""
        pub_date_str = entry.get('pub_date', '')
        if pub_date_str:
            try:
                return dateutil_parser.parse(pub_date_str).replace(tzinfo=None)
            except (ValueError, OverflowError):
                pass
        self.logger.warning("No matching date format found. Using current date.")
        return datetime.now()

    def define_tags(self, entry):
        """
        Define tags that will be posted along the posts.
        """
        if self.config_dict.get('client_name', '') == 'pyladies_bot':
            tags = '#pyladies #python '
        elif self.config_dict.get('client_name', '') == 'rladies_bot':
            tags = '#rladies #rstats '
        else:
            self.logger.info('Bot name not found')
            tags = ''

        pub_date = self.parse_pub_date(entry)

        age_of_post = datetime.now() - pub_date

        if age_of_post.days > 730:
            tags += '#oldiebutgoodie '

        if len(entry['tags']) > 0:
            for tag in entry['tags']:
                if tag.lower() in ['pyladies', 'python', 'rstats', 'rladies']:
                    pass
                else:
                    tag_clean = tag.replace(' ', '').replace('-', '').lower()[:50]
                    tags += f"#{tag_clean} "

        return tags

    def get_bluesky_did(self, platform_user_handle):
        """
        Method to get Bluesky DID to uniquely identify (and tag) user.
        """
        url = (
            f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?"
            f"handle={platform_user_handle.lstrip('@')}"
        )
        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                did = data.get('did', None)

                if did:
                    return did
                self.logger.info(
                    'The "did" field was not found in the response.'
                )
            else:
                self.logger.info(
                    'Failed to retrieve data. Status code: %s',
                    response.status_code
                )

        except requests.RequestException as e:
            self.logger.info('An error occurred: %s', e)

        return None

    def build_post_mastodon(
        self, title, name, platform_user_handle, tags, entry, content_type="blog"
    ):
        """
        Build Mastodon post.
        """
        platform_user_handle = self.check_platform_handle(platform_user_handle)

        emoji = CONTENT_TYPE_EMOJI.get(content_type, "📝")
        post = f'{emoji} "{title}"\n\n' if title else ''

        if self.config_dict.get('gen_ai_support', None):
            try:
                summarized_blog_post = self.summarize_text(entry)
            except Exception as e:  # pylint: disable=broad-except
                self.logger.warning("Gemini summarization failed, falling back to no summary: %s", e)
                summarized_blog_post = ""
            if summarized_blog_post:
                post += summarized_blog_post + '\n\n'

        if name:
            post += f'👤 {name}'
        if platform_user_handle:
            post += f' ({platform_user_handle})'
        if name or platform_user_handle:
            post += '\n\n'

        post += f"🔗 {entry.get('link', '')}\n\n{tags}"

        self.logger.info('*****************************')
        self.logger.info(post)
        self.logger.info('*****************************')

        return post

    @staticmethod
    def generate_text_to_summarize(entry):
        """
        Generate text to summarize.
        """
        text = (
            f"Title: {entry.get('title', '')}\n"
            f"Summary: {entry.get('summary', '')}"
        )
        if len(text.split()) > 700:
            words = text.split()[:700]
            return ' '.join(words)
        return text

    @staticmethod
    def clean_response(response):
        """
        Clean response.
        """
        return ' '.join(response.text.replace('\n', ' ').split())

    def summarize_text(self, entry):
        """
        Summarize text using LLMs.
        """
        text = self.generate_text_to_summarize(entry)
        prompt = (
            'Summarize the content of the post in maximum 60 characters. '
            'Be as concise as possible and be engaging. '
            "Don't repeat the title.\n\n"
            + text
        )
        _retryable_codes = ("429", "503")
        _max_attempts = 3
        _retry_wait = 30
        response = None
        for attempt in range(_max_attempts):
            try:
                response = self.genai_client.models.generate_content(
                    model=self.config_dict.get('gemini_model_name', ''),
                    contents=prompt
                )
                break
            except Exception as e:  # pylint: disable=broad-except
                if attempt < _max_attempts - 1 and any(
                    code in str(e) for code in _retryable_codes
                ):
                    self.logger.info(
                        "Gemini API transient error (attempt %d/%d), "
                        "retrying in %ds: %s",
                        attempt + 1, _max_attempts, _retry_wait, e
                    )
                    time.sleep(_retry_wait)
                else:
                    raise
        response_cleaned = self.clean_response(response)
        safety_ratings = response.candidates[0].safety_ratings
        if not safety_ratings or all(
            rating.probability.name == 'NEGLIGIBLE'
            for rating in safety_ratings
        ):
            return response_cleaned
        return ''

    @staticmethod
    def check_platform_handle(platform_user_handle):
        """
        Check platform handle.
        """
        if not platform_user_handle:
            return ""
        if (len(platform_user_handle) > 1
                and not platform_user_handle.startswith('@')):
            return f"@{platform_user_handle}"
        return platform_user_handle

    def build_post_bluesky(
        self,
        title,
        name,
        platform_user_handle,
        tags,
        entry,
        content_type="blog"
    ):
        """
        Build post for Bluesky.
        """
        bluesky_max_graphemes = 300
        link = entry.get('link', '')
        platform_user_handle = self.check_platform_handle(platform_user_handle)

        summarized_blog_post = ''
        if self.config_dict.get('gen_ai_support', None):
            try:
                summarized_blog_post = self.summarize_text(entry) or ''
            except Exception as e:  # pylint: disable=broad-except
                self.logger.warning("Gemini summarization failed, falling back to no summary: %s", e)
                summarized_blog_post = ''

        # Resolve DID once so _build() never makes a duplicate HTTP call
        did = self.get_bluesky_did(platform_user_handle) if platform_user_handle else None

        emoji = CONTENT_TYPE_EMOJI.get(content_type, "📝")
        tag_list = [t.strip() for t in tags.split('#') if t.strip()]

        def _build(tag_subset):
            tb = client_utils.TextBuilder()
            if title:
                tb.text(f'{emoji} "{title}"\n\n')
            if summarized_blog_post:
                tb.text(summarized_blog_post)
                tb.text('\n\n')
            if name:
                tb.text(f'👤 {name}')
            if platform_user_handle:
                tb.mention(f' ({platform_user_handle})', did)
            if name or platform_user_handle:
                tb.text('\n\n')
            tb.text('🔗 ')
            tb.link(link, link)
            tb.text('\n\n')
            for tag_clean in tag_subset:
                tb.tag(f'#{tag_clean} ', tag_clean)
            return tb

        # Try with all tags; drop from the end one by one until within limit
        for count in range(len(tag_list), -1, -1):
            text_builder = _build(tag_list[:count])
            if len(text_builder.build_text()) <= bluesky_max_graphemes:
                return text_builder

        return _build([])

    def build_post(self, entry, feed):
        """Take the entry dict and build a post"""

        tags = self.define_tags(entry)
        platform = self.config_dict.get('platform', '')
        platform_user_handle = feed.get(platform)

        title = entry.get('title', '')
        name = feed.get('name', '')
        content_type = feed.get('content_type', 'blog')

        if self.config_dict.get('platform', '') == 'mastodon':
            return self.build_post_mastodon(
                title,
                name,
                platform_user_handle,
                tags,
                entry,
                content_type,
            )
        if self.config_dict.get('platform', '') == 'bluesky':
            return self.build_post_bluesky(
                title,
                name,
                platform_user_handle,
                tags,
                entry,
                content_type,
            )
        return None

    def send_post_to_mastodon(self, en, client, post_txt):
        """
        Send post to Mastodon.
        """
        media_content = en.get('media_content', None)
        alt_text = en.get('alt_text', None)

        if media_content:
            try:
                self.logger.info('Uploading media to mastodon')
                filename = self.download_image(media_content)
                media_upload_mastodon = client.media_post(filename)

                if alt_text:
                    self.logger.info('Adding description')
                    client.media_update(media_upload_mastodon,
                                        description=alt_text)

                self.logger.info('Now ready to post... ⏳')
                client.status_post(post_txt, media_ids=[media_upload_mastodon])

                self.logger.info('Posted 🎉')
                return 'success'
            except Exception as e:
                self.logger.exception(
                    'Urg, media could not be printed for %s. Exception: %s',
                    en.get('link', 'unknown link'),
                    e)
                client.status_post(post_txt)
                self.logger.info('Posted post without image.')
                return 'failed'
        else:
            try:
                client.status_post(post_txt)
                self.logger.info('Posted 🎉')
                return 'success'
            except Exception as e:
                self.logger.exception(
                    'Urg, exception %s for %s',
                    e,
                    en.get('link', 'unknown link')
                )
                return 'failed'

    def send_post_to_bluesky(self, en, client, post_txt, embed_external):
        """
        Send post to Bluesky.
        """
        try:
            if embed_external:
                client.send_post(text=post_txt, embed=embed_external)
            else:
                client.send_post(text=post_txt)
            self.logger.info("Posted 🎉")
            return 'success'
        except Exception as e:
            self.logger.exception("Urg, exception %s for %s", e, en['link'])
            return 'failed'

    def build_embed_external(self, en, client):
        """
        Build embed external. This is a speciality of Bluesky's protocol.
        """
        if en['media_content']:
            filename = self.download_image(en['media_content'])
            if filename is None:
                return None
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

    def send_post(self, en, feed, client):
        """Turn the dict into post text and send the post"""
        result = None
        self.logger.info(
            "Preparing the post on %s "
            "(%s) ...",
            self.config_dict['client_name'],
            {self.config_dict['platform']}
        )

        post_txt = self.build_post(
            en,
            feed
        )
        if self.config_dict["platform"] == "mastodon":
            result = self.send_post_to_mastodon(
                en,
                client,
                post_txt
            )
        elif self.config_dict["platform"] == "bluesky":
            embed_external = self.build_embed_external(
                en,
                client
            )
            result = self.send_post_to_bluesky(
                en,
                client,
                post_txt,
                embed_external
            )
        return result

    @staticmethod
    def load_feed(feed_path, d):
        """Method to load RSS feed"""
        full_fpd = feedparser.parse(feed_path)
        return d + full_fpd.entries

    @staticmethod
    def get_rss_feed_archive(feed):
        """Method to get RSS feed archive content"""
        if not feed.get('ARCHIVE'):
            return {'link': []}
        archive_path = Path(feed['ARCHIVE'][0])
        archive_file = archive_path / 'file.json'

        if archive_path.exists():
            try:
                with archive_file.open('rb') as fp:
                    rss_feed_archive = json.load(fp)
            except (FileNotFoundError, json.JSONDecodeError):
                rss_feed_archive = {'link': []}
        else:
            if any(
                domain in feed['ARCHIVE'][0]
                for domain in ["www.youtube.com", "medium.com"]
            ):
                archive_path = archive_path / \
                    feed['name'].lower().replace(' ', '-')

            archive_path.mkdir(parents=True, exist_ok=True)
            rss_feed_archive = {'link': []}

        return rss_feed_archive

    @staticmethod
    def get_number_of_archive_entries(d, rss_feed_archive):
        """
        Calculate the number of entries in the feed and archive,
        ensuring archive structure is correct.
        """
        number_of_entries_feed = len(d)

        if 'link' in rss_feed_archive and isinstance(
            rss_feed_archive['link'],
            list
        ):
            number_of_entries_archive = len(set(rss_feed_archive['link']))
        else:
            # Fix the archive structure if 'link' key is missing or incorrect
            rss_feed_archive = {'link': list(set(rss_feed_archive))}
            number_of_entries_archive = len(rss_feed_archive['link'])

        return (
            rss_feed_archive,
            number_of_entries_archive,
            number_of_entries_feed,
        )

    @staticmethod
    def adjust_archive_path(base_path, domain, counter_name):
        """
        Helper function to clean up path construction for
        YouTube and Medium
        """
        feed_name_slug = counter_name.lower().replace(' ', '-')
        if "www.youtube.com" in domain or "medium.com" in domain:
            return base_path / feed_name_slug / feed_name_slug
        return base_path

    def get_folder_path(self, feed):
        """Method to identify folder path"""

        rss_feeds = feed.get('rss_feed', [])
        archive_paths = []
        archive = f"archive/{self.config_dict.get('archive', '')}"

        if len(rss_feeds) > 1:
            for rss_feed in rss_feeds:
                domain = urlsplit(rss_feed).netloc
                folder_path = Path(archive) / domain
                archive_paths.append(str(folder_path))

        elif len(rss_feeds) == 1:
            domain = urlsplit(rss_feeds[0]).netloc
            folder_path = Path(archive) / domain
            folder_path = self.adjust_archive_path(
                folder_path,
                domain,
                feed['name']
            )
            archive_paths.append(str(folder_path))

        feed['ARCHIVE'] = archive_paths
        return feed

    def process_feed(self, feed, count_post, client):
        """
        Process the RSS feed and generate a post for any entry
        we haven't yet seen.
        """
        name = feed.get('name', 'unknown name')
        rss_feed = feed.get('rss_feed', 'unknown feed')
        self.logger.info("=========================================")
        self.logger.info(
            'Begin processing of feeds from %s (%s)',
            name,
            rss_feed
        )

        feed = self.get_folder_path(feed)

        d = []

        for feed_path in rss_feed:
            # if "medium.com" in feed_path:
            #     parsed_url = urlparse(feed_path)
            #     subdomain = parsed_url.hostname.split('.')[0]
            #     feed_path = f"https://medium.com/feed/@{subdomain}"
            # # Load the feed
            try:
                d = self.load_feed(feed_path, d)
                rss_feed_archive = self.get_rss_feed_archive(feed)
                # Identify number of entries
                (
                    rss_feed_archive,
                    number_of_entries_archive,
                    number_of_entries_feed
                ) = self.get_number_of_archive_entries(d, rss_feed_archive)
                # If there are more entries, go through the list:

                feed_config = {
                    'rss_feed_archive': rss_feed_archive,
                    'number_of_entries_feed': number_of_entries_feed,
                    'feed': feed,
                    'd': d
                }

                if number_of_entries_feed > number_of_entries_archive:
                    prev_count = count_post
                    count_post = self._process_feed(
                        client,
                        count_post,
                        feed_config
                    )
                    if count_post > prev_count:
                        self.logger.info(
                            'New RSS feeds are successfully loaded and '
                            'processed.'
                        )
                    else:
                        self.logger.info(
                            'Feed has new entries but all are already '
                            'in the archive — nothing to post.'
                        )
                    return count_post
                self.logger.info(
                    'Archive is up to date with the feed — '
                    'no new entries since last run.'
                )
                return count_post
            except Exception as e:
                self.logger.info(
                    '🚨 Feed for %s not available because %s',
                    feed_path,
                    e
                )
                return count_post

    def _save_rss_feed_archive(self, feed, rss_feed_archive):
        """ Save RSS feed archive to a file """
        archive_path = os.path.join(feed['ARCHIVE'][0], 'file.json')
        safe_root = Path.cwd().resolve()
        target = Path(archive_path).resolve()
        if not str(target).startswith(str(safe_root)):
            raise ValueError(
                f"Archive path {archive_path!r} escapes the project root — refusing to write."
            )
        with open(archive_path, 'w', encoding='utf-8') as fp:
            json.dump(rss_feed_archive, fp)
        self.logger.info("Archive for %s updated successfully.", feed['name'])

    @staticmethod
    def _get_media_content(entry):
        """ Extract media content from an RSS entry """
        en = {}
        if 'www.youtube.com' in entry.link:
            en['media_content'] = (
                f"http://img.youtube.com/vi/"
                f"{entry.id.replace('yt:video:', '')}/hqdefault.jpg"
            )
        elif 'media_content' in entry:
            en['media_content'] = entry.media_content[0]['url']
        else:
            soup = BeautifulSoup(entry.summary, "html.parser")
            img_url = [
                img['src']
                for img in soup.find_all('img')
                if img.has_attr('src')
            ]
            alt_text = [
                img['alt']
                for img in soup.find_all('img')
                if img.has_attr('alt')
            ]
            if img_url:
                en['media_content'] = img_url[0]
            if alt_text:
                en['alt_text'] = alt_text[0] if alt_text else ''
        return en

    def _process_feed(
        self,
        client,
        count_post,
        feed_config
    ):
        """ Process RSS feed entries and send posts """
        count = 0
        count_fails = 0
        result = None
        for _, entry in enumerate(feed_config['d']):
            if count >= 1:  # Limit to 1 post per run
                break
            if count_fails >= 1:
                self.logger.warning(
                    "Stopping feed after post failure — skipping remaining entries."
                )
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

            if self.process_images:
                en.update(self._get_media_content(entry))

            if en['link'] not in feed_config['rss_feed_archive']['link']:
                if self.no_dry_run:
                    result = self.send_post(en, feed_config['feed'], client)
                    if result == 'success':
                        feed_config['rss_feed_archive']['link'].append(en['link'])
                        count_post += 1
                        count += 1
                        time.sleep(1)
                    elif result == 'failed':
                        count_fails += 1
                        time.sleep(1)
                else:
                    self.logger.info(
                        "[DRY RUN] Would post: '%s' from %s",
                        en.get('title', 'unknown'),
                        en.get('link', 'unknown'),
                    )
                    count_post += 1
                    count += 1

        if self.no_dry_run and result == 'success':
            try:
                self._save_rss_feed_archive(
                    feed_config['feed'],
                    feed_config['rss_feed_archive']
                )
            except OSError as e:
                self.logger.error(
                    "Failed to save archive for %s: %s",
                    feed_config['feed'].get('name', 'unknown'),
                    e,
                )

        return count_post


if __name__ == "__main__":
    promote_blog_post_handler = PromoteBlogPost(
        config_dict=None,
        no_dry_run=True
    )
    promote_blog_post_handler.promote_blog_post()
