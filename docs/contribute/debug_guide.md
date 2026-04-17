# Debugging locally with `debug.py`

`debug.py` lets you run any bot module locally and see what it would do — without posting anything.

## Prerequisites

- Python 3.12
- Dependencies installed: `pdm install`
- A `.env` file in the project root

## `.env` setup

Add the credentials for the platform and bot you want to test:

```bash
# Bluesky — R-Ladies
RLADIES_BSKY_USERNAME=your-handle.bsky.social
RLADIES_BSKY_PASSWORD=your-app-password

# Bluesky — PyLadies
PYLADIES_BSKY_USERNAME=your-handle.bsky.social
PYLADIES_BSKY_PASSWORD=your-app-password

# Mastodon
PLATFORM=mastodon
USERNAME=your-username
PASSWORD=your-password
CLIENT_NAME=your-client-name
ACCESS_TOKEN=your-access-token
BOT_CLIENTCRED_SECRET=path/to/clientcred.secret

# Required for blog promotion (AI summaries)
GEMINI_API_KEY=your-key
GEMINI_MODEL_NAME=gemini-2.5-flash
```

You only need the variables for the bot/platform combination you're testing.

## Configure the script

Open `src/debug.py` and set the three fields in `__init__`:

```python
self.bot = 'rladies'        # 'rladies' or 'pyladies'
self.platform = 'bluesky'   # 'bluesky' or 'mastodon'
self.what_to_debug = 'blog' # 'blog' | 'boost_tags' | 'boost_mentions' | 'anniversary' | 'rss'
```

`no_dry_run` is `False` by default — **leave it as-is** to inspect behavior without posting anything.

## Run

```bash
cd src
python debug.py
```

Log output at `INFO` level will show what the bot would do. Set `no_dry_run = True` only when you're ready to post for real.

### Preferred: run with PDM

```bash
pdm run python src/debug.py
```

PDM resolves the virtualenv and dependencies automatically — no need to `cd src` or activate an environment manually.

### Alternative: VS Code debugger with PDM

Add a launch configuration to `.vscode/launch.json`:

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Debug bot (PDM)",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/src/debug.py",
            "python": "${workspaceFolder}/.venv/bin/python",
            "cwd": "${workspaceFolder}/src",
            "envFile": "${workspaceFolder}/.env"
        }
    ]
}
```

This lets you set breakpoints in any bot module and step through execution in the VS Code debugger. The `cwd` is set to `src/` so relative imports resolve correctly, and `.env` is loaded automatically.
