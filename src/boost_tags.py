import time
import os
import config
from urllib.parse import urlparse
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky


def repost_tags_mastodon(client, config_dict):
    for tag in config_dict["tags"]:
        tag = tag.lower().strip("# ")
        print(f" > Reading timeline for new toots tagged #{tag}")

        try:
            statuses = client.timeline_hashtag(
                tag,
                limit=config_dict["timeline_depth_limit"]
            )
        except Exception as e:
            print(
                f" ! Network error while attempting to fetch statuses: {e}."
                "Trying again..."
            )
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
                print(
                    f'   * Boosting new toot by {status.account.username} ',
                    f'using tag #{tag} viewable at: {status.url}'
                )
                client.status_reblog(status.id)
                client.status_favourite(status.id)


def boost_tags(config_dict=None, NO_DRY_RUN=False):
    if (config_dict is None) and (NO_DRY_RUN):
        config_dict = {
            "platform": os.getenv("PLATFORM"),
            "password": os.getenv("PASSWORD"),
            "username": os.getenv("USERNAME"),
            "client_name": os.getenv("CLIENT_NAME"),
            "tags": os.getenv("TAGS_TO_BOOST")
        }
        if config_dict["platform"] == "mastodon":
            config_dict["mastodon_visiblity"] = config.MASTODON_VISIBILITY
            config_dict["api_base_url"] = config.API_BASE_URL
            config_dict["access_token"] = os.getenv("ACCESS_TOKEN")
            config_dict["client_cred_file"] = os.getenv('BOT_CLIENTCRED_SECRET')
            config_dict["timeline_depth_limit"] = 40
        else:
            config_dict["api_base_url"] = "bluesky"

    print("")
    client_name = config_dict['client_name']
    print(f"Initializing {client_name} Bot")
    print("=================" + "="*len(client_name))
    print(f" > Connecting to {config_dict['api_base_url']}")

    if config_dict["platform"] == "mastodon":
        ## Commented because it wasn't fully working

        #account, client = login_mastodon(config_dict)
        #print(f" > Fetched account data for {account.acct}")

        # repost_tags_mastodon(client, config_dict)
        print("This feature currently doesn't work for Mastodon. It's deployed using AWS.")
    elif config_dict["platform"] == "bluesky":
        client = login_bluesky(config_dict)
        print(" > Fetched account data")

        print(" > Beginning search-loop and repost posts")
        print("------------------------")

        timeline = client.get_timeline(algorithm='reverse-chronological')
        cids = [post.post.cid for post in timeline.feed]
        for tag in [config_dict['tags']]:
            r = client.app.bsky.feed.search_posts(
                params=dict(
                    q=tag,
                    tag=[tag],
                    sort="top",
                    limit=50
                    )
                )
            for post in r.posts:
                text = post.record.text
                tags_list = [tag.strip("#").lower() for tag in text.split() if tag.startswith("#")]
                print("---------------------")
                print(f"Repost post by {post.author.handle}")
                print(post.record.text)
                print(f"Tag list: {tags_list}")
                if tag in tags_list and post.cid not in cids:
                    try:
                        print(
                            '   * Reposted post reference:',
                            client.repost(uri=post.uri,
                                          cid=post.cid)
                        )
                    except Exception as e:
                        print(
                            f"   * Reposting new post with URI {post.uri} "
                            f"and CID {post.cid} did not work because of {e}"
                            f"- going to the next post.")
                    time.sleep(0.1)
        print('Successfully process notification.')


if __name__ == "__main__":
    boost_tags(config_dict=None, NO_DRY_RUN=True)
