"""
Module to promote anniversaries on Mastodon and Bluesky.
Handles fetching events, building posts, and posting to platforms.
"""

import json
import logging
import os
import posixpath
import re
import shutil
from datetime import datetime
from typing import Any, Dict, Optional, Union
from urllib.parse import urlsplit

import requests
from dotenv import load_dotenv
from atproto import client_utils, models

import config
from helper.login_bluesky import login_bluesky
from helper.login_mastodon import login_mastodon

load_dotenv()

REQUEST_TIMEOUT = 10  # seconds


class PromoteAnniversary:
    """
    Handles fetching event data and posting anniversary messages
    to social platforms.
    """

    def __init__(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        no_dry_run: bool = True
    ) -> None:
        """
        Initialize a PromoteAnniversary handler.

        Args:
            config_dict: Optional configuration dictionary.
            no_dry_run: Whether to actually execute posting (True)
                or just simulate actions (False).
        """
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.config_dict = config_dict
        self.no_dry_run = no_dry_run
        self.base_path = (
            "https://raw.githubusercontent.com/cosimameyer/"
            "illustrations/main/amazing-women"
        )
   
    @property
    def cfg(self) -> Dict[str, Any]:
        """Property to ensure that the dictionary is initialized."""
        if self.config_dict is None:
            raise RuntimeError("Config dictionary not initialized")
        return self.config_dict

    def promote_anniversary(self) -> None:
        """Main entry point. Loads configuration, fetches events, and posts if applicable."""
        if self.config_dict is None and self.no_dry_run:
            self.config_dict = {
                "platform": os.getenv("PLATFORM"),
                "images": os.getenv("IMAGES"),
                "password": os.getenv("PASSWORD"),
                "username": os.getenv("USERNAME"),
                "client_name": os.getenv("CLIENT_NAME"),
            }
            if self.config_dict["platform"] == "mastodon":
                self.config_dict["api_base_url"] = config.API_BASE_URL
                self.config_dict[
                    "mastodon_visibility"
                ] = config.MASTODON_VISIBILITY
                self.config_dict["client_id"] = os.getenv("CLIENT_ID")
                self.config_dict["client_secret"] = os.getenv("CLIENT_SECRET")
                self.config_dict["access_token"] = os.getenv("ACCESS_TOKEN")
                self.config_dict[
                    "client_cred_file"
                ] = os.getenv("BOT_CLIENTCRED_SECRET")
            else:
                self.config_dict["api_base_url"] = "bluesky"

        if self.no_dry_run:
            self.logger.info(
                "Initializing %s Bot",
                self.cfg["client_name"]
            )
            self.logger.info(
                "=" * (len(self.cfg["client_name"]) + 17)
            )
            self.logger.info(
                " > Connecting to %s",
                self.cfg["api_base_url"]
            )

            if self.cfg["platform"] == "mastodon":
                _, client = login_mastodon(self.config_dict)
            elif self.cfg["platform"] == "bluesky":
                client = login_bluesky(self.config_dict)
            else:
                self.logger.error(
                    "Unsupported platform: %s",
                    self.cfg["platform"]
                )
                return
        else:
            client = None

        with open("metadata/events.json", encoding="utf-8") as f:
            events = json.load(f)

        if self.no_dry_run:
            for event in events:
                if self.is_matching_current_date(event["date"]):
                    self.send_post(event, client)

    @staticmethod
    def is_matching_current_date(
        date_str: str, date_format: str = "%m-%d"
    ) -> bool:
        """
        Check whether the given date matches today's date.

        Args:
            date_str: Date string to compare (e.g., "08-30").
            date_format: Format of the provided date string. 
                         Defaults to "%m-%d".

        Returns:
            True if the date matches today's date, False otherwise.
        """
        current_date = datetime.now().strftime(date_format)
        return date_str == current_date

    def download_image(self, url: str) -> str:
        """
        Download an image from a URL if not already cached locally.

        Args:
            url: URL to the image.

        Returns:
            Path to the downloaded image file.
        """
        path = urlsplit(url).path
        filename = posixpath.basename(path)
        file_path = os.path.join(self.cfg["images"], filename)

        if not os.path.isfile(file_path):
            os.makedirs(self.cfg["images"], exist_ok=True)
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) "
                    "Gecko/20100101 Firefox/20.0"
                    )
                }
            response = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=REQUEST_TIMEOUT
            )

            with open(file_path, "wb") as out_file:
                shutil.copyfileobj(response.raw, out_file)
            del response
        else:
            self.logger.info("Image already downloaded: %s", file_path)

        return file_path

    def build_post(
        self,
        event: Dict[str, Any]
    ) -> Union[str, client_utils.TextBuilder]:
        """
        Build the post text for Mastodon or Bluesky.

        Args:
            event: Dictionary containing event data.

        Returns:
            A formatted post string (Mastodon) or TextBuilder object (Bluesky).
        """
        tags = "\n\n#amazingwomenintech #womenalsoknow #impactthefuture"

        if self.cfg["platform"] == "mastodon":
            return (
                f"Let's meet {event['name']} ✨\n\n"
                f"{event['description_mastodon']}\n\n"
                f"🔗 {event['wiki_link']}{tags}"
            )

        if self.cfg["platform"] == "bluesky":
            text_builder = client_utils.TextBuilder()
            if event.get("bluesky"):
                did = self.get_bluesky_did(event["bluesky"])
                text_builder.text("Let's meet ")
                text_builder.mention(event["bluesky"], did)
                text_builder.text(" ⭐️\n\n")
            else:
                text_builder.text(f"Let's meet {event['name']} ⭐️\n\n")

            split_text = [
                item.rstrip(" ")
                for item in re.split(r"(#\w+)", event["description_bluesky"])
                if item.strip()
            ]
            for text_chunk in split_text:
                if text_chunk.startswith("#"):
                    for tag in text_chunk.split("#"):
                        if tag.strip():
                            text_builder.tag(f"#{tag.strip()}", tag.strip())
                else:
                    text_builder.text(
                        self.add_whitespace_if_needed(text_chunk)
                    )

            text_builder.text("\n\n🔗 ")
            text_builder.link(event["wiki_link"], event["wiki_link"])
            text_builder.text("\n\n")
            for tag in tags.split("#"):
                if tag.strip():
                    text_builder.tag(f"#{tag.strip()} ", tag.strip())
            return text_builder

        raise ValueError(
            f"Unsupported platform: {self.cfg['platform']}"
        )

    def send_post(self, event: Dict[str, Any], client: Any) -> None:
        """Send a post to the configured platform (Mastodon or Bluesky)."""
        self.logger.info(
            "Preparing the post on %s (%s)...",
            self.cfg["client_name"],
            self.cfg["platform"]
        )
        post_txt = self.build_post(event)

        if self.cfg["platform"] == "mastodon":
            self.send_post_to_mastodon(event, client, post_txt)
        elif self.cfg["platform"] == "bluesky":
            embed_external = self.build_embed_external(event, client)
            self.send_post_to_bluesky(event, client, post_txt, embed_external)

    def build_embed_external(
        self,
        event: Dict[str, Any],
        client: Any
    ) -> models.AppBskyEmbedExternal.Main:
        """
        Build an external embed object for Bluesky posts.

        Args:
            event: Event data dictionary.
            client: Authenticated Bluesky client.

        Returns:
            A Bluesky external embed object.
        """
        url = f"{self.base_path}/{event['img']}"
        filename = self.download_image(url)

        with open(filename, "rb") as f:
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

    def get_bluesky_did(self, platform_user_handle: str) -> Optional[str]:
        """
        Resolve a Bluesky handle into a DID.

        Args:
            platform_user_handle: User handle on Bluesky (with or without '@').

        Returns:
            The DID string if found, otherwise None.
        """
        url = (
            f"https://bsky.social/xrpc/com.atproto.identity.resolveHandle?"
            f"handle={platform_user_handle.lstrip('@')}"
        )
        try:
            response = requests.get(url, timeout=REQUEST_TIMEOUT)
            if response.status_code == 200:
                data = response.json()
                return data.get("did")
            self.logger.info(
                "Failed to retrieve data. Status code: %s",
                response.status_code)
        except requests.RequestException as e:
            self.logger.info("An error occurred: %s", e)
        return None

    @staticmethod
    def add_whitespace_if_needed(text_chunk: str) -> str:
        """Ensure spacing consistency for Bluesky text chunks."""
        return text_chunk + " " if not text_chunk.endswith(("(", "{", "[")) else text_chunk

    def send_post_to_bluesky(
        self,
        event: Dict[str, Any],
        client: Any,
        post_txt: client_utils.TextBuilder,
        embed_external: Any
    ) -> None:
        """Send a post to Bluesky with optional media embed."""
        self.logger.info(
            "Preview your post...\n\n%s",
            post_txt._buffer.getvalue().decode("utf-8")
        )
        try:
            client.send_post(text=post_txt, embed=embed_external)
            self.logger.info("Posted 🎉")
        except Exception as e:
            self.logger.exception("Exception %s for %s", e, event["name"])

    def send_post_to_mastodon(
        self,
        event: Dict[str, Any],
        client: Any,
        post_txt: str
    ) -> None:
        """Send a post to Mastodon, with media if available."""
        try:
            if event.get("img"):
                self.logger.info("Uploading media to Mastodon")
                url = f"{self.base_path}/{event['img']}"
                filename = self.download_image(url)

                media_upload = client.media_post(filename)
                description = event.get("alt") or str(event["name"])
                client.media_update(media_upload, description=description)

                client.status_post(post_txt, media_ids=media_upload)
                self.logger.info("Posted with image 🎉")
            else:
                client.status_post(post_txt)
                self.logger.info("Posted without image 🎉")
        except Exception as e:
            self.logger.exception("Exception %s for %s", e, event.get("name"))


if __name__ == "__main__":
    handler = PromoteAnniversary(config_dict=None, no_dry_run=True)
    handler.promote_anniversary()
