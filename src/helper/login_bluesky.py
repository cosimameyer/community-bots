from atproto import Client

def login_bluesky(config_dict):
    print(f" > Logging in as {config_dict['username']} with password <TRUNCATED>")
    client = Client()
    client.login(config_dict["username"], config_dict["password"])
    print(" > Successfully logged in")

    return client
