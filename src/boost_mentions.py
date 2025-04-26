import os
import config
from helper.login_mastodon import login_mastodon
from helper.login_bluesky import login_bluesky

if __name__ == "__main__":
    config_dict = {
        "platform": os.getenv("PLATFORM"),
        "password": os.getenv("PASSWORD"),
        "username": os.getenv("USERNAME"),
        "client_name": os.getenv("CLIENT_NAME")
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
    client_name = config_dict.get("client_name")
    print(f"Initializing {client_name} Bot")
    print("=================" + "=" * len(client_name or ""))
    print(f" > Connecting to {config_dict['api_base_url']}")

    if config_dict["platform"] == "mastodon":
        account, client = login_mastodon(config_dict)
        notifications = client.notifications(types=['mention'])
        print(f" > Fetched account data for {account.acct}")

        print(" > Beginning search-loop and toot and boost toots")
        print("------------------------")

        print(" > Reading statuses to identify tootable statuses")
        for notification in notifications:
            if not notification.status.favourited and \
                    notification.status.account.acct != account.acct:
                # Boost and favorite the new status
                try:
                    print(
                        f"   * Boosting new toot by "
                        f"{notification.account.username} "
                        f"viewable at: {notification.status.url}"
                    )
                    client.status_reblog(notification.status.id)
                    client.status_favourite(notification.status.id)
                except Exception as e:
                    print(
                        f"   * Boosting new toot by "
                        f" {notification.account.username} did not work "
                        f"because {e}- going to the next toot."
                    )
    elif config_dict["platform"] == "bluesky":
        client = login_bluesky(config_dict)
        print(" > Fetched account data")

        print(" > Beginning search-loop and repost posts")
        print("------------------------")

        print(" > Reading statuses to identify postable statuses")
        last_seen_at = client.get_current_time_iso()
        response = client.app.bsky.notification.list_notifications()
        timeline = client.get_timeline(algorithm='reverse-chronological')
        cids = [post.post.cid for post in timeline.feed]

        for notification in response.notifications:
            if (
                notification.reason == "mention"
                and notification.cid not in cids
            ):
                try:
                    print(
                        '   * Reposted post reference:',
                        client.repost(uri=notification.uri,
                        cid=notification.cid)
                    )
                except Exception as e:
                    print(
                        f"   * Reposting new post with URI {notification.uri}"
                        f" and CID {notification.cid} did not work because "
                        f"of {e} - going to the next post."
                    )

        client.app.bsky.notification.update_seen({'seen_at': last_seen_at})
        print('Successfully process notification. Last seen at:', last_seen_at)
