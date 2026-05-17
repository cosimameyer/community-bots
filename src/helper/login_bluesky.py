"""Module to log into Bluesky."""

import logging
import time
from typing import TypedDict

from atproto import Client

logger = logging.getLogger(__name__)

# Suppress credential-adjacent debug output from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("atproto").setLevel(logging.WARNING)
logging.getLogger("atproto_client").setLevel(logging.WARNING)

_MAX_LOGIN_ATTEMPTS = 3
_RETRY_BASE_DELAY_SECONDS = 30


class BlueskyConfig(TypedDict):
    """Typed configuration for Bluesky login."""
    username: str
    password: str


def login_bluesky(config_dict: BlueskyConfig) -> Client:
    """
    Log in to Bluesky and return the client instance.

    Retries up to 3 times with linear backoff to handle transient 403s
    caused by shared-IP rate limiting on the createSession endpoint.

    Args:
        config_dict: Configuration required for Bluesky login.

    Returns:
        A logged-in Bluesky `Client` instance.
    """
    logger.info(" > Logging in as %s", config_dict["username"])

    last_exception: Exception | None = None
    for attempt in range(_MAX_LOGIN_ATTEMPTS):
        try:
            client = Client()
            profile = client.login(
                config_dict["username"],
                config_dict["password"],
            )
            logger.info(" > Successfully logged in as @%s", profile.handle)
            return client
        except Exception as e:
            last_exception = e
            if attempt < _MAX_LOGIN_ATTEMPTS - 1:
                delay = _RETRY_BASE_DELAY_SECONDS * (attempt + 1)
                logger.warning(
                    " > Login attempt %d/%d failed (%s), retrying in %ds",
                    attempt + 1,
                    _MAX_LOGIN_ATTEMPTS,
                    e,
                    delay,
                )
                time.sleep(delay)

    raise last_exception
