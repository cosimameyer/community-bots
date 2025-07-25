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
from atproto import client_utils, models
import google.generativeai as genai

import feedparser
import requests
from bs4 import BeautifulSoup
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky

import config


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
                "pickle_file": self._ensure_metadata_prefix(
                    os.getenv("PICKLE_FILE", "")
                ),
                "gen_ai_support": True,
                "gemini_api_key": os.getenv("GEMINI_API_KEY"),
                "gemini_model_name": "gemini-2.5-flash"
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

            if self.config_dict["gen_ai_support"]:
                genai.configure(api_key=self.config_dict["gemini_api_key"])
        else:
            self.config_dict['pickle_file'] = self._ensure_metadata_prefix(
                self.config_dict.get('pickle_file')
            )
            self.config_dict['counter'] = self._ensure_metadata_prefix(
                self.config_dict.get('counter')
            )

    def promote_blog_post(self):
        """Core method to promote blog post"""
        
        self.get_config()

        if self.no_dry_run:
            client_name = self.config_dict.get('client_name', 'unknown')
            self.logger.info("")
            self.logger.info(
                'Initializing %s Bot',
                client_name
            )
            separator = "%s", "=" * (len(client_name) + 17)
            self.logger.info(separator)
            self.logger.info(
                " > Connecting to %s",
                self.config_dict.get('api_base_url', '')
            )

            if self.config_dict["platform"] == "mastodon":
                _, client = login_mastodon(self.config_dict)
            elif self.config_dict["platform"] == "bluesky":
                client = login_bluesky(self.config_dict)
        else:
            client = None
            
        feeds = self.read_metadata_pickle()
        counter_name = self.read_counter_name()

        # Initiate count to post a maximum of 2 posts per run
        count_post = 0

        # Drop empty rss_feeds
        feeds = [x for x in feeds if x['rss_feed'] != '']

        if self.no_dry_run:
            self.process_feeds(feeds, counter_name, count_post, client)
        else:
            for feed in feeds:
                count_post = self.process_feed(
                    feed,
                    count_post,
                    client
                )
                
    def process_feeds(self, feeds, counter_name, count_post, client):
        """
        Method to handle processing of all feeds.
        """
        for feed in feeds:
            if counter_name not in (feed['name'], '\n', ''):
                continue
            if len(feed['rss_feed']) == 0 or feed['rss_feed'] == [None]:
                continue
            
            is_last_feed = feed['name'] == feeds[-1]['name']

            if count_post == 0 and is_last_feed:
                count_post = self.process_feed(
                    feed,
                    count_post,
                    client
                )

                # Add the counter_name
                if is_last_feed:
                    new_feed = feeds[0]
                    count_post = self.process_feed(
                        new_feed,
                        count_post,
                        client
                    )

                    self.logger.info(
                        "Successfully promoted blog posts. "
                        "Thank you and see you next time!")
                    self.update_counter(feeds[1]['name'])
                    break

            elif count_post < 2:
                count_post = self.process_feed(
                    feed,
                    count_post,
                    client
                )
                counter_name = ''
                if is_last_feed:
                    self.update_counter(feed['name'])
                self.logger.info(
                    "=========================================")

            else:
                self.logger.info(
                    "Successfully promoted blog posts. "
                    "Thank you and see you next time!")
                self.update_counter(feed['name'])
                break

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
        with open(self.config_dict["counter"], 'r', encoding='utf-8') as f:
            return f.read()

    def read_metadata_pickle(self):
        """
        Read metadata pickle file
        """
        with open(self.config_dict["pickle_file"], 'rb') as fp:
            self.logger.info(
                "============================================="
            )
            feeds = pickle.load(fp)
            self.logger.info('Meta data was successfully loaded')
            self.logger.info(
                "============================================="
            )
            return feeds

    @staticmethod
    def _ensure_metadata_prefix(value: str, prefix="metadata/") -> str:
        """
        Ensures that a string has the prefix "metadata/". If it does not
        have this, update it.
        """
        if not value.startswith(prefix):
            return prefix + value
        return value

    def download_image(self, url: str):
        """
        Downloads an image from the given URL and saves it locally,
        organizing files by domain name.
        """
        try:
            filename = ''
            # Parse the URL components
            if self.config_dict["platform"] == "bluesky":
                domain = urlsplit(url).path
                filename = posixpath.basename(domain)
            elif self.config_dict["platform"] == "mastodon":
                domain = urlsplit(url).netloc
                filename = posixpath.basename(urlsplit(url).path)

            # Create folder structure based on the domain name
            domain_dir = Path(self.config_dict['images']) / domain
            domain_dir.mkdir(parents=True, exist_ok=True)

            # Full file path for the image
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
                self.logger.info(
                    "Failed to parse date with format: %s",
                    date_format
                )

        # If none of the formats match, use the current date as a fallback
        self.logger.warning(
            "No matching date format found. Using current date."
        )
        return datetime.now()  # Fallback value

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
                    tags += (
                        f"#{tag.replace(' ', '').replace('-', '').lower()} "
                    )

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
            response = requests.get(url)

            if response.status_code == 200:
                data = response.json()
                did = data.get('did', None)

                if did:
                    return did
                else:
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

    def build_post_mastodon(
        self, basis_text, platform_user_handle, tags, entry
    ):
        """
        Build Mastodon post.
        """
        platform_user_handle = self.check_platform_handle(platform_user_handle)

        if platform_user_handle:
            basis_text += f" ({platform_user_handle}) "
        if self.config_dict.get('gen_ai_support', None):
            summarized_blog_post = self.summarize_text(entry)
            if summarized_blog_post:
                basis_text.text('\n\n📖 ')
                basis_text.text(summarized_blog_post)
        basis_text += f"\n\n🔗 {entry.get('link', '')}\n\n{tags}"

        self.logger.info('*****************************')
        self.logger.info(basis_text)
        self.logger.info('*****************************')

        return basis_text

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
        model = genai.GenerativeModel(
            self.config_dict.get('gemini_model_name', '')
        )
        prompt_parts = [
            'Summarize the content of the post in maximum 60 characters.',
            'Be as concise as possible and be engaging.',
            'Don\'t repeat the title.',
            text
        ]
        response = model.generate_content(prompt_parts)
        response_cleaned = self.clean_response(response)
        safety_ratings = response.candidates[0].safety_ratings
        if all(
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
        if (len(platform_user_handle) > 1
                and not platform_user_handle.startswith('@')):
            return f"@{platform_user_handle}"
        return platform_user_handle

    def build_post_bluesky(
        self,
        basis_text,
        platform_user_handle,
        tags,
        entry
    ):
        """
        Build post for Bluesky.
        """
        text_builder = client_utils.TextBuilder()
        text_builder.text(basis_text)

        platform_user_handle = self.check_platform_handle(platform_user_handle)

        if platform_user_handle:
            did = self.get_bluesky_did(platform_user_handle)
            text_builder.mention(f" ({platform_user_handle})", did)
        if self.config_dict.get('gen_ai_support', None):
            summarized_blog_post = self.summarize_text(entry)
            if summarized_blog_post:
                text_builder.text('\n\n📖 ')
                text_builder.text(summarized_blog_post)
        text_builder.text('\n\n🔗 ')
        link = entry.get('link', '')
        text_builder.link(link, link)
        text_builder.text('\n\n')
        for tag in tags.split('#'):
            tag_clean = tag.strip()
            if tag_clean:
                text_builder.tag(f"#{tag_clean} ", tag_clean)
        return text_builder

    def build_post(self, entry, feed):
        """Take the entry dict and build a post"""

        tags = self.define_tags(entry)
        platform = self.config_dict.get('platform', '')
        platform_user_handle = feed.get(platform)

        title = entry.get('title', '')
        name = feed.get('name', '')

        basis_text = ""

        if title:
            basis_text += f"📝 '{title}'\n\n"

        if name:
            basis_text += f"👤 {name}"
            
        if self.config_dict.get('platform', '') == 'mastodon':
            return self.build_post_mastodon(
                basis_text,
                platform_user_handle,
                tags,
                entry
            )
        elif self.config_dict.get('platform', '') == 'bluesky':
            return self.build_post_bluesky(
                basis_text,
                platform_user_handle,
                tags,
                entry
            )

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
                client.status_post(post_txt, media_ids=media_upload_mastodon)

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
        archive_path = Path(feed['ARCHIVE'][0])
        archive_file = archive_path / 'file.pkl'

        if archive_path.exists():
            try:
                with archive_file.open('rb') as fp:
                    rss_feed_archive = pickle.load(fp)
            except (FileNotFoundError, pickle.UnpicklingError):
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
        archive = self.config_dict.get('archive', '')

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
                    count_post = self._process_feed(
                        client,
                        count_post,
                        feed_config
                    )
                    self.logger.info(
                        'New RSS feeds are successfully loaded and '
                        'processed.'
                    )
                    return count_post
                self.logger.info('Maximum number of posts is already posted.')
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
        archive_path = os.path.join(feed['ARCHIVE'][0], 'file.pkl')
        with open(archive_path, 'wb') as fp:
            pickle.dump(rss_feed_archive, fp)
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

            if self.process_images:
                en.update(self._get_media_content(entry))

            if en['link'] not in feed_config['rss_feed_archive']['link']:
                feed_config['rss_feed_archive']['link'].append(en['link'])
                if self.no_dry_run:
                    result = self.send_post(en, feed_config['feed'], client)
                if result == 'success':
                    count_post += 1
                    count += 1
                    time.sleep(1)
                elif result == 'failed':
                    count_fails += 1
                    time.sleep(1)

        if self.no_dry_run:
            if result == 'success':
                self._save_rss_feed_archive(
                    feed_config['feed'],
                    feed_config['rss_feed_archive']
                )

        return count_post


if __name__ == "__main__":
    promote_blog_post_handler = PromoteBlogPost(
        config_dict=None,
        no_dry_run=True
    )
    promote_blog_post_handler.promote_blog_post()
