"""Module to boost mentions that tag the community bots."""

import os
import logging
from typing import Optional, Dict, Any, cast

from dotenv import load_dotenv

import config
from helper.login_mastodon import login_mastodon, MastodonConfig
from helper.login_bluesky import login_bluesky, BlueskyConfig

load_dotenv()


class BoostMentions:
    """
    Handle boosting mentions of the community bots across platforms.

    This class connects to either Mastodon or Bluesky depending on
    configuration and boosts or reposts mentions accordingly.
    """

    def __init__(
        self,
        config_dict: Optional[Dict[str, Any]] = None,
        no_dry_run: bool = True
    ) -> None:
        """
        Initialize the BoostMentions handler.

        Args:
            config_dict: Optional configuration dictionary.
            no_dry_run: If True, perform actual boosts; if False, dry run.
        """
        self.logger = logging.getLogger(__name__)

        self.process_images = False
        self.no_dry_run = no_dry_run
        self.config_dict = config_dict

    @property
    def cfg(self) -> Dict[str, Any]:
        """Property to ensure that the dictionary is initialized."""
        if self.config_dict is None:
            raise RuntimeError(
                "config_dict is not set; call boost_mentions() or pass "
                "config_dict to the constructor before accessing cfg"
            )
        return self.config_dict

    def boost_mentions(self) -> None:
        """
        Boost mentions on the configured social media platform.

        Connects to the appropriate API (Mastodon or Bluesky) and processes
        notifications to identify mentions. When found, the mention is
        boosted, favorited, or reposted depending on platform.
        """
        self.set_up_config_dict()

        self.logger.info("==========================")
        client_name = self.cfg.get("client_name")
        self.logger.info("Initializing %s Bot", client_name)
        self.logger.info("=================%s", "=" * len(client_name or ""))
        self.logger.info(
            " > Connecting to %s", self.cfg["api_base_url"]
        )

        if self.cfg["platform"] == "mastodon":
            self._boost_mentions_mastodon()
        elif self.cfg["platform"] == "bluesky":
            self._boost_mentions_bluesky()

    def _boost_mentions_mastodon(self) -> None:
        """Fetch and boost Mastodon mentions."""
        account, client = login_mastodon(cast(MastodonConfig, self.config_dict))
        notifications = client.notifications(types=["mention"])
        self.logger.info(" > Fetched account data for %s", account.acct)
        self.logger.info(" > Beginning search-loop and toot and boost toots")
        self.logger.info("------------------------")
        self.logger.info(" > Reading statuses to identify tootable status")

        for notification in notifications:
            if (
                not notification.status.favourited
                and notification.status.account.acct != account.acct
            ):
                if not self.no_dry_run:
                    self.logger.info(
                        "   * [DRY RUN] Would boost toot by %s viewable at: %s",
                        notification.account.username,
                        notification.status.url,
                    )
                else:
                    try:
                        self.logger.info(
                            "   * Boosting new toot by %s viewable at: %s",
                            notification.account.username,
                            notification.status.url,
                        )
                        client.status_reblog(notification.status.id)
                        client.status_favourite(notification.status.id)
                    except Exception as e:
                        self.logger.info(
                            "   * Boosting new toot by %s did not work: %s",
                            notification.account.username,
                            e,
                        )

    def _boost_mentions_bluesky(self) -> None:
        """Fetch and repost Bluesky mentions."""
        client = login_bluesky(cast(BlueskyConfig, self.config_dict))
        self.logger.info(" > Fetched account data")
        self.logger.info(" > Beginning search-loop and repost posts")
        self.logger.info("------------------------")
        self.logger.info(" > Reading statuses to identify postable statuses")

        last_seen_at = client.get_current_time_iso()
        response = client.app.bsky.notification.list_notifications()
        timeline = client.get_timeline(algorithm="reverse-chronological")
        cids = [post.post.cid for post in timeline.feed]

        for notification in response.notifications:
            if (
                notification.reason == "mention"
                and notification.cid not in cids
            ):
                if not self.no_dry_run:
                    self.logger.info(
                        "   * [DRY RUN] Would repost URI %s CID %s",
                        notification.uri,
                        notification.cid,
                    )
                else:
                    try:
                        self.logger.info(
                            "   * Reposted post reference: %s",
                            client.repost(
                                uri=notification.uri,
                                cid=notification.cid,
                            ),
                        )
                    except Exception as e:
                        self.logger.info(
                            (
                                "   * Reposting new post with URI %s and "
                                "CID %s did not work because of %s - "
                                "going to the next post."
                            ),
                            notification.uri,
                            notification.cid,
                            e,
                        )

        if self.no_dry_run:
            client.app.bsky.notification.update_seen({"seen_at": last_seen_at})
        self.logger.info(
            "Successfully processed notifications. Last seen at: %s",
            last_seen_at,
        )

    def set_up_config_dict(self) -> None:
        """
        Populate the configuration dictionary with required parameters.

        Loads environment variables and values from `config` to prepare
        platform-specific settings.
        """
        if self.config_dict is None:
            self.config_dict = {}
        self.config_dict.setdefault("platform", os.getenv("PLATFORM"))
        self.config_dict.setdefault("password", os.getenv("PASSWORD"))
        self.config_dict.setdefault("username", os.getenv("USERNAME"))
        self.config_dict.setdefault("client_name", os.getenv("CLIENT_NAME"))
        if self.config_dict["platform"] == "mastodon":
            self.config_dict.setdefault("mastodon_visiblity", config.MASTODON_VISIBILITY)
            self.config_dict.setdefault("api_base_url", config.API_BASE_URL)
            self.config_dict.setdefault("access_token", os.getenv("ACCESS_TOKEN"))
            self.config_dict.setdefault(
                "client_cred_file", os.getenv("BOT_CLIENTCRED_SECRET")
            )
            self.config_dict.setdefault("timeline_depth_limit", 40)
        else:
            self.config_dict.setdefault("api_base_url", "bluesky")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    boost_mentions_handler = BoostMentions(
        config_dict=None,
        no_dry_run=True,
    )
    boost_mentions_handler.boost_mentions()
