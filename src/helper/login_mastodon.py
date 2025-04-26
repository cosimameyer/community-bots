from mastodon import Mastodon

def login_mastodon(config_dict):
    client_id, client_secret = Mastodon.create_app(
                    config_dict["client_name"],
                    api_base_url=config_dict["api_base_url"])

    client = Mastodon(
        client_id=client_id,
        access_token=config_dict["access_token"],
        client_secret=client_secret,
        api_base_url=config_dict["api_base_url"],
    )
    print(f" > Logging in as {config_dict['username']} with password <TRUNCATED>")

    client.log_in(
        config_dict["username"],
        config_dict["password"],
    )
    account = client.me()
    
    print(" > Successfully logged in")

    return account, client
