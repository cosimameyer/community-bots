import time
import os
from urllib.parse import urlparse
from mastodon import Mastodon
from dotenv import load_dotenv

load_dotenv()

try:
    import config
except ModuleNotFoundError:
    print("ERROR: You must rename `config_example.py` to `config.py` and edit it with your account credentials.")
    import sys; sys.exit()

# Constants
TIME_TO_SLEEP = 1800  # 1800 seconds = 30 minutes
TIMELINE_DEPTH_LIMIT = 40  # How many of the latest statuses to pull per tag. 
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PASSWORD = os.getenv("PASSWORD")
USERNAME = config.USERNAME
CLIENT_CRED_FILE = '{}_clientcred.secret'.format(config.CLIENT_NAME.lower())

def setup_client_cred_file():
    try:
        with open(CLIENT_CRED_FILE) as f:
            print(' > Found pre-existing secrets file')

    except IOError:
        # If the CLIENT_CRED_FILE doesn't exist, connect to Mastodon, get secrets, and create the cred file.
        print(' > No secrets file found. Auto-generating a new one')
        try:
            Mastodon.create_app(
            config.CLIENT_NAME,
            api_base_url = config.API_BASE_URL,
            to_file = CLIENT_CRED_FILE)
        except:
            print(' > Error connecting to Mastodon. Client secrets could not be generated')
            raise
        

print("")
print("Initializing {} Bot".format(config.CLIENT_NAME))
print("=================" + "="*len(config.CLIENT_NAME))
print(" > Connecting to {}".format(config.API_BASE_URL))
setup_client_cred_file()

# Create client
mastodon = Mastodon(
    client_id = CLIENT_CRED_FILE,
    api_base_url = config.API_BASE_URL,
)   

print(" > Logging in as {} with password <TRUNCATED>".format(USERNAME))

# Then login. This can be done every time, or use persisted with to_file.
mastodon.log_in(
    USERNAME,
    PASSWORD,
    # to_file = 'hashtaggamedev_usercred.secret'
)

print(" > Successfully logged in")
print(" > Fetching account data")

def lambda_handler(event, context):

    account = mastodon.me()

    print(f" > Fetched account data for {account.acct}")

    print(" > Beginning search-loop and toot and boost toots")
    print("------------------------")

    for tag in config.TAGS:
        tag = tag.lower().strip("# ")
        print(f" > Reading timeline for new toots tagged #{tag}")

        try:
            statuses = mastodon.timeline_hashtag(tag, limit=TIMELINE_DEPTH_LIMIT)
        except:
            print(" ! Network error while attempting to fetch statuses. Trying again...")
            time.sleep(30)
            continue

        # Sleep momentarily so we don't get rate limited.
        time.sleep(0.1)
        
        print(" > Reading statuses to identify tootable statuses")
        for status in statuses:
            domain = urlparse(status.url).netloc
            if not status.favourited and \
                    status.account.acct != account.acct and \
                    domain not in config.IGNORE_SERVERS:
                # Boost and favorite the new status
                print(f"   * Boosting new toot by {status.account.username} using tag #{tag} viewable at: {status.url}")
                mastodon.status_reblog(status.id)
                mastodon.status_favourite(status.id)
