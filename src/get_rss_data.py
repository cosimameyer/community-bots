"""Module to get RSS metadata from JSON files."""
import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

REQUEST_TIMEOUT = 10  # seconds


class RSSData:
    """
    Handle gathering RSS data from JSON files.
    """

    def __init__(self, config_dict=None, no_dry_run=True):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.config_dict = config_dict or {}
        self.no_dry_run = no_dry_run

        if self.no_dry_run:
            self.base_url = os.getenv("BASE_URL")
            self.github_raw_url = os.getenv("GITHUB_RAW_URL")
            self.json_file = os.getenv("JSON_FILE")
        else:
            self.base_url = self.config_dict.get("api_base_url")
            self.github_raw_url = self.config_dict.get("github_raw_url")
            self.json_file = self.config_dict.get("json_file")

    def get_rss_data(self):
        """
        Retrieve and save RSS metadata.
        """
        contents_list = self.get_json_data()
        meta_data = self.get_meta_data(contents_list)

        if self.no_dry_run:
            with open(self.json_file, "w", encoding="utf-8") as fp:
                json.dump(meta_data, fp, ensure_ascii=False, indent=2)

            self.logger.info(
                "Meta data successfully saved to %s",
                self.json_file
            )
        else:
            self.logger.info(
                "[DRY RUN] Would write %d entries to %s:\n%s",
                len(meta_data),
                self.json_file,
                json.dumps(meta_data, ensure_ascii=False, indent=2),
            )

    def get_json_file_names(self) -> list[str]:
        """
        Retrieve available JSON file names from the configured base URL.

        The method loads the page at `self.base_url`, extracts embedded
        JavaScript data inside the `<react-app>` element, and constructs full
        raw GitHub URLs for each JSON file.

        Returns:
            list[str]: A list of JSON file URLs.

        Raises:
            requests.HTTPError: If the request to `self.base_url` fails.
            json.JSONDecodeError: If the embedded script cannot be parsed
                                    as JSON.
            AttributeError: If the expected DOM structure is missing.
        """
        response = requests.get(self.base_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")
        script_tag = soup.find("react-app").find("script")

        payload = json.loads(script_tag.string)
        try:
            items = (
                payload["payload"]["codeViewTreeRoute"]["tree"]["items"]
            )
        except KeyError as exc:
            top_keys = list(payload.get("payload", {}).keys())
            raise RuntimeError(
                f"Unexpected GitHub payload structure — missing key {exc}. "
                f"Available keys under 'payload': {top_keys}. "
                "Update the key path in get_json_file_names()."
            ) from exc
        return [
            f"{self.github_raw_url}/{item['path'].split('/')[-1]}"
            for item in items
            if item["path"].endswith(".json")
        ]

    def get_json_data(self) -> list[dict]:
        """
        Download and parse JSON files from discovered file URLs.

        The method retrieves the list of JSON file URLs via
        `get_json_file_names()`, fetches each file, and loads it into memory.

        Returns:
            list[dict]: A list of parsed JSON objects.

        Raises:
            RuntimeError: If no JSON file URLs were found.
            requests.HTTPError: If fetching a JSON file fails with an HTTP
                                error.
            json.JSONDecodeError: If a response is not valid JSON.
        """
        json_files = self.get_json_file_names()
        if not json_files:
            raise RuntimeError("No JSON files found.")

        contents_list = []
        for json_file in json_files:
            try:
                response = requests.get(json_file, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                contents_list.append(response.json())
            except (requests.RequestException, json.JSONDecodeError) as exc:
                self.logger.warning("Could not access %s. %s", json_file, exc)

        return contents_list

    @staticmethod
    def extract_info(content: dict) -> dict:
        """
        Extract metadata information from a single JSON content item.

        The method collects:
        - `name`: The author's name (first entry in `authors`).
        - `rss_feed`: RSS feed URL (prefers `rss_feed`, falls back to
            `rss_feed_youtube`).
        - `mastodon`: Author's Mastodon handle if available.
        - `bluesky`: Author's Bluesky handle if available.

        Args:
            content (dict): Parsed JSON object representing author and
                            feed data.

        Returns:
            dict: A dictionary containing metadata fields.
        """
        rss_feed = content.get("rss_feed") or content.get("rss_feed_youtube") or ""

        author = content.get("authors", [{}])[0]
        name = author.get("name", "")

        social_media_list = author.get("social_media", [])
        social_media = social_media_list[0] if social_media_list else {}
        mastodon = social_media.get("mastodon", "")
        bluesky = social_media.get("bluesky", "")

        return {
            "name": name,
            "rss_feed": rss_feed,
            "mastodon": mastodon,
            "bluesky": bluesky,
        }

    def get_meta_data(self, contents_list: list[dict]) -> list[dict]:
        """
        Aggregate metadata from multiple JSON content items.

        Iterates through all content dictionaries, extracts metadata
        using `extract_info()`, and compiles the results into a list.

        Args:
            contents_list (list[dict]): List of parsed JSON content
                                        dictionaries.

        Returns:
            list[dict]: A list of metadata dictionaries.
        """
        meta_data = []
        for content in contents_list:
            meta_data.append(self.extract_info(content))
        return meta_data


if __name__ == "__main__":
    rss_data_handler = RSSData(config_dict=None, no_dry_run=True)
    rss_data_handler.get_rss_data()
