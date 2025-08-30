"""Module to log into Bluesky."""

import logging
from typing import Dict, Any

from atproto import Client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def login_bluesky(config_dict: Dict[str, Any]) -> Client:
    """
    Log in to Bluesky and return the client instance.

    Args:
        config_dict: A dictionary containing Bluesky login credentials:
            - username: str
            - password: str

    Returns:
        A logged-in Bluesky `Client` instance.
    """
    logger.info(
        " > Logging in as %s with password <TRUNCATED>",
        config_dict["username"],
    )

    client = Client()
    client.login(
        config_dict.get("username", ""),
        config_dict.get("password", ""),
    )

    logger.info(" > Successfully logged in")

    return client
