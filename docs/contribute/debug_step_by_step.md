# Step-by-step local testing guide

`debug.py` is the single entry point for running any bot module locally.
It lets you verify that a module connects correctly, reads the right data,
and would post the right content — without touching any live account unless
you explicitly flip the live-run flag.

This guide walks through every testable scenario, the credentials each one
needs, what you should see in the logs, and what to watch out for.

---

## How it works

`debug.py` exposes four settings at the top of `DebugBots.__init__`:

```python
self.bot          = 'pyladies'   # 'pyladies' or 'rladies'
self.what_to_debug = 'blog'      # see the scenario table below
self.platform     = 'bluesky'    # 'bluesky' or 'mastodon'
self.no_dry_run   = False        # False = safe dry run, True = actually post
```

Edit those four lines, then run:

```bash
pdm run python src/debug.py
```

**Always start with `no_dry_run = False`.** The dry-run path logs everything
the bot would do without making any API calls that write data. Only switch
to `True` when you are confident the output looks right.

---

## One-time setup

### 1. Install dependencies

```bash
pdm install
```

### 2. Create a `.env` file

Create a file named `.env` in the project root. You only need the variables
for the bot/platform combination you are testing — see each scenario below
for the exact keys required.

```bash
# --- Bluesky credentials ---
PYLADIES_BSKY_USERNAME=your-handle.bsky.social
PYLADIES_BSKY_PASSWORD=your-app-password

RLADIES_BSKY_USERNAME=your-handle.bsky.social
RLADIES_BSKY_PASSWORD=your-app-password

# --- Mastodon credentials ---
PYLADIES_MASTODON_USERNAME=your-username
PYLADIES_MASTODON_PASSWORD=your-password
PYLADIES_MASTODON_ACCESS_TOKEN=your-access-token
PYLADIES_BOT_CLIENTCRED_SECRET=path/to/pyladies.secret

RLADIES_MASTODON_USERNAME=your-username
RLADIES_MASTODON_PASSWORD=your-password
RLADIES_MASTODON_ACCESS_TOKEN=your-access-token
RLADIES_BOT_CLIENTCRED_SECRET=path/to/rladies.secret

# --- AI summaries (blog scenario only) ---
GEMINI_API_KEY=your-gemini-key
```

---

## Scenario reference

| `what_to_debug` | What it exercises | Needs credentials? | Platform matters? |
|---|---|---|---|
| `blog` | Fetch RSS → check archive → (post) blog entry | Yes | Yes |
| `rss` | Fetch blog list from GitHub → update local JSON | No | No |
| `boost_tags` | Search posts by hashtag → (boost) matching posts | Yes | Yes |
| `boost_mentions` | Fetch mentions → (boost/repost) them | Yes | Yes |
| `anniversary` | Read `events.json` → (post) today's anniversary | Yes | Yes |

---

## Scenario 1 — `blog`: promote a blog post

**Goal:** Verify that the bot can read the RSS feed for a given bot, find
posts that are not yet in the archive, build a correctly formatted post
text, and (in live mode) publish it to the platform.

### When to use this

- After changing `promote_blog_post.py` or the post-building logic
- When testing a new bot/platform combination for the first time
- When the archive or counter file is suspected to be out of sync

### Required env vars

| Combination | Vars needed |
|---|---|
| pyladies + bluesky | `PYLADIES_BSKY_USERNAME`, `PYLADIES_BSKY_PASSWORD`, `GEMINI_API_KEY` |
| pyladies + mastodon | `PYLADIES_MASTODON_USERNAME`, `PYLADIES_MASTODON_PASSWORD`, `PYLADIES_MASTODON_ACCESS_TOKEN`, `PYLADIES_BOT_CLIENTCRED_SECRET`, `GEMINI_API_KEY` |
| rladies + bluesky | `RLADIES_BSKY_USERNAME`, `RLADIES_BSKY_PASSWORD`, `GEMINI_API_KEY` |
| rladies + mastodon | `RLADIES_MASTODON_USERNAME`, `RLADIES_MASTODON_PASSWORD`, `RLADIES_MASTODON_ACCESS_TOKEN`, `RLADIES_BOT_CLIENTCRED_SECRET`, `GEMINI_API_KEY` |

### Steps

1. Set the knobs in `debug.py`:

    ```python
    self.bot           = 'pyladies'   # or 'rladies'
    self.what_to_debug = 'blog'
    self.platform      = 'bluesky'    # or 'mastodon'
    self.no_dry_run    = False
    ```

2. Run:

    ```bash
    pdm run python src/debug.py
    ```

3. Read the log output. A dry run shows lines like:

    ```
    INFO  Initializing pyladies_bot Bot
    INFO  > Connecting to bluesky
    INFO  [DRY RUN] Would post: 'How I built my first R package' from https://...
    ```

4. If the output looks correct, switch to live mode and run again:

    ```python
    self.no_dry_run = True
    ```

### What to watch for

