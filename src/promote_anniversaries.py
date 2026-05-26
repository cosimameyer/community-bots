"""
Module to promote anniversaries on Mastodon and Bluesky.
Handles fetching events, building posts, and posting to platforms.
"""

import io
import json
import logging
import os
import pathlib
import posixpath
import re
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Union, cast
from urllib.parse import urlsplit

import yaml
from PIL import Image

import requests
from dotenv import load_dotenv
from atproto import client_utils, models

import config
from helper.login_bluesky import login_bluesky, BlueskyConfig
from helper.login_mastodon import login_mastodon, MastodonConfig

load_dotenv()

REQUEST_TIMEOUT = 10  # seconds
logger = logging.getLogger(__name__)

GALLERY_WOMEN = pathlib.Path(
    os.getenv("GALLERY_PATH", "../gallery/content/amazing-women-in-tech")
)


def load_persons(gallery_path: pathlib.Path = GALLERY_WOMEN) -> List[Dict[str, Any]]:
    """
    Read per-person frontmatter from gallery index.md files.

    Each returned dict has the same keys as gallery frontmatter
    (name, anniversary, alt, wiki_link, bluesky, bio_gallery,
    bio_bluesky, bio_mastodon) plus 'img' as a pathlib.Path to
    the portrait PNG, or None when no PNG is found.
    """
    persons = []
    if not gallery_path.is_dir():
        logger.warning("Gallery path not found: %s — skipping person events", gallery_path)
        return persons
    for person_dir in sorted(gallery_path.iterdir()):
        if not person_dir.is_dir():
            continue
        index = person_dir / "index.md"
        if not index.exists():
            continue
        text = index.read_text(encoding="utf-8")
        parts = text.split("---")
        if len(parts) < 3:
            continue
        fm = yaml.safe_load(parts[1])
        if not isinstance(fm, dict):
            continue
        fm["img"] = next(person_dir.glob("*.png"), None)
        persons.append(fm)
    return persons


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
            raise RuntimeError(
                "config_dict is not set; call promote_anniversary() or pass "
                "config_dict to the constructor before accessing cfg"
            )
        return self.config_dict

    def promote_anniversary(self) -> None:
        """Main entry point. Loads configuration, fetches events, and posts if applicable."""
        if self.config_dict is None and self.no_dry_run:
            self._setup_config_from_env()

        if self.config_dict is None and self.no_dry_run:
            self.logger.error("No config_dict provided — cannot run")
            return

        if self.config_dict is not None:
            self.logger.info("Initializing %s Bot", self.cfg["client_name"])
            self.logger.info("=" * (len(self.cfg["client_name"]) + 17))
            self.logger.info(" > Connecting to %s", self.cfg["api_base_url"])

        client = self._connect_client() if self.no_dry_run else None
        if client is None and self.no_dry_run:
            self.logger.error("Failed to connect to %s", self.cfg["platform"])
            return

        gallery_path = pathlib.Path(
            self.cfg.get("gallery_path", str(GALLERY_WOMEN)) if self.config_dict else str(GALLERY_WOMEN)
        )
        events: List[Dict[str, Any]] = load_persons(gallery_path)

        special_file = self.cfg.get("events_special_file", "metadata/events_special.json") if self.config_dict else "metadata/events_special.json"
        if os.path.exists(special_file):
            with open(special_file, encoding="utf-8") as f:
                events.extend(json.load(f))

        for event in events:
            if self.is_matching_current_date(event.get("anniversary", "")):
                if not self.no_dry_run:
                    self.logger.info(
                        "[DRY RUN] Would post anniversary for %s on %s",
                        event.get("name"),
                        event.get("anniversary"),
                    )
                else:
                    self.send_post(event, client)

    def _setup_config_from_env(self) -> None:
        """Populate config_dict from environment variables (used in GitHub Actions)."""
        self.config_dict = {
            "platform": os.getenv("PLATFORM"),
            "images": os.getenv("IMAGES"),
            "password": os.getenv("PASSWORD"),
            "username": os.getenv("USERNAME"),
            "client_name": os.getenv("CLIENT_NAME"),
        }
        if self.config_dict["platform"] == "mastodon":
            self.config_dict["api_base_url"] = config.API_BASE_URL
            self.config_dict["mastodon_visibility"] = config.MASTODON_VISIBILITY
            self.config_dict["client_id"] = os.getenv("CLIENT_ID")
            self.config_dict["client_secret"] = os.getenv("CLIENT_SECRET")
            self.config_dict["access_token"] = os.getenv("ACCESS_TOKEN")
            self.config_dict["client_cred_file"] = os.getenv("BOT_CLIENTCRED_SECRET")
        else:
            self.config_dict["api_base_url"] = "https://bsky.social"
        self.config_dict.setdefault(
            "gallery_path", os.getenv("GALLERY_PATH", str(GALLERY_WOMEN))
        )
        self.config_dict.setdefault(
            "events_special_file", os.getenv("EVENTS_SPECIAL_FILE", "metadata/events_special.json")
        )

    def _connect_client(self):
        """Connect to the configured platform and return the client."""
        if self.cfg["platform"] == "mastodon":
            _, client = login_mastodon(cast(MastodonConfig, self.config_dict))
            return client
        if self.cfg["platform"] == "bluesky":
            return login_bluesky(cast(BlueskyConfig, self.config_dict))
        self.logger.error("Unsupported platform: %s", self.cfg["platform"])
        return None

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
            with requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=REQUEST_TIMEOUT
            ) as response:
                with open(file_path, "wb") as out_file:
                    shutil.copyfileobj(response.raw, out_file)
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
                f"{event['bio_mastodon']}\n\n"
                f"🔗 {event['wiki_link']}{tags}"
            )

        if self.cfg["platform"] == "bluesky":
            bluesky_max_graphemes = 300
            tag_list = [t.strip() for t in tags.split("#") if t.strip()]
            did = self.get_bluesky_did(event["bluesky"]) if event.get("bluesky") else None

            def _build(tag_subset, desc_override=None):
                desc = desc_override if desc_override is not None else event["bio_bluesky"]
                tb = client_utils.TextBuilder()
                if event.get("bluesky"):
                    tb.text("Let's meet ")
                    tb.mention(event["bluesky"], did)
                    tb.text(" ⭐️\n\n")
                else:
                    tb.text(f"Let's meet {event['name']} ⭐️\n\n")
                split_text = [
                    item.rstrip(" ")
                    for item in re.split(r"(#\w+)", desc)
                    if item.strip()
                ]
                for text_chunk in split_text:
                    if text_chunk.startswith("#"):
                        for tag in text_chunk.split("#"):
                            if tag.strip():
                                tb.tag(f"#{tag.strip()}", tag.strip())
                    else:
                        tb.text(self.add_whitespace_if_needed(text_chunk))
                tb.text("\n\n🔗 ")
                tb.link(event["wiki_link"], event["wiki_link"])
                if tag_subset:
                    tb.text("\n\n")
                    for i, tag in enumerate(tag_subset):
                        display = f"#{tag}" if i == len(tag_subset) - 1 else f"#{tag} "
                        tb.tag(display, tag)
                return tb

            # Drop trailing tags one by one until within limit
            for count in range(len(tag_list), -1, -1):
                text_builder = _build(tag_list[:count])
                if len(text_builder.build_text()) <= bluesky_max_graphemes:
                    return text_builder

            # Still over limit: trim description to fit
            overhead = len(_build([], desc_override="").build_text())
            available = bluesky_max_graphemes - overhead - 1  # -1 for "…"
            desc_trimmed = event["bio_bluesky"][:available].rstrip() + "…"
            return _build([], desc_override=desc_trimmed)

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
            embed_external = (
                self.build_embed_external(event, client) if event.get("img") else None
            )
            self.send_post_to_bluesky(event, client, post_txt, embed_external)

    def _resolve_image(self, event: Dict[str, Any]) -> tuple:
        """
        Return (local_filepath, uri) for the event image.

        For gallery persons, img is a pathlib.Path to a local file;
        for special events it is a bare filename fetched from base_path.
        """
        img = event.get("img")
        if isinstance(img, pathlib.Path) and img.exists():
            return str(img), event.get("wiki_link", str(img))
        filename_str = str(img) if img else ""
        url = f"{self.base_path}/{filename_str}"
        return self.download_image(url), url

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
        filename, uri = self._resolve_image(event)

        with open(filename, "rb") as f:
            img_data = f.read()

        img_data = self._compress_for_bluesky(img_data)
        if len(img_data) > self._BLUESKY_MAX_BLOB_BYTES:
            self.logger.warning(
                "Image still exceeds Bluesky blob limit (%d bytes) after compression — upload may fail.",
                len(img_data),
            )
        thumb = client.upload_blob(img_data)

        return models.AppBskyEmbedExternal.Main(
            external=models.AppBskyEmbedExternal.External(
                title=f"Image of {event['name']}",
                description=event.get("alt", ""),
                uri=uri,
                thumb=thumb.blob,
            )
        )

    _BLUESKY_MAX_BLOB_BYTES = 1_000_000

    @staticmethod
    def _compress_for_bluesky(img_data: bytes) -> bytes:
        """Return img_data compressed to under 1 MB for Bluesky, converting to JPEG if needed."""
        if len(img_data) <= PromoteAnniversary._BLUESKY_MAX_BLOB_BYTES:
            return img_data
        image = Image.open(io.BytesIO(img_data)).convert("RGB")
        for quality in (85, 70, 55, 40):
            buf = io.BytesIO()
            image.save(buf, format="JPEG", quality=quality, optimize=True)
            if buf.tell() <= PromoteAnniversary._BLUESKY_MAX_BLOB_BYTES:
                return buf.getvalue()
        return buf.getvalue()

    @staticmethod
    def get_bluesky_did(platform_user_handle: str) -> Optional[str]:
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
            logger.warning(
                "Failed to retrieve data. Status code: %s",
                response.status_code,
            )
        except requests.RequestException as e:
            logger.warning("An error occurred: %s", e)
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
            post_txt.build_text()
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
        if event.get("img"):
            try:
                self.logger.info("Uploading media to Mastodon")
                filename, _ = self._resolve_image(event)

                media_upload = client.media_post(filename)
                description = event.get("alt") or str(event["name"])
                client.media_update(media_upload, description=description)

                client.status_post(post_txt, media_ids=[media_upload])
                self.logger.info("Posted with image 🎉")
                return
            except Exception as e:
                self.logger.exception(
                    "Media upload failed for %s: %s — falling back to text-only",
                    event.get("name"),
                    e,
                )

        try:
            client.status_post(post_txt)
            self.logger.info("Posted without image 🎉")
        except Exception as e:
            self.logger.exception("Exception %s for %s", e, event.get("name"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    handler = PromoteAnniversary(config_dict=None, no_dry_run=True)
    handler.promote_anniversary()
