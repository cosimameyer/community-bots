"""Module to log into Mastodon."""

import logging
from typing import Tuple, Dict, Any

from mastodon import Mastodon, MastodonNotFoundError, MastodonAPIError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def login_mastodon(config_dict: Dict[str, Any]) -> Tuple[Any, Mastodon]:
    """
    Log in to Mastodon and return the account and client.

    Args:
        config_dict: A dictionary containing authentication details and
            Mastodon configuration, including:
                - client_name: str
                - api_base_url: str
                - access_token: str
                - username: str
                - password: str

    Returns:
        A tuple containing:
            - account: The Mastodon account object for the logged-in user.
            - client: The Mastodon client instance.

    Raises:
        MastodonNotFoundError: If the instance cannot be reached.
        MastodonAPIError: If authentication fails or API errors occur.
    """
    client_id, client_secret = Mastodon.create_app(
        config_dict["client_name"],
        api_base_url=config_dict["api_base_url"],
    )

    client = Mastodon(
        client_id=client_id,
        access_token=config_dict["access_token"],
        client_secret=client_secret,
        api_base_url=config_dict["api_base_url"],
    )
    logger.info(
        " > Logging in as %s with password <TRUNCATED>",
        config_dict["username"],
    )

    client.log_in(
        config_dict["username"],
        config_dict["password"],
    )
    account = client.me()

    logger.info(" > Successfully logged in")

    return account, client
