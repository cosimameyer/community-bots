"""Module to log into Mastodon."""

import logging
from typing import TypedDict

from mastodon import Mastodon

logger = logging.getLogger(__name__)


class MastodonConfig(TypedDict):
    """Typed configuration for Mastodon login."""
    api_base_url: str
    access_token: str


def login_mastodon(config_dict: MastodonConfig) -> tuple[dict, Mastodon]:
    """
    Log in to Mastodon and return the account and client.

    Args:
        config_dict: Configuration required for Mastodon login.

    Returns:
        A tuple containing:
            - account: The Mastodon account object.
            - client: The Mastodon client instance.
    """
    client = Mastodon(
        access_token=config_dict["access_token"],
        api_base_url=config_dict["api_base_url"],
    )

    logger.info(" > Logging in as access token holder on %s", config_dict["api_base_url"])

    account = client.me()

    logger.info(" > Successfully logged in as @%s", account["username"])

    return account, client
