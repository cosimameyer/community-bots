"""Module to login to Bluesky"""

import logging
from atproto import Client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def login_bluesky(config_dict):
    logger.info(
        ' > Logging in as %s with password <TRUNCATED>',
        config_dict['username']
    )
    client = Client()
    client.login(
        config_dict.get('username', ''), config_dict.get('password', '')
    )
    logger.info(' > Successfully logged in')

    return client
