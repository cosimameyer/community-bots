"""Module to log into Bluesky."""

import logging
from typing import TypedDict

from atproto import Client

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class BlueskyConfig(TypedDict):
    """Typed configuration for Bluesky login."""
    username: str
    password: str


def login_bluesky(config_dict: BlueskyConfig) -> Client:
    """
    Log in to Bluesky and return the client instance.

    Args:
        config_dict: Configuration required for Bluesky login.

    Returns:
        A logged-in Bluesky `Client` instance.
    """
    logger.info(
        " > Logging in as %s with password <TRUNCATED>",
        config_dict["username"],
    )

    client = Client()
    client.login(
        config_dict["username"],
        config_dict["password"],
    )

    logger.info(" > Successfully logged in")

    return client
