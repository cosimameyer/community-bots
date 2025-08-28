"""Module to get RSS metadata from JSON files."""
import re
import os
import json
import logging
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()


class RSSData():
    """
    Class to handle gathering RSS data from JSON files.
    """
    def __init__(self, config_dict=None, no_dry_run=True):
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

        self.config_dict = config_dict
        self.no_dry_run = no_dry_run

        if self.no_dry_run:
            self.base_url = os.getenv("BASE_URL")
            self.github_raw_url = os.getenv("GITHUB_RAW_URL")
            self.json_file = os.getenv("JSON_FILE")
        else:
            self.base_url = self.config_dict["api_base_url"]
            self.github_raw_url = self.config_dict["github_raw_url"]
            self.json_file = self.config_dict["json_file"]

    def get_rss_data(self):
        """
        Method to get RSS data.
        """
        contents_list = self.get_json_data()
        meta_data = self.get_meta_data(contents_list)

        if self.no_dry_run:
            with open(self.json_file, 'wb') as fp:
                json.dump(meta_data, fp)

            self.logger(
                f"""
                Meta data were saved successfully to file {self.json_file}
                """
            )

    @staticmethod
    def extract_elements(string: str, suffix):
        """
        Method to extract elements.
        """
        pattern = rf'"((?!blog)[^"]*{suffix})"'
        matches = re.findall(pattern, string)
        return matches

    def get_json_file_names(self):
        """
        Method to get JSON file names.
        """
        result = requests.get(self.base_url)
        result.raise_for_status()

        soup = BeautifulSoup(result.content, 'html.parser')
        res = soup.find('react-app').find('script')

        payload = json.loads(res.contents[0])

        filename = []
        for blog in payload['payload']['tree']['items']:
            file = blog['path'].split("/")[-1]
            filename.append(f"{self.github_raw_url}/{file}")

        return filename

    def get_json_data(self):
        """
        Method to get JSON data.
        """
        json_files = self.get_json_file_names()
        if json_files == []:
            exit()
        else:
            contents_list = []

            for json_file in json_files:
                try:
                    response = requests.get(json_file).text
                    json_response = json.loads(response)
                    contents_list.append(json_response)
                except Exception as e:
                    self.logger(f"{json_file} could not be accessed. {e}")
            return contents_list

    @staticmethod
    def extract_info(content):
        """
        Extract metadata info from JSON file.
        """

        if 'rss_feed' in content:
            rss_feed = [content['rss_feed']]
        else:
            rss_feed = [None]

        if 'rss_feed_youtube' in content:
            rss_feed_yt = [content['rss_feed_youtube']]
        else:
            rss_feed_yt = [None]

        rss_feed = [a or b for a, b in zip(rss_feed, rss_feed_yt)]
        if rss_feed == [None]:
            rss_feed = ''

        name = content['authors'][0]['name']

        if 'mastodon' in content['authors'][0]['social_media'][0].keys():
            mastodon = content['authors'][0]['social_media'][0]['mastodon']
        else:
            mastodon = ''

        if 'bluesky' in content['authors'][0]['social_media'][0].keys():
            bluesky = content['authors'][0]['social_media'][0]['bluesky']
        else:
            bluesky = ''

        return {
            "name": name,
            "rss_feed": rss_feed,
            "mastodon": mastodon,
            "bluesky": bluesky
        }

    def get_meta_data(self, contents_list):
        """
        Method to get metadata based on JSON files.
        """
        meta_data = []
        for content in contents_list:
            content_data = self.extract_info(content)
            if content_data is not None:

                meta_data.append(content_data)
        return meta_data


if __name__ == "__main__":
    rss_data_handler = RSSData(config_dict=None, no_dry_run=True)
    rss_data_handler.get_rss_data()
