import logging
import json
from datetime import datetime
from urllib.parse import urlsplit
import config
import os
import re
from atproto import client_utils, models
import posixpath
import shutil
import requests
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky

class PromoteAnniversary():
    def __init__(self, config_dict=None, no_dry_run=True):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)
        
        self.config_dict = config_dict
        self.no_dry_run = no_dry_run

    def promote_anniversary(self):
        if (self.config_dict is None) and (self.no_dry_run):
            self.config_dict = {
                "platform": os.getenv("PLATFORM"),
                "images": os.getenv("IMAGES"),
                "password": os.getenv("PASSWORD"),
                "username": os.getenv("USERNAME"),
                "client_name": os.getenv("CLIENT_NAME")
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
        
        if self.no_dry_run:
            self.logger.info("")
            self.logger.info("Initializing %s Bot", self.config_dict["client_name"])
            self.logger.info("%s", "=" * (len(self.config_dict["client_name"]) + 17))
            self.logger.info(" > Connecting to %s",  self.config_dict["api_base_url"])
            
            if self.config_dict["platform"] == "mastodon":
                _, client = login_mastodon(self.config_dict)
            elif self.config_dict["platform"] == "bluesky":
                client = login_bluesky(self.config_dict)
        else:
            client = None
        
        with open('events.json') as f:
            events = json.load(f)
            
        if self.no_dry_run:
            for event in events:
                if self.is_matching_current_date(event["date"]):
                    self.send_post(event, client)
                    continue
                    # if  self.config_dict["platform"] == "mastodon":
                    #     send_post_to_mastodon(event,  self.config_dict, client)
                    #     continue
                    # elif  self.config_dict["platform"] == "bluesky":
                    #     send_post_to_bluesky(event,  self.config_dict, client)
                    #    continue

    @staticmethod
    def is_matching_current_date(date_str: str, format='%m-%d') -> bool:
        """Method to define if the event matches the current date and should be posted

        Args:
            date_str (str): Date taken from event dictionary
            format (str, optional): _description_. Defaults to '%m-%d'.

        Returns:
            bool: Defines whether the date matches the current date (True if yes)
        """
        current_date = datetime.now().strftime(format)
        return date_str == current_date

    def download_image(self, url):
        """
        # Taken from here: https://github.com/zeratax/mastodon-img-bot/blob/master/bot.py
        :param url: string with the url to the image
        :return: string with the path to the saved image
        """
        path = urlsplit(url).path
        filename = posixpath.basename(path)

        file_path = f"{self.config_dict['images']}/{filename}"
        if not os.path.isfile(file_path):
            if not os.path.isdir(self.config_dict['images']):
                os.makedirs(self.config_dict['images'])

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'}
            response = requests.get(url, headers=headers, stream=True)

            with open(file_path, 'wb') as out_file:
                shutil.copyfileobj(
                    response.raw, out_file)
            del response
        else:
            print("Image already downloaded")
        return file_path

    def build_post(self, event):
        """Method to build the toot

        Args:
            event (dict): Dictionary with information

        Returns:
            str: String with toot text
        """
        tags = f"\n\n#amazingwomenintech #womenalsoknow #impactthefuture"

        if self.config_dict["platform"] == "mastodon":
            toot_str = ""
            toot_str += f"Let's meet {event['name']} ✨\n\n{event['description_mastodon']}\n\n🔗 {event['wiki_link']}"
            toot_str += tags
            return toot_str
        elif self.config_dict["platform"] == "bluesky":
            text_builder = client_utils.TextBuilder()
            if event["bluesky"]:
                did = self.get_bluesky_did(event["bluesky"])
                text_builder.text(f"Let's meet ")
                text_builder.mention(f"{event['bluesky']}", did)
                text_builder.text(" ⭐️\n\n")
            else:
                text_builder.text(f"Let's meet {event['name']} ⭐️\n\n")
            split_text = re.split(r'(#\w+)', event["description_bluesky"])
            split_text = [item.rstrip(' ') for item in split_text if item.strip()]
            for text_chunk in split_text:
                if text_chunk.startswith('#'):
                    for tag in text_chunk.split("#"):
                        tag_clean = tag.strip()
                    if tag_clean:
                        text_builder.tag(f"#{tag_clean}", tag_clean)
                else:
                    text_chunk_clean = self.add_whitespace_if_needed(text_chunk)
                    text_builder.text(text_chunk_clean)
            text_builder.text('\n\n🔗 ')
            text_builder.link(event["wiki_link"], event["wiki_link"])
            text_builder.text('\n\n')
            for tag in tags.split("#"):
                tag_clean = tag.strip()
                if tag_clean:
                    text_builder.tag(f"#{tag_clean} ", tag_clean)
            return text_builder

    def send_post(self, event, client):
        """Turn the dict into post text and send the post"""
        
        self.logger.info(f"Preparing the post on {self.config_dict['client_name']} ({self.config_dict['platform']}) ...")
        
        post_txt = self.build_post(event)    
        if self.config_dict["platform"] == "mastodon":
            self.send_post_to_mastodon(event, client, post_txt)
        elif self.config_dict["platform"] == "bluesky":
            embed_external = self.build_embed_external(event, client)
            self.send_post_to_bluesky(event, client, post_txt, embed_external)        

    def build_embed_external(self, event, client):
        base_path = "https://raw.githubusercontent.com/cosimameyer/illustrations/main/amazing-women"
        url = f"{base_path}/{event['img']}"
        filename = self.download_image(url)
        with open(filename, 'rb') as f:
            img_data = f.read()

        thumb = client.upload_blob(img_data)

        return models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=f"Image of {event['name']}",
                description=event["alt"],
                uri=url,
                thumb=thumb.blob,
            )
        )
        
    @staticmethod
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
                    print("The 'did' field was not found in the response.")
            else:
                print(f"Failed to retrieve data. Status code: {response.status_code}")

        except requests.RequestException as e:
            print("An error occurred:", e)

    def send_post_to_bluesky(self, event, client, post_txt, embed_external):
        print(f"Preview your post...\n\n{post_txt._buffer.getvalue().decode('utf-8')}")  
        try:
            client.send_post(text=post_txt, embed=embed_external)
            self.logger.info("Posted 🎉")
        except Exception as e:
            self.logger.exception("Urg, exception %s for %s", e, event['name'])

    @staticmethod
    def add_whitespace_if_needed(text_chunk):
        if not text_chunk.endswith(('(', '{', '[')):
            text_chunk += ' '
        return text_chunk

    def send_post_to_mastodon(self, event, client, post_txt):
        """
        Turn the dict into toot text
        and send the toot
        """
        if event['img']:
            try:
                print("Uploading media to mastodon")
                base_path = "https://raw.githubusercontent.com/cosimameyer/illustrations/main/amazing-women"
                url = f"{base_path}/{event['img']}"
                
                filename = self.download_image(url)
                media_upload_mastodon = client.media_post(filename)
                
                print("adding description")
                if event["alt"]:
                    client.media_update(media_upload_mastodon,
                                        description=event["alt"])
                else:
                    client.media_update(media_upload_mastodon,
                                        description=str(event["name"]))

                print("ready to post")
                client.status_post(post_txt, 
                                media_ids=media_upload_mastodon)

                print("posted")
            except Exception as e:
                print(f"Urg, media could not be printed.\n Exception {event['name']} because of {e}")
                client.status_post(post_txt)
                print("Posted toot without image.")     
        else:
            try: 
                client.status_post(post_txt)
                print("posted")     
            except Exception as e:
                print(f"Urg, exception {event['toot']}. The reason was {e}")    
                    

              
if __name__ == "__main__":
    promote_anniversary_handler = PromoteAnniversary(config_dict=None, no_dry_run=True)
    promote_anniversary_handler.promote_anniversary()

