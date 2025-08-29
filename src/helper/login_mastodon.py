"""Module to log into Mastodon"""

import logging
from mastodon import Mastodon

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def login_mastodon(config_dict):
    client_id, client_secret = Mastodon.create_app(
                    config_dict["client_name"],
                    api_base_url=config_dict["api_base_url"])

    client = Mastodon(
        client_id=client_id,
        access_token=config_dict["access_token"],
        client_secret=client_secret,
        api_base_url=config_dict["api_base_url"],
    )
    logger.info(
        ' > Logging in as %s with password <TRUNCATED>',
        config_dict['username']
        )

    client.log_in(
        config_dict["username"],
        config_dict["password"],
    )
    account = client.me()

    logger.info(' > Successfully logged in')

    return account, client
