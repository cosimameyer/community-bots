import logging
import json
from datetime import datetime
from urllib.parse import urlsplit
import config
import os
import re
from mastodon import Mastodon
from atproto import Client, client_utils, models
import posixpath
import shutil
import requests
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky

# Set up logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

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

def download_image(url, config_dict):
    """
    # Taken from here: https://github.com/zeratax/mastodon-img-bot/blob/master/bot.py
    :param url: string with the url to the image
    :return: string with the path to the saved image
    """
    path = urlsplit(url).path
    filename = posixpath.basename(path)

    #logging.Logger.info("downloading image...")

    file_path = f"{config_dict['images']}/{filename}"
    if not os.path.isfile(file_path):
        if not os.path.isdir(config_dict['images']):
            os.makedirs(config_dict['images'])

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'}
        response = requests.get(url, headers=headers, stream=True)

        with open(file_path, 'wb') as out_file:
            shutil.copyfileobj(
                response.raw, out_file)
        del response
        #logging.Logger.info("image downloaded!")
    else:
        print("Image already downloaded")
    return file_path

def build_post(event, config_dict):
    """Method to build the toot

    Args:
        event (dict): Dictionary with information

    Returns:
        str: String with toot text
    """
    tags = f"\n\n#amazingwomenintech #womenalsoknow #impactthefuture"

    if config_dict["platform"] == "mastodon":
        toot_str = ""
        toot_str += f"Let's meet {event['name']} ✨\n\n{event['description_mastodon']}\n\n🔗 {event['wiki_link']}"
        toot_str += tags
        return toot_str
    elif config_dict["platform"] == "bluesky":
        text_builder = client_utils.TextBuilder()
        if event["bluesky"]:
            did = get_bluesky_did(event["bluesky"])
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
                text_chunk_clean = add_whitespace_if_needed(text_chunk)
                text_builder.text(text_chunk_clean)
        text_builder.text('\n\n🔗 ')
        text_builder.link(event["wiki_link"], event["wiki_link"])
        text_builder.text('\n\n')
        for tag in tags.split("#"):
            tag_clean = tag.strip()
            if tag_clean:
                text_builder.tag(f"#{tag_clean} ", tag_clean)
        return text_builder

def send_post(event, config_dict, client):
    """Turn the dict into post text and send the post"""
    
    logger.info(f"Preparing the post on {config_dict['client_name']} ({config_dict['platform']}) ...")
    
    post_txt = build_post(event, config_dict)    
    if config_dict["platform"] == "mastodon":
        #pass
        send_post_to_mastodon(event, client, config_dict, post_txt)
    elif config_dict["platform"] == "bluesky":
        #pass
        embed_external = build_embed_external(event, client, config_dict)
        send_post_to_bluesky(event, client, post_txt, embed_external)        

def build_embed_external(event, client, config_dict):
    base_path = "https://raw.githubusercontent.com/cosimameyer/illustrations/main/amazing-women"
    url = f"{base_path}/{event['img']}"
    filename = download_image(url, config_dict)
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

def send_post_to_bluesky(event, client, post_txt, embed_external):
    print(f"Preview your post...\n\n{post_txt._buffer.getvalue().decode('utf-8')}")  
    try:
        client.send_post(text=post_txt, embed=embed_external)
        logger.info("Posted 🎉")
    except Exception as e:
        logger.exception("Urg, exception %s for %s", e, event['name'])

def add_whitespace_if_needed(text_chunk):
    if not text_chunk.endswith(('(', '{', '[')):
        text_chunk += ' '
    return text_chunk

def send_post_to_mastodon(event, client, config_dict, post_txt):
    """
    Turn the dict into toot text
    and send the toot
    """
    if event['img']:
        try:
            print("Uploading media to mastodon")
            base_path = "https://raw.githubusercontent.com/cosimameyer/illustrations/main/amazing-women"
            url = f"{base_path}/{event['img']}"
            
            filename = download_image(url, config_dict)
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
                
def promote_anniversary(config_dict=None, NO_DRY_RUN=True):
    if (config_dict is None) and (NO_DRY_RUN):
        config_dict = {
            "platform": os.getenv("PLATFORM"),
            "images": os.getenv("IMAGES"),
            "password": os.getenv("PASSWORD"),
            "username": os.getenv("USERNAME"),
            "client_name": os.getenv("CLIENT_NAME")
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
     
    with open('events.json') as f:
        events = json.load(f)
        
    if NO_DRY_RUN:
        for event in events:
            if is_matching_current_date(event["date"]):
                send_post(event, config_dict, client)
                continue
                # if config_dict["platform"] == "mastodon":
                #     send_post_to_mastodon(event, config_dict, client)
                #     continue
                # elif config_dict["platform"] == "bluesky":
                #     send_post_to_bluesky(event, config_dict, client)
                #    continue

              
if __name__ == "__main__":
    promote_anniversary(config_dict=None, NO_DRY_RUN=True)

