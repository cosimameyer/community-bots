"""Module to boost posts containing specific tags using community bots."""

import json
import re
import time
import os
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, cast
from dotenv import load_dotenv

import config
from helper.login_bluesky import login_bluesky, BlueskyConfig

try:
    from mastodon import MastodonNetworkError, MastodonAPIError  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    class MastodonNetworkError(Exception):
        """Fallback Mastodon network error."""

    class MastodonAPIError(Exception):
        """Fallback Mastodon API error."""

try:
    from atproto.exceptions import AtProtocolError  # type: ignore
    from atproto_client.exceptions import InvokeTimeoutError  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    class AtProtocolError(Exception):
        """Fallback Bluesky/AtProto error."""

    class InvokeTimeoutError(Exception):
        """Fallback Bluesky timeout error."""


load_dotenv()


class BoostTags:
    """
    Handles boosting of posts containing specified tags across different platforms.
    Currently supports Bluesky. Mastodon support is stubbed.
    """

    def __init__(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        no_dry_run: bool = True,
    ) -> None:
        """
        Initialize the BoostTags handler.

        Args:
            config_dict: Optional configuration dictionary for the bot.
            no_dry_run: If True, actually perform reposts; if False, dry run.
        """
        self.logger = logging.getLogger(__name__)

        self.no_dry_run = no_dry_run
        self.config_dict = config_dict

    @property
    def cfg(self) -> Dict[str, Any]:
        """Property to ensure that the dictionary is initialized."""
        if self.config_dict is None:
            raise RuntimeError(
                "config_dict is not set; call boost_tags() or pass "
                "config_dict to the constructor before accessing cfg"
            )
        return self.config_dict

    def boost_tags(self) -> None:
        """
        Main entrypoint to start boosting tags based on configuration.

        Loads configuration from environment variables if not provided.
        Handles platform-specific reposting logic.
        """
        self.set_up_config_dict()

        client_name = self.cfg.get("client_name", "Unknown")
        self.logger.info("========")
        self.logger.info("Initializing %s Bot", client_name)
        self.logger.info("=" * (20 + len(client_name)))
        self.logger.info(" > Connecting to %s", self.cfg["api_base_url"])

        if self.cfg["platform"] == "mastodon":
            self._boost_tags_mastodon()
        elif self.cfg["platform"] == "bluesky":
            self._boost_tags_bluesky()

    def set_up_config_dict(self) -> None:
        """
        Populate the configuration dictionary with required parameters.

        Loads environment variables and values from `config` to prepare
        platform-specific settings.
        """
        if self.config_dict is None:
            self.config_dict = {}
        platform = (os.getenv("PLATFORM") or "").lower()
        if not platform and not self.config_dict.get("platform"):
            raise ValueError("PLATFORM environment variable is not set.")
        self.config_dict.setdefault("platform", platform)
        self.config_dict.setdefault("password", os.getenv("PASSWORD"))
        self.config_dict.setdefault("username", os.getenv("USERNAME"))
        self.config_dict.setdefault("client_name", os.getenv("CLIENT_NAME", "CommunityBot"))
        self.config_dict.setdefault(
            "tags",
            [t.strip() for t in os.getenv("TAGS_TO_BOOST", "").split(",") if t.strip()],
        )
        self.config_dict.setdefault("max_boosts_per_run", 5)
        if self.config_dict["platform"] == "mastodon":
            self.config_dict.setdefault("mastodon_visibility", config.MASTODON_VISIBILITY)
            self.config_dict.setdefault("api_base_url", config.API_BASE_URL)
            self.config_dict.setdefault("access_token", os.getenv("ACCESS_TOKEN"))
            self.config_dict.setdefault(
                "client_cred_file", os.getenv("BOT_CLIENTCRED_SECRET")
            )
            self.config_dict.setdefault("timeline_depth_limit", 40)
        elif self.config_dict["platform"] == "bluesky":
            self.config_dict.setdefault("api_base_url", "https://bsky.social")
        else:
            raise ValueError(
                f"Unknown platform: {self.config_dict['platform']!r}. "
                "Expected 'mastodon' or 'bluesky'."
            )

    def _boost_tags_mastodon(self) -> None:
        """Handle reposting tags on Mastodon."""
        raise NotImplementedError("Mastodon tag boosting is not yet implemented.")

    _SEEN_CIDS_FILE = Path("metadata/bluesky_seen_cids.json")
    _SEEN_CIDS_MAX_AGE_DAYS = 7
    _VALID_TAG_PATTERN = re.compile(r'^[a-zA-Z0-9_]{1,100}$')

    def _load_seen_cids(self) -> dict:
        """Load persistent seen-CIDs from file, pruning entries older than 7 days."""
        if self._SEEN_CIDS_FILE.exists():
            try:
                with self._SEEN_CIDS_FILE.open("r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {}
        else:
            data = {}
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._SEEN_CIDS_MAX_AGE_DAYS)
        return {
            cid: ts
            for cid, ts in data.items()
            if datetime.fromisoformat(ts) > cutoff
        }

    def _save_seen_cids(self, seen_cids: dict) -> None:
        """Save persistent seen-CIDs to file."""
        try:
            self._SEEN_CIDS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with self._SEEN_CIDS_FILE.open("w", encoding="utf-8") as f:
                json.dump(seen_cids, f, ensure_ascii=False, indent=2)
        except OSError as e:
            self.logger.warning("Could not save seen CIDs file: %s", e)

    def _boost_tags_bluesky(self) -> None:
        """Handle reposting tags on Bluesky."""
        # Fix 1: validate tags from config before proceeding
        raw_tags = self.cfg.get("tags", [])
        if isinstance(raw_tags, str):
            raw_tag_list = [t.strip().lstrip('#') for t in raw_tags.split(',')]
        else:
            raw_tag_list = [t.strip().lstrip('#') for t in raw_tags]
        valid_tags = [t for t in raw_tag_list if self._VALID_TAG_PATTERN.match(t)]
        if not valid_tags:
            self.logger.warning("No valid tags after validation — skipping boost.")
            return

        try:
            client = login_bluesky(cast(BlueskyConfig, self.config_dict))
        except InvokeTimeoutError:
            self.logger.error("Timed out while logging in to Bluesky. Aborting.")
            return
        self.logger.info(" > Fetched Bluesky account data.")
        self.logger.info(" > Starting search-loop for reposting.")

        # Fix 9: use persistent seen-CIDs file instead of single-page timeline dedup
        seen_cids_dict = self._load_seen_cids()
        try:
            timeline = client.get_timeline(algorithm="reverse-chronological")
            now_ts = datetime.now(timezone.utc).isoformat()
            for post in timeline.feed:
                seen_cids_dict[post.post.cid] = now_ts
        except InvokeTimeoutError:
            self.logger.error("Timed out fetching timeline. Aborting.")
            return
        seen_cids = set(seen_cids_dict.keys())

        max_boosts = self.cfg.get("max_boosts_per_run", 5)
        boost_count = 0

        for tag in valid_tags:
            tag = tag.lower().strip("# ")
            self.logger.info(" > Searching for tag #%s", tag)
            if boost_count >= max_boosts:
                self.logger.info(
                    " > Reached max boosts per run (%d), stopping.", max_boosts
                )
                break

            try:
                response = client.app.bsky.feed.search_posts(
                    params={"q": tag, "tag": [tag], "sort": "top", "limit": 50}
                )
            except InvokeTimeoutError:
                self.logger.error("Timed out searching posts for tag #%s. Skipping.", tag)
                continue
            for post in response.posts:
                if boost_count >= max_boosts:
                    break

                # Prefer facets (structured ATProto tags) over text parsing.
                tags_in_post: set = set()
                for facet in (getattr(post.record, "facets", None) or []):
                    for feature in facet.features:
                        if hasattr(feature, "tag"):
                            tags_in_post.add(feature.tag.lower())
                if not tags_in_post:
                    tags_in_post = {
                        t.strip("#.,!?").lower()
                        for t in post.record.text.split()
                        if t.startswith("#")
                    }

                own_handle = (self.cfg.get("username") or "").lower()
                if (
                    tag in tags_in_post
                    and post.cid not in seen_cids
                    and post.author.handle.lower() != own_handle
                ):
                    if not self.no_dry_run:
                        self.logger.info(
                            "   * [DRY RUN] Would repost URI %s CID %s by %s",
                            post.uri,
                            post.cid,
                            post.author.handle,
                        )
                        seen_cids.add(post.cid)
                        seen_cids_dict[post.cid] = datetime.now(timezone.utc).isoformat()
                        boost_count += 1
                    else:
                        try:
                            result = client.repost(uri=post.uri, cid=post.cid)
                            self.logger.info(
                                "   * Reposted post by %s (ref: %s)",
                                post.author.handle,
                                result,
                            )
                            seen_cids.add(post.cid)
                            seen_cids_dict[post.cid] = datetime.now(timezone.utc).isoformat()
                            boost_count += 1
                        except AtProtocolError as e:
                            self.logger.error(
                                "   * Failed to repost URI %s, CID %s: %s",
                                post.uri,
                                post.cid,
                                e,
                            )
                    time.sleep(0.1)  # avoid hammering API

        self._save_seen_cids(seen_cids_dict)
        self.logger.info("Finished processing Bluesky reposts.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = BoostTags()
    bot.boost_tags()
