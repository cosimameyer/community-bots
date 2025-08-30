"""Module to boost mentions that tag the community bots."""

import os
import logging
from typing import Optional, Dict, Any

from dotenv import load_dotenv

import config
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky

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
        logging.basicConfig(level=logging.INFO)

        self.process_images = False
        self.no_dry_run = no_dry_run
        self.config_dict = config_dict

    @property
    def cfg(self) -> Dict[str, Any]:
        """Property to ensure that the dictionary is initialized."""
        if self.config_dict is None:
            raise RuntimeError("Config dictionary not initialized")
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
            account, client = login_mastodon(self.config_dict)
            notifications = client.notifications(types=["mention"])
            self.logger.info(
                " > Fetched account data for %s", account.acct
            )

            self.logger.info(
                " > Beginning search-loop and toot and boost toots"
            )
            self.logger.info("------------------------")

            self.logger.info(
                " > Reading statuses to identify tootable status"
            )
            for notification in notifications:
                if (
                    not notification.status.favourited
                    and notification.status.account.acct != account.acct
                ):
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

        elif self.cfg["platform"] == "bluesky":
            client = login_bluesky(self.config_dict)
            self.logger.info(" > Fetched account data")

            self.logger.info(" > Beginning search-loop and repost posts")
            self.logger.info("------------------------")

            self.logger.info(
                " > Reading statuses to identify postable statuses"
            )
            last_seen_at = client.get_current_time_iso()
            response = client.app.bsky.notification.list_notifications()
            timeline = client.get_timeline(algorithm="reverse-chronological")
            cids = [post.post.cid for post in timeline.feed]

            for notification in response.notifications:
                if (
                    notification.reason == "mention"
                    and notification.cid not in cids
                ):
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

            client.app.bsky.notification.update_seen({"seen_at": last_seen_at})
            self.logger.info(
                "Successfully process notification. Last seen at: %s",
                last_seen_at,
            )

    def set_up_config_dict(self) -> None:
        """
        Populate the configuration dictionary with required parameters.

        Loads environment variables and values from `config` to prepare
        platform-specific settings.
        """
        self.config_dict = {
            "platform": os.getenv("PLATFORM"),
            "password": os.getenv("PASSWORD"),
            "username": os.getenv("USERNAME"),
            "client_name": os.getenv("CLIENT_NAME"),
        }
        if self.config_dict["platform"] == "mastodon":
            self.config_dict["mastodon_visiblity"] = config.MASTODON_VISIBILITY
            self.config_dict["api_base_url"] = config.API_BASE_URL
            self.config_dict["access_token"] = os.getenv("ACCESS_TOKEN")
            self.config_dict["client_cred_file"] = os.getenv(
                "BOT_CLIENTCRED_SECRET"
            )
            self.config_dict["timeline_depth_limit"] = 40
        else:
            self.config_dict["api_base_url"] = "bluesky"


if __name__ == "__main__":
    boost_mentions_handler = BoostMentions(
        config_dict=None,
        no_dry_run=True,
    )
    boost_mentions_handler.boost_mentions()
