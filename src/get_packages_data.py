"""Module to get package metadata from awesome-*-creations repos."""
import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

REQUEST_TIMEOUT = 10  # seconds


def _extract_contributor(person: dict) -> dict:
    """Normalise a single author/maintainer entry into a contributor dict.

    directory_id is preserved when present — it marks an R-Ladies community
    member and is used downstream to decide whether to link the person.
    """
    social_media_list = person.get("social_media", [])
    social = social_media_list[0] if social_media_list else {}
    contributor = {
        "name": person.get("name", ""),
        "mastodon": social.get("mastodon", ""),
        "bluesky": social.get("bluesky", ""),
    }
    if person.get("directory_id"):
        contributor["directory_id"] = person["directory_id"]
    return contributor


class PackagesData:
    """
    Handle gathering package metadata from awesome-*-creations repos.
    """

    def __init__(self, config_dict=None, no_dry_run=True):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.config_dict = config_dict or {}
        self.no_dry_run = no_dry_run

        if self.config_dict:
            self.base_url = self.config_dict.get("base_url")
            self.github_raw_url = self.config_dict.get("github_raw_url")
            self.json_file = self.config_dict.get("json_file")
        else:
            self.base_url = os.getenv("BASE_URL")
            self.github_raw_url = os.getenv("GITHUB_RAW_URL")
            self.json_file = os.getenv("JSON_FILE")

    def get_packages_data(self):
        """
        Retrieve and save package metadata.
        """
        contents_list = self.get_json_data()
        meta_data = self.get_meta_data(contents_list)

        if self.no_dry_run:
            with open(self.json_file, "w", encoding="utf-8") as fp:
                json.dump(meta_data, fp, ensure_ascii=False, indent=2)

            self.logger.info(
                "Package meta data successfully saved to %s",
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

        Returns:
            list[str]: A list of JSON file URLs.
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

        Returns:
            list[dict]: A list of parsed JSON objects.
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
        Extract metadata from a single package JSON.

        Handles both source formats:
        - PyLadies: maintainers[] + pypi_url + docs_url; social nested under
          maintainers[].social_media[].
        - RLadies: authors[] + pkdown_url + bug_reports_url; no social in
          package JSON. Authors with a directory_id are R-Ladies members.

        PyLadies docs_url is mapped to pkdown_url (semantically equivalent).

        Returns:
            dict: Normalised metadata dictionary with a contributors list.
                  R-Ladies community members carry a directory_id field;
                  other contributors and all PyLadies maintainers do not.
        """
        maintainers = content.get("maintainers", [])
        authors = content.get("authors", [])

        contributors = [
            _extract_contributor(p)
            for p in (maintainers or authors)
        ]

        return {
            "name": content.get("name", ""),
            "title": content.get("title", ""),
            "description": content.get("description", ""),
            "repo_url": content.get("repo_url", ""),
            "pypi_url": content.get("pypi_url", ""),
            "pkdown_url": content.get("pkdown_url") or content.get("docs_url") or "",
            "bug_reports_url": content.get("bug_reports_url", ""),
            "logo_url": content.get("logo_url", ""),
            "last_updated": content.get("last_updated", ""),
            "contributors": contributors,
        }

    def get_meta_data(self, contents_list: list[dict]) -> list[dict]:
        """
        Aggregate metadata from all package JSON files.

        Returns:
            list[dict]: A list of metadata dictionaries.
        """
        meta_data = []
        for content in contents_list:
            meta_data.append(self.extract_info(content))
        return meta_data


if __name__ == "__main__":
    packages_data_handler = PackagesData(config_dict=None, no_dry_run=True)
    packages_data_handler.get_packages_data()
