"""Script to check that content length does not exceed 500 characters."""

import json
import sys
import logging
from typing import Any, Dict, List, Optional

MAX_POST_LENGTH = 500

logger = logging.getLogger(__name__)


def load_json(filename: str) -> Optional[List[Dict[str, Any]]]:
    """
    Load JSON data from a file.

    Args:
        filename: Path to the JSON file.

    Returns:
        Parsed JSON data as a list of dictionaries,
        or None if the file is missing or invalid.
    """
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error("Error: The file '%s' was not found.", filename)
        return None
    except json.JSONDecodeError:
        logger.error(
            "Error: The file '%s' contains invalid JSON.",
            filename
        )
        return None


def check_entries(data: List[Dict[str, Any]]) -> None:
    """
    Check if combined length of `name`, `description`, and `wiki_link`
    exceeds 500 characters for any entry.

    Args:
        data: List of entries to validate.

    Raises:
        SystemExit: If any entry exceeds 500 characters.
    """
    if not data:
        logger.warning("Warning: No entries found to check.")
        return
    for entry in data:
        name = entry.get('name', '')
        combined_text = (
            f"Let's meet {name} ✨\n\n"
            f"{entry.get('description', '')}\n\n"
            f"🔗 {entry.get('wiki_link', '')}\n\n"
            "#amazingwomeninstem #womeninstem "
            "#womenalsoknow #impactthefuture"
        )

        if len(combined_text) > MAX_POST_LENGTH:
            logger.warning(
                "🚨 Alert: The combined text for '%s' exceeds %s characters!",
                name, MAX_POST_LENGTH
            )
            logger.info("Combined length: %s characters.", len(combined_text))
            logger.info(combined_text)
            logger.info(
                "Length of description: %s",
                len(entry.get('description', ''))
            )
            sys.exit(1)  # Exit with error code to indicate failure


def main() -> None:
    """
    Load the JSON file and validate content length for each entry.
    """
    filename = sys.argv[1] if len(sys.argv) > 1 else "events.json"
    data = load_json(filename)

    if data is None:
        sys.exit(1)

    check_entries(data)
    logger.info("All good! 🎉")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
