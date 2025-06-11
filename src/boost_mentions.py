"""Module to boost mentions that tag the community bots"""

import os
import logging
from dotenv import load_dotenv

import config
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky

load_dotenv()


class BoostMentions():
    """
    Class to handle boosting mentions of the community bots.
    """
    def __init__(self, config_dict=None, no_dry_run=True):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

        self.process_images = False
        self.no_dry_run = no_dry_run
        self.config_dict = config_dict

    def boost_mentions(self):
        """
        Method to boost mentions on social media platforms.
        """
        self.set_up_config_dict()

        self.logger("==========================")
        client_name = self.config_dict.get("client_name")
        self.logger(f"Initializing {client_name} Bot")
        self.logger("=================" + "=" * len(client_name or ""))
        self.logger(f" > Connecting to {self.config_dict['api_base_url']}")

        if self.config_dict["platform"] == "mastodon":
            account, client = login_mastodon(self.config_dict)
            notifications = client.notifications(types=['mention'])
            self.logger(f" > Fetched account data for {account.acct}")

            self.logger(" > Beginning search-loop and toot and boost toots")
            self.logger("------------------------")

            self.logger(" > Reading statuses to identify tootable statuses")
            for notification in notifications:
                if not notification.status.favourited and \
                        notification.status.account.acct != account.acct:
                    # Boost and favorite the new status
                    try:
                        self.logger(
                            f"   * Boosting new toot by "
                            f"{notification.account.username} "
                            f"viewable at: {notification.status.url}"
                        )
                        client.status_reblog(notification.status.id)
                        client.status_favourite(notification.status.id)
                    except Exception as e:
                        self.logger(
                            f"   * Boosting new toot by "
                            f" {notification.account.username} did not work "
                            f"because {e}- going to the next toot."
                        )
        elif self.config_dict["platform"] == "bluesky":
            client = login_bluesky(self.config_dict)
            self.logger(" > Fetched account data")

            self.logger(" > Beginning search-loop and repost posts")
            self.logger("------------------------")

            self.logger(" > Reading statuses to identify postable statuses")
            last_seen_at = client.get_current_time_iso()
            response = client.app.bsky.notification.list_notifications()
            timeline = client.get_timeline(algorithm='reverse-chronological')
            cids = [post.post.cid for post in timeline.feed]

            for notification in response.notifications:
                if (
                    notification.reason == "mention"
                    and notification.cid not in cids
                ):
                    try:
                        self.logger(
                            '   * Reposted post reference:',
                            client.repost(
                                uri=notification.uri,
                                cid=notification.cid
                            )
                        )
                    except Exception as e:
                        self.logger(
                            f"""
                               * Reposting new post with URI {notification.uri}
                            and CID {notification.cid} did not work because
                            of {e} - going to the next post.
                            """
                        )

            client.app.bsky.notification.update_seen({'seen_at': last_seen_at})
            self.logger(
                'Successfully process notification. Last seen at:',
                last_seen_at
            )

    def set_up_config_dict(self):
        """
        Method to set up the config dictionary with the required parameters
        """
        self.config_dict = {
            "platform": os.getenv("PLATFORM"),
            "password": os.getenv("PASSWORD"),
            "username": os.getenv("USERNAME"),
            "client_name": os.getenv("CLIENT_NAME")
        }
        if self.config_dict["platform"] == "mastodon":
            self.config_dict["mastodon_visiblity"] = config.MASTODON_VISIBILITY
            self.config_dict["api_base_url"] = config.API_BASE_URL
            self.config_dict["access_token"] = os.getenv("ACCESS_TOKEN")
            self.config_dict["client_cred_file"] = os.getenv(
                'BOT_CLIENTCRED_SECRET'
            )
            self.config_dict["timeline_depth_limit"] = 40
        else:
            self.config_dict["api_base_url"] = "bluesky"


if __name__ == "__main__":
    boost_mentions_handler = BoostMentions(config_dict=None, no_dry_run=True)
    boost_mentions_handler.boost_mentions()