- **`[DRY RUN] Would post`** — confirms a new entry was found in the feed and is not yet in the archive. Good.
- **`Archive is up to date with the feed`** — every entry in the RSS feed is already in the archive. If you just reset the archive file, this means the feed has not changed.
- **`No config for bot=… platform=…`** — your `bot`/`platform` combination is not supported. Check the values.
- **`ModuleNotFoundError`** — you are running from the wrong directory. Use `pdm run python src/debug.py` from the project root, not from inside `src/`.

### Files read/written

| File | Purpose |
|---|---|
| `metadata/pyladies_meta_data.json` (or `rladies`) | Blog feed index — lists all known feeds |
| `metadata/pyladies_counter_bluesky.txt` (or variant) | Counter tracking which feed was last processed |
| `pyladies_archive_directory_bluesky/file.json` (or variant) | Archive of already-posted links |

The archive is only written to disk if `no_dry_run = True` and a post is
sent successfully.

---

## Scenario 2 — `rss`: update the blog feed index

**Goal:** Verify that the bot can reach the GitHub repository that lists
community blogs, parse the blog entries, and write an updated JSON metadata
file locally.

### When to use this

- After a new blog is added to the awesome-pyladies-blogs or
  awesome-rladies-blogs repository
- When the metadata JSON file is suspected to be stale or missing

### Required env vars

None — this scenario reads from public GitHub URLs only.

### Steps

1. Set the knobs:

    ```python
    self.bot           = 'pyladies'   # or 'rladies'
    self.what_to_debug = 'rss'
    self.platform      = 'bluesky'    # value is ignored for this scenario
    self.no_dry_run    = False
    ```

2. Run:

    ```bash
    pdm run python src/debug.py
    ```

3. Inspect `metadata/pyladies_meta_data.json` (or `rladies`) to confirm it
   was updated with the latest blogs.

### What to watch for

- The log should show each blog entry being fetched.
- A network error here means the public GitHub URL is unreachable. Check
  your internet connection or whether the repository has moved.
- `no_dry_run` has no meaningful effect here — the metadata JSON is always
  written when the fetch succeeds, regardless of the flag. This is
  intentional: the RSS fetch is always a read-only operation from the
  platform's perspective.

---

## Scenario 3 — `boost_tags`: boost posts by hashtag

**Goal:** Verify that the bot can search the platform for posts tagged with
the community hashtag (`#pyladies` or `#rladies`), identify ones it has
not yet boosted, and (in live mode) boost or repost them.

### When to use this

- After changing `boost_tags.py`
- When investigating why the tag-boost job did or did not run

### Required env vars

| Combination | Vars needed |
|---|---|
| pyladies + bluesky | `PYLADIES_BSKY_USERNAME`, `PYLADIES_BSKY_PASSWORD` |
| pyladies + mastodon | `PYLADIES_MASTODON_USERNAME`, `PYLADIES_MASTODON_PASSWORD`, `PYLADIES_MASTODON_ACCESS_TOKEN`, `PYLADIES_BOT_CLIENTCRED_SECRET` |
| rladies + bluesky | `RLADIES_BSKY_USERNAME`, `RLADIES_BSKY_PASSWORD` |
| rladies + mastodon | `RLADIES_MASTODON_USERNAME`, `RLADIES_MASTODON_PASSWORD`, `RLADIES_MASTODON_ACCESS_TOKEN`, `RLADIES_BOT_CLIENTCRED_SECRET` |

### Steps

1. Set the knobs:

    ```python
    self.bot           = 'rladies'      # or 'pyladies'
    self.what_to_debug = 'boost_tags'
    self.platform      = 'mastodon'     # or 'bluesky'
    self.no_dry_run    = False
    ```

2. Run:

    ```bash
    pdm run python src/debug.py
    ```

3. The log shows posts found under the hashtag and whether each one would
   be boosted or skipped (already boosted).

4. If the output looks right, set `no_dry_run = True` and run again.

### What to watch for

- **`[DRY RUN] Would boost`** — a new post was found and would be boosted. Good.
- **No boost lines at all** — no recent posts under that hashtag, or all
  recent ones have already been boosted. This is normal.
- A login error here almost always means the credentials in `.env` are wrong
  or the account's app password has been revoked.

---

## Scenario 4 — `boost_mentions`: boost posts that mention the bot

**Goal:** Verify that the bot can fetch its notification feed, identify posts
that mentioned it and have not yet been boosted, and (in live mode) boost or
repost them.

### When to use this

- After changing `boost_mentions.py`
- When investigating why a mention was not boosted

### Required env vars

Same as `boost_tags` — see the table in Scenario 3.

### Steps

1. Set the knobs:

    ```python
    self.bot           = 'rladies'         # or 'pyladies'
    self.what_to_debug = 'boost_mentions'
    self.platform      = 'bluesky'         # or 'mastodon'
    self.no_dry_run    = False
    ```

2. Run:

    ```bash
    pdm run python src/debug.py
    ```

