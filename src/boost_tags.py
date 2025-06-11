"""Module to boost tags with the community bots"""
import time
import os
import logging
from urllib.parse import urlparse
from dotenv import load_dotenv

import config
from helper.login_bluesky import login_bluesky

load_dotenv()


class BoostTags():
    """
    Class to handle boosting tags by the community bots.
    """
    def __init__(self, config_dict=None, no_dry_run=True):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

        self.config_dict = config_dict
        self.no_dry_run = no_dry_run

    def repost_tags_mastodon(self, client):
        """
        Method to repost posts using specified tags on Mastodon.
        """
        for tag in self.config_dict["tags"]:
            tag = tag.lower().strip("# ")
            self.logger.info(
                " > Reading timeline for new toots tagged #%s",
                tag
            )

            try:
                statuses = client.timeline_hashtag(
                    tag,
                    limit=self.config_dict["timeline_depth_limit"]
                )
            except Exception as e:
                self.logger.info(
                    "! Network error while attempting to fetch statuses: %s. "
                    "Trying again...",
                    e,
                )
                time.sleep(30)
                continue

            # Sleep momentarily so we don't get rate limited.
            time.sleep(0.1)

            self.logger.info(
                " > Reading statuses to identify tootable statuses"
            )
            for status in statuses:
                domain = urlparse(status.url).netloc
                if not status.favourited and \
                        status.account.acct != account.acct and \
                        domain not in config.IGNORE_SERVERS:
                    # Boost and favorite the new status
                    self.logger.info(
                        "* Boosting new toot by %s using tag #%s "
                        "viewable at: %s",
                        status.account.username,
                        tag,
                        status.url,
                    )
                    client.status_reblog(status.id)
                    client.status_favourite(status.id)

    def boost_tags(self):
        """
        Method to boost tags.
        """
        if (self.config_dict is None) and (self.no_dry_run):
            self.config_dict = {
                "platform": os.getenv("PLATFORM"),
                "password": os.getenv("PASSWORD"),
                "username": os.getenv("USERNAME"),
                "client_name": os.getenv("CLIENT_NAME"),
                "tags": os.getenv("TAGS_TO_BOOST")
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

        self.logger.info("========")
        client_name = self.config_dict['client_name']
        self.logger.info("Initializing %s Bot", client_name)
        separator = "=================" + "=" * len(client_name)
        self.logger.info(separator)
        self.logger.info(
            " > Connecting to %s", self.config_dict['api_base_url']
        )

        if self.config_dict["platform"] == "mastodon":
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
        elif self.config_dict["platform"] == "bluesky":
            client = login_bluesky(self.config_dict)
            self.logger.info(" > Fetched account data")

            self.logger.info(" > Beginning search-loop and repost posts")
            self.logger.info("------------------------")

            timeline = client.get_timeline(algorithm='reverse-chronological')
            cids = [post.post.cid for post in timeline.feed]
            for tag in [self.config_dict['tags']]:
                r = client.app.bsky.feed.search_posts(
                    params={
                        "q": tag,
                        "tag": [tag],
                        "sort": 'top',
                        "limit": 50
                    }
                )
                for post in r.posts:
                    text = post.record.text
                    tags_list = [
                        tag.strip("#").lower()
                        for tag in text.split()
                        if tag.startswith("#")
                    ]
                    self.logger.info("---------------------")
                    self.logger("Repost post by %s", post.author.handle)
                    self.logger.info(post.record.text)
                    self.logger.info("Tag list: %s", tags_list)
                    if tag in tags_list and post.cid not in cids:
                        try:
                            result = client.repost(uri=post.uri, cid=post.cid)
                            self.logger.info(
                                "   * Reposted post reference: %s", result
                            )
                        except Exception as e:
                            self.logger.info(
                                "* Reposting new post with URI %s and CID %s "
                                "did not work because of %s "
                                "- going to the next post.",
                                post.uri,
                                post.cid,
                                e,
                            )
                        time.sleep(0.1)
            self.logger.info('Successfully process notification.')


if __name__ == "__main__":
    boost_tags_handler = BoostTags(config_dict=None, no_dry_run=True)
    boost_tags_handler.boost_tags()
