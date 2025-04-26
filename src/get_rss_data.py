from bs4 import BeautifulSoup
import requests
import json
import re
import os
import json
import requests
import pickle

def extract_elements(string, suffix):
    pattern = r'"((?!blog)[^"]*{})"'.format(suffix)
    matches = re.findall(pattern, string)
    return matches

# Get data from GitHub
def get_json_file_names(BASE_URL, GITHUB_RAW_URL):
    result = requests.get(BASE_URL)
    result.raise_for_status()  # Raise an exception for 4XX or 5XX status codes

    soup = BeautifulSoup(result.content, 'html.parser')
    res = soup.find('react-app').find('script')#, href=True)
    
    payload = json.loads(res.contents[0])
    
    #json_files = extract_elements(soup.text, ".json")
    #json_files = soup.find_all(title=re.compile("\.json$"))
    #json_files = [link['href'] for link in json_links if link['href'].endswith('.json')]

    filename = []
    for blog in payload['payload']['tree']['items']:
        file = blog['path'].split("/")[-1]
        filename.append(f"{GITHUB_RAW_URL}/{file}")
            
    return filename

def get_json_data(BASE_URL, GITHUB_RAW_URL):
    json_files = get_json_file_names(BASE_URL, GITHUB_RAW_URL)
    if json_files == []:
         exit()
    else:
        contents_list = []

        for json_file in json_files:
            try:
                response = requests.get(json_file).text
                json_response = json.loads(response)
                contents_list.append(json_response)
            except:
                print(f"{json_file} could not be accessed")
        return contents_list
    
def extract_info(content):

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

    return {"name": name, "rss_feed": rss_feed, "mastodon": mastodon, "bluesky": bluesky}
    
def get_meta_data(contents_list):
    meta_data = [] 
    for content in contents_list:
        content_data = extract_info(content)
        if content_data != None:
            
            meta_data.append(content_data)
    return meta_data

def get_rss_data(config_dict=None, NO_DRY_RUN=True):
    if NO_DRY_RUN:
        BASE_URL = os.getenv("BASE_URL") 
        GITHUB_RAW_URL = os.getenv("GITHUB_RAW_URL")
        PICKLE_FILE = os.getenv("PICKLE_FILE")
    else:
        BASE_URL = config_dict["api_base_url"]
        GITHUB_RAW_URL = config_dict["github_raw_url"]
        PICKLE_FILE = config_dict["pickle_file"]
        
    contents_list = get_json_data(BASE_URL, GITHUB_RAW_URL)
    meta_data = get_meta_data(contents_list)

    if NO_DRY_RUN:
        with open(PICKLE_FILE, 'wb') as fp:
            pickle.dump(meta_data, fp)
        
        print(f'Meta data were saved successfully to file {PICKLE_FILE}')
    
    
if __name__ == "__main__":
    get_rss_data(config_dict=None, NO_DRY_RUN=True)