3. The log shows each notification and whether it would be boosted or
   skipped (already reblogged, or from the bot's own account).

4. If the output looks right, set `no_dry_run = True` and run again.

### What to watch for

- **`[DRY RUN] Would boost toot by …`** (Mastodon) or **`[DRY RUN] Would repost URI …`** (Bluesky) — a new mention was found and would be acted on.
- **`Successfully processed notifications. Last seen at: …`** — the Bluesky
  notification cursor was updated (only happens in live mode).
- A mention is skipped silently if it was already reblogged by the bot, or
  if it came from the bot account itself — both are correct behaviour.

---

## Scenario 5 — `anniversary`: post a community anniversary

**Goal:** Verify that the bot reads `metadata/events.json`, finds any event
whose `date` field matches today's date (`MM-DD` format), builds a correctly
formatted post, and (in live mode) sends it with the correct image.

### When to use this

- After changing `promote_anniversaries.py`
- After adding or editing an entry in `metadata/events.json`
- When you want to test the image-upload path

### Required env vars

| Combination | Vars needed |
|---|---|
| pyladies + bluesky | `PYLADIES_BSKY_USERNAME`, `PYLADIES_BSKY_PASSWORD` |
| pyladies + mastodon | `PYLADIES_MASTODON_USERNAME`, `PYLADIES_MASTODON_PASSWORD`, `PYLADIES_MASTODON_ACCESS_TOKEN`, `PYLADIES_BOT_CLIENTCRED_SECRET` |
| rladies + bluesky | `RLADIES_BSKY_USERNAME`, `RLADIES_BSKY_PASSWORD` |
| rladies + mastodon | `RLADIES_MASTODON_USERNAME`, `RLADIES_MASTODON_PASSWORD`, `RLADIES_MASTODON_ACCESS_TOKEN`, `RLADIES_BOT_CLIENTCRED_SECRET` |

### Steps

1. **Prepare a test event.** Open `metadata/events.json` and confirm that at
   least one entry has today's date in `MM-DD` format:

    ```json
    {
      "name": "Ada Lovelace",
      "date": "12-10",
      "description_mastodon": "...",
      "description_bluesky": "...",
      "wiki_link": "https://en.wikipedia.org/wiki/Ada_Lovelace",
      "bluesky": "@ada.bsky.social",
      "img": "ada_lovelace.png",
      "alt": "Portrait of Ada Lovelace"
    }
    ```

    If no entry matches today, temporarily add one with today's date. Do not
    commit that change — it's only for local testing.

2. Set the knobs:

    ```python
    self.bot           = 'pyladies'      # or 'rladies'
    self.what_to_debug = 'anniversary'
    self.platform      = 'bluesky'       # or 'mastodon'
    self.no_dry_run    = False
    ```

3. Run:

    ```bash
    pdm run python src/debug.py
    ```

4. The log shows:

    ```
    INFO  [DRY RUN] Would post anniversary for Ada Lovelace on 12-10
    ```

5. If the output looks right, set `no_dry_run = True` and run again. The bot
   will download the image (if an `img` key is present), upload it to the
   platform, and send the post.

### What to watch for

- **No output about an anniversary** — no entry in `events.json` matches
  today's date. Add a test entry as described in step 1.
- **Image already downloaded** — the image was cached locally on a previous
  run. Safe to ignore; it will use the local copy.
- **Media upload failed … falling back to text-only** — the image could not
  be uploaded (network issue or unsupported format). The post is still sent
  without the image, and the exception is logged. Check the `img` path and
  the platform's media limits.
- On Bluesky, the Bluesky handle in the `bluesky` field (e.g. `@ada.bsky.social`)
  is resolved to a DID via the public API. If that lookup fails, the name is
  used as plain text instead — the post still goes out.

---

## Troubleshooting

### "No config for bot=… platform=…"

Your `bot`/`platform` combination is not in the supported matrix. Valid
combinations are:

| `bot` | `platform` |
|---|---|
| `pyladies` | `bluesky` |
| `pyladies` | `mastodon` |
| `rladies` | `bluesky` |
| `rladies` | `mastodon` |

The `rss` scenario ignores `platform` entirely.

### Login errors

- **Bluesky:** the `PYLADIES_BSKY_PASSWORD` / `RLADIES_BSKY_PASSWORD` env
  vars must be an *app password* (generated in Bluesky Settings → Privacy &
  Security → App Passwords), not your main account password.
- **Mastodon:** the access token must have `read` and `write:statuses` scopes.
  Re-generate it in your Mastodon account settings if in doubt.

### ModuleNotFoundError / ImportError

Run from the project root using PDM, not from inside `src/`:

```bash
# Correct
pdm run python src/debug.py

# Wrong (relative imports break)
cd src && python debug.py
```

### Dry run shows nothing

- For `blog`: all entries in the RSS feed are already in the archive. Delete
  or empty the archive file (`archive_directory*/file.json`) to force a
  re-run.
- For `boost_tags` / `boost_mentions`: there are no recent posts matching
  the criteria. Post something yourself on the relevant platform under the
  hashtag and try again.
- For `anniversary`: no entry in `events.json` matches today's date. Add a
  temporary test entry (see Scenario 5, step 1).
