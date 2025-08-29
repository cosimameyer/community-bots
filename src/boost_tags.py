"""Module to boost posts containing specific tags using community bots."""

import time
import os
import logging
from urllib.parse import urlparse
from dotenv import load_dotenv

import config
from helper.login_bluesky import login_bluesky

load_dotenv()


class BoostTags:
    """
    Handles boosting of posts containing specified tags across different platforms.
    Currently supports Bluesky. Mastodon support is stubbed.
    """

    def __init__(self, config_dict: dict | None = None, no_dry_run: bool = True) -> None:
        """
        Initialize the BoostTags handler.

        Args:
            config_dict (dict | None): Configuration dictionary for the bot.
                If None, values will be loaded from environment variables.
            no_dry_run (bool): If True, actually perform reposts instead of dry-run.
        """
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)

        self.config_dict = config_dict
        self.no_dry_run = no_dry_run

    def repost_tags_mastodon(self, client) -> None:
        """
        Repost Mastodon statuses containing the configured tags.

        Args:
            client: Authenticated Mastodon client instance.

        Notes:
            Currently non-functional since account fetching is commented out.
        """
        if "tags" not in self.config_dict:
            self.logger.warning("No tags configured for Mastodon reposts.")
            return

        for tag in self.config_dict["tags"]:
            tag = tag.lower().strip("# ")
            self.logger.info("Reading timeline for new toots tagged #%s", tag)

            try:
                statuses = client.timeline_hashtag(
                    tag,
                    limit=self.config_dict.get("timeline_depth_limit", 40),
                )
            except Exception as e:  # TODO: Replace with specific Mastodon exception
                self.logger.error("Network error while fetching statuses: %s. Retrying...", e)
                time.sleep(30)
                continue

            time.sleep(0.1)  # rate limiting

            for status in statuses:
                domain = urlparse(status.url).netloc
                # BUG: `account` undefined since login_mastodon is commented out
                if (
                    not status.favourited
                    and status.account.acct != account.acct  # <-- FIX NEEDED
                    and domain not in config.IGNORE_SERVERS
                ):
                    self.logger.info(
                        "Boosting toot by %s tagged #%s (%s)",
                        status.account.username,
                        tag,
                        status.url,
                    )
                    client.status_reblog(status.id)
                    client.status_favourite(status.id)

    def boost_tags(self) -> None:
        """
        Main entrypoint to start boosting tags based on configuration.

        Loads configuration from environment variables if not provided.
        Handles platform-specific reposting logic.
        """
        if self.config_dict is None and self.no_dry_run:
            self._load_config_from_env()

        platform = self.config_dict.get("platform")
        client_name = self.config_dict.get("client_name", "Unknown")
        self.logger.info("========")
        self.logger.info("Initializing %s Bot", client_name)
        self.logger.info("=" * (20 + len(client_name)))
        self.logger.info("Connecting to %s", self.config_dict["api_base_url"])

        if platform == "mastodon":
            self._boost_tags_mastodon()
            self.logger.warning("Mastodon support is currently not implemented.")
        elif platform == "bluesky":
            self._boost_tags_bluesky()
        else:
            self.logger.error("Unsupported platform: %s", platform)

    def _load_config_from_env(self) -> None:
        """Load configuration values from environment variables into self.config_dict."""
        self.config_dict = {
            "platform": os.getenv("PLATFORM", "").lower(),
            "password": os.getenv("PASSWORD"),
            "username": os.getenv("USERNAME"),
            "client_name": os.getenv("CLIENT_NAME", "CommunityBot"),
            "tags": os.getenv("TAGS_TO_BOOST", "").split(","),
        }
        if self.config_dict["platform"] == "mastodon":
            self.config_dict.update({
                "mastodon_visibility": config.MASTODON_VISIBILITY,
                "api_base_url": config.API_BASE_URL,
                "access_token": os.getenv("ACCESS_TOKEN"),
                "client_cred_file": os.getenv("BOT_CLIENTCRED_SECRET"),
                "timeline_depth_limit": 40,
            })
        else:
            self.config_dict["api_base_url"] = "bluesky"
            
    def _boost_tags_mastodon(self) -> None:
        """Handle reposting tags on Mastodon."""
            # # Commented because it wasn't fully working

            # account, client = login_mastodon(config_dict)
            # self.logger.info(f" > Fetched account data for {account.acct}")

            # repost_tags_mastodon(client, config_dict)
            self.logger.info(
                """
                This feature currently doesn't work for Mastodon.
                It's deployed using AWS.
                """
            )

    def _boost_tags_bluesky(self) -> None:
        """Handle reposting tags on Bluesky."""
        if not self.no_dry_run:
            self.logger.info("Dry-run mode: no reposts will be made.")
            return

        client = login_bluesky(self.config_dict)
        self.logger.info("Fetched Bluesky account data.")
        self.logger.info("Starting search-loop for reposting.")

        timeline = client.get_timeline(algorithm="reverse-chronological")
        seen_cids = {post.post.cid for post in timeline.feed}

        for tag in self.config_dict["tags"]:
            response = client.app.bsky.feed.search_posts(
                params={"q": tag, "tag": [tag], "sort": "top", "limit": 50}
            )
            for post in response.posts:
                tags_in_post = {
                    t.strip("#").lower()
                    for t in post.record.text.split()
                    if t.startswith("#")
                }

                if tag.lower() in tags_in_post and post.cid not in seen_cids:
                    try:
                        result = client.repost(uri=post.uri, cid=post.cid)
                        self.logger.info(
                            "Reposted post by %s (ref: %s)",
                            post.author.handle, result
                        )
                    except Exception as e:
                        self.logger.error(
                            "Failed to repost URI %s, CID %s: %s",
                            post.uri,
                            post.cid,
                            e,
                        )
                    time.sleep(0.1)  # avoid hammering API

        self.logger.info("Finished processing Bluesky reposts.")


if __name__ == "__main__":
    bot = BoostTags()
    bot.boost_tags()
