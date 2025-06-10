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
    def __init__(self, config_dict=None, no_dry_run=True):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        
        self.process_images = False
        self.no_dry_run = no_dry_run
        self.config_dict = config_dict
    
    def promote_blog_post(self):
        """Core method to promote blog post"""

        if (self.config_dict is None) and (self.no_dry_run):
            self.config_dict = {
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
                "gemini_model_name": "gemini-2.5-flash"
            }
            if self.config_dict["platform"] == "mastodon":
                self.config_dict["api_base_url"] = config.API_BASE_URL
                self.config_dict["mastodon_visibility"] = config.MASTODON_VISIBILITY
                self.config_dict["client_id"] = os.getenv("CLIENT_ID")
                self.config_dict["client_secret"] = os.getenv("CLIENT_SECRET")
                self.config_dict["access_token"] = os.getenv("ACCESS_TOKEN")
                self.config_dict["client_cred_file"] = os.getenv('BOT_CLIENTCRED_SECRET')
            else:
                self.config_dict["api_base_url"] = "bluesky"
            
            if self.config_dict["gen_ai_support"]:
                genai.configure(api_key=self.config_dict["gemini_api_key"])
            
        if self.no_dry_run:
            self.logger.info("")
            self.logger.info("Initializing %s Bot", self.config_dict["client_name"])
            self.logger.info("%s", "=" * (len(self.config_dict["client_name"]) + 17))
            self.logger.info(" > Connecting to %s", self.config_dict["api_base_url"])
            
            if self.config_dict["platform"] == "mastodon":
                _, client = login_mastodon(self.config_dict)
            elif self.config_dict["platform"] == "bluesky":
                client = login_bluesky(self.config_dict)
        else:
            client = None

        with open(self.config_dict["pickle_file"], 'rb') as fp:
            self.logger.info(
                "================================================================")
            FEEDS = pickle.load(fp)
            self.logger.info('Meta data was successfully loaded')
            self.logger.info(
                "================================================================")

        # Initiate count to post a maximum of 2 posts per run
        count_post = 0

        with open(self.config_dict["counter"], 'r') as f:
            feed_name = f.read()

        # Drop empty rss_feeds
        FEEDS = [x for x in FEEDS if x['rss_feed'] != '']

        if self.no_dry_run:
            for feed in FEEDS:
                if ((feed_name in (feed['name'], '\n', ''))
                    and (len(feed['rss_feed']) > 0)
                        and (feed['rss_feed'] != [None])):
                    if (count_post == 0) & (feed['name'] == FEEDS[-1]['name']):
                        count_post = self.process_feed(feed,
                                                count_post,
                                                client)

                        # Add the feed_name
                        if feed['name'] == FEEDS[-1]['name']:
                            new_feed = FEEDS[0]
                            count_post = self.process_feed(new_feed,
                                                    count_post,
                                                    client)

                            self.logger.info(
                                "Successfully promoted blog posts. "
                                "Thank you and see you next time!")
                            feed_name = FEEDS[1]['name']
                            with open(self.config_dict["counter"], 'w') as txt_file:
                                txt_file.write(feed_name)
                            self.logger.info(
                                "================================================")
                            break

                    elif count_post < 2:
                        count_post = self.process_feed(feed,
                                                count_post,
                                                client)

                        # Add the feed_name
                        feed_name = ''
                        if feed['name'] == FEEDS[-1]['name']:
                            with open(self.config_dict["counter"], 'w') as txt_file:
                                txt_file.write(feed['name'])
                        self.logger.info(
                            "=================================================================")

                    else:
                        self.logger.info(
                            "Successfully promoted blog posts. "
                            "Thank you and see you next time!")
                        feed_name = feed['name']
                        with open(self.config_dict["counter"], 'w') as txt_file:
                            txt_file.write(feed_name)
                        break
        else:
            for feed in FEEDS:
                count_post = self.process_feed(feed,
                                        count_post,
                                        client)

        
    def download_image(self, url: str) -> str:
        """
        Downloads an image from the given URL and saves it locally, 
        organizing files by domain name.
        """
        try:
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'
            }

            # Download the image
            self.logger.info("Downloading image from %s...", url)
            response = requests.get(url, headers=headers, stream=True, timeout=15)
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
            response.close() if 'response' in locals() else None


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
                self.logger.info("Failed to parse date with format: %s", date_format)

        # If none of the formats match, use the current date as a fallback
        self.logger.warning("No matching date format found. Using current date.")
        return datetime.now()  # Fallback value

    def define_tags(self, entry):
        if self.config_dict["client_name"] == 'pyladies_bot':
            tags = '#pyladies #python '
        elif self.config_dict["client_name"] == 'rladies_bot':
            tags = '#rladies #rstats '
        else:
            self.logger.info("Bot name not found")
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
                    tags += f'#{tag.replace(" ", "").replace("-", "").lower()} '

        return tags
        
    def get_bluesky_did(self, platform_user_handle):
        
        url = f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?handle={platform_user_handle.lstrip('@')}"
        try:
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                did = data.get("did")
                
                if did:
                    return did
                else:
                    self.logger.info("The 'did' field was not found in the response.")
            else:
                self.logger.info(f"Failed to retrieve data. Status code: {response.status_code}")

        except requests.RequestException as e:
            self.logger.info("An error occurred:", e)
            
    def build_post_mastodon(self, basis_text, platform_user_handle, tags, entry):
        platform_user_handle = self.check_platform_handle(platform_user_handle)
        
        if platform_user_handle:
            basis_text += f" ({platform_user_handle}) "
        if self.config_dict["gen_ai_support"]:
            summarized_blog_post = self.summarize_text(entry)
            if summarized_blog_post:
                basis_text.text('\n\n📖 ')
                basis_text.text(summarized_blog_post)    
        basis_text += f'\n\n🔗 {entry["link"]}\n\n{tags}'
        
        self.logger.info("*****************************")
        self.logger.info(basis_text)
        self.logger.info("*****************************")

        return basis_text

    @staticmethod
    def generate_text_to_summarize(entry):
        text = f"Title: {entry['title']}\nSummary: {entry['summary']}"
        if len(text.split())>700:
            words = text.split()[:700]
            return ' '.join(words)
        return text 

    @staticmethod
    def clean_response(response):
        return ' '.join(response.text.replace("\n", " ").split())


    def summarize_text(self, entry):
        text = self.generate_text_to_summarize(entry)
        model = genai.GenerativeModel(self.config_dict["gemini_model_name"])
        prompt_parts = ["Summarize the content of the post in maximum 60 characters.",
                        "Be as concise as possible and be engaging.",
                        "Don't repeat the title.",
                        text]
        response = model.generate_content(prompt_parts)
        response_cleaned = self.clean_response(response)
        safety_ratings = response.candidates[0].safety_ratings
        if all(rating.probability.name == "NEGLIGIBLE" for rating in safety_ratings):
            return response_cleaned
        return ''

    @staticmethod
    def check_platform_handle(platform_user_handle):
        if len(platform_user_handle)>1 and not platform_user_handle.startswith('@'):
            return f"@{platform_user_handle}"
        return platform_user_handle
        
    def build_post_bluesky(self, basis_text, platform_user_handle, tags, entry):
        
        text_builder = client_utils.TextBuilder()
        text_builder.text(basis_text)
        
        platform_user_handle = self.check_platform_handle(platform_user_handle)
        
        if platform_user_handle:
            did = self.get_bluesky_did(platform_user_handle)
            text_builder.mention(f" ({platform_user_handle})", did)
        if self.config_dict["gen_ai_support"]:
            summarized_blog_post = self.summarize_text(entry)
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

    def build_post(self, entry, feed):
        """Take the entry dict and build a post"""
        
        tags = self.define_tags(entry)
        platform = self.config_dict.get("platform")
        platform_user_handle = feed.get(platform)
        
        basis_text = f'📝 "{entry["title"]}"\n\n👤 {feed["name"]}'
        
        if self.config_dict["platform"] == "mastodon":
            return self.build_post_mastodon(basis_text, platform_user_handle, tags, entry)
        elif self.config_dict["platform"] == "bluesky":
            return self.build_post_bluesky(basis_text, platform_user_handle, tags, entry)

    def send_post_to_mastodon(self, en, client, post_txt):
        if en['media_content']:
            try:
                self.logger.info("Uploading media to mastodon")
                filename = self.download_image(en['media_content'])
                media_upload_mastodon = client.media_post(filename)

                if 'alt_text' in en:
                    self.logger.info("adding description")
                    client.media_update(media_upload_mastodon,
                                        description=en['alt_text'])

                self.logger.info("ready to post")
                client.status_post(post_txt, media_ids=media_upload_mastodon)

                self.logger.info("Posted 🎉")
                return 'success'
            except Exception as e:
                self.logger.exception(
                    "Urg, media could not be printed for %s. Exception: %s", en['link'], e)
                client.status_post(post_txt)
                self.logger.info("Posted post without image.")
                return 'failed'
        else:
            try:
                client.status_post(post_txt)
                self.logger.info("Posted 🎉")
                return 'success'
            except Exception as e:
                self.logger.exception("Urg, exception %s for %s", e, en['link'])
                return 'failed'

    def send_post_to_bluesky(self, en, client, post_txt, embed_external):
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
        self.logger.info(f"Preparing the post on {self.config_dict['client_name']} ({self.config_dict['platform']}) ...")
        
        post_txt = self.build_post(en, feed, self.config_dict)    
        if self.config_dict["platform"] == "mastodon":
            result = self.send_post_to_mastodon(en, client, post_txt)
        elif self.config_dict["platform"] == "bluesky":
            embed_external = self.build_embed_external(en, client)
            result = self.send_post_to_bluesky(en, client, post_txt, embed_external)
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
            if any(domain in feed['ARCHIVE'][0] for domain in ["www.youtube.com", "medium.com"]):
                archive_path = archive_path / \
                    feed['name'].lower().replace(' ', '-')

            archive_path.mkdir(parents=True, exist_ok=True)
            rss_feed_archive = {'link': []}

        return rss_feed_archive

    @staticmethod
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

    def get_folder_path(self, feed):
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
                folder_path = Path(self.config_dict["archive"]) / domain
                archive_paths.append(str(folder_path))

        elif len(rss_feeds) == 1:
            domain = urlsplit(rss_feeds[0]).netloc
            folder_path = Path(self.config_dict["archive"]) / domain
            folder_path = adjust_archive_path(folder_path, domain, feed['name'])
            archive_paths.append(str(folder_path))

        feed['ARCHIVE'] = archive_paths
        return feed


    def process_feed(self, feed, count_post, client):
        """
        Process the RSS feed and generate a post for any entry 
        we haven't yet seen.
        """
        self.logger.info("====================================================")
        self.logger.info("Begin processing of feeds from %s (%s)",
                    feed['name'], feed['rss_feed'])

        feed = self.get_folder_path(feed)

        d = []

        for feed_path in feed['rss_feed']:
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
                    self.logger.info("New RSS feeds are successfully loaded and "
                                "processed.")
                    return count_post
                self.logger.info("Maximum number of posts is already posted.")
                return count_post
            except Exception as e:
                self.logger.info("🚨 Feed for %s not available because %s", feed_path, e)
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


    def _process_feed(self,
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

            if self.process_images:
                en.update(self._get_media_content(entry))

            if en['link'] not in feed_config['rss_feed_archive']['link']:
                feed_config['rss_feed_archive']['link'].append(en['link'])
                if self.no_dry_run:
                    result = self.send_post(en, feed_config['feed'], client)
                if result=='success':
                    count_post += 1
                    count += 1
                    time.sleep(1)
                elif result=='failed':
                    count_fails += 1
                    time.sleep(1)

        if self.no_dry_run:
            if result=='success':
                self._save_rss_feed_archive(feed_config['feed'],
                                    feed_config['rss_feed_archive'])

        return count_post

if __name__ == "__main__":
    promote_blog_post_handler = PromoteBlogPost(config_dict=None, no_dry_run=True)
    promote_blog_post_handler.promote_blog_post()
