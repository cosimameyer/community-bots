# Architecture

This page describes how the community bots are structured and how data flows through the system.

## Overview

The project contains six automation bots that run on Bluesky (and historically Mastodon). Each bot is a standalone Python class triggered by a scheduled GitHub Actions workflow.

Each bot is a Python class in `src/`, triggered by a GitHub Actions cron job. The class then calls the appropriate platform API — `Mastodon.py` for Mastodon and `atproto` for Bluesky.

```
GitHub Actions (cron)
        │
        ▼
  Bot class (src/)
        │
  ┌─────┴─────┐
  ▼           ▼
Mastodon    Bluesky
(Mastodon.py) (atproto)
```

## Bots

### Promote Anniversaries (`promote_anniversaries.py`)

Posts a celebration message on the anniversary date of women in tech profiles.

**Flow:** The bot loads `events.json`, compares each entry's date against today, builds a text post with the person's image, and sends it to both platforms.

```
metadata/events.json
        │
        ▼
PromoteAnniversary.promote_anniversary()
        │
        ├─ is_matching_current_date()   ← compare MM-DD to today
        ├─ build_post()                 ← format text + hashtags
        ├─ download_image()             ← fetch from GitHub raw URL
        └─ send_post()
              ├─ send_post_to_mastodon()
              └─ send_post_to_bluesky()
```

Each entry in `events.json` holds a name, anniversary date (`MM-DD`), description, image filename, and wiki link. The bot runs daily and only posts when the date matches.

---

### Promote Blog Posts (`promote_blog_post.py`)

Rotates through community members and shares their latest blog post.

**Flow:** The bot reads a counter file to pick the next community member, fetches their RSS feed, generates a summary via Gemini, posts to the platform, then commits the updated counter back to the repository.

```
metadata/{pyladies,rladies}_meta_data.json   ← member list + RSS feeds
metadata/*_counter_*.txt                     ← tracks current position

        │
        ▼
PromoteBlogPost.promote_blog_post()
        │
        ├─ read_metadata_json()       ← load member list
        ├─ read_counter_name()        ← determine next member
        ├─ process_feeds()
        │     ├─ fetch RSS feed
        │     ├─ parse_pub_date()
        │     ├─ download_image()
        │     ├─ generate_summary()   ← Gemini API
        │     └─ send_post()
        ├─ update_counter()           ← advance position
        └─ push changes to repo       ← commit updated counter
```

The counter files (`*_counter_mastodon.txt`, `*_counter_bluesky.txt`) persist the current rotation index between runs. After each post the bot commits the updated counter back to the repository.

---

### Boost Tags (`boost_tags.py`)

Reposts any public post tagged `#pyladies` or `#rladies`.

**Flow:** The bot searches each configured hashtag, then reposts any public post it finds that hasn't already been boosted.

```
config.TAGS  ←  ['#rladies', '#pyladies']

        │
        ▼
BoostTags.boost_tags()
        │
        ├─ repost_tags_mastodon()
        │     └─ timeline_hashtag() → status_reblog()
        └─ repost_tags_bluesky()
              └─ feed.search_posts() → feed.repost()
```

`config.IGNORE_SERVERS` lists Mastodon instances whose posts should be skipped.

---

### Boost Mentions (`boost_mentions.py`)

Boosts and likes posts that mention the bot accounts.

**Flow:** The bot reads its notification feed, then boosts and likes any new mention it finds.

```
BoostMentions.boost_mentions()
        │
        ├─ [Mastodon]
        │     ├─ notifications(types=['mention'])
        │     ├─ status_reblog()
        │     └─ status_favourite()
        └─ [Bluesky]
              ├─ notification.list_notifications()
              ├─ feed.repost()
              └─ feed.like()
```

---

### RSS Data Collector (`get_rss_data.py`)

Scrapes community RSS feeds and regenerates the metadata JSON files used by the blog-post bot.

**Flow:** The bot fetches the community blog list from GitHub, parses each blog's RSS feed, and writes an updated metadata JSON file locally.

```
RSSData.get_rss_data()
        │
        ├─ get_json_data()       ← load existing metadata
        ├─ get_meta_data()       ← fetch + parse RSS feeds
        │     └─ extract_elements()
        └─ write updated JSON    ← metadata/{pyladies,rladies}_meta_data.json
```

This bot runs on a daily schedule and keeps the member list fresh.

---

### Package Data Collector (`get_packages_data.py`)

Scrapes community package listings and regenerates the metadata JSON files used by the package-promotion bot.

**Flow:** The bot fetches the `data/packages/` directory listing from the awesome-\*-creations GitHub repository, downloads each package JSON, normalises the fields (handling both PyLadies and RLadies+ schema variants), and writes an updated metadata file.

```
PackagesData.get_packages_data()
        │
        ├─ get_json_file_names() ← scrape GitHub tree for .json file URLs
        ├─ get_json_data()       ← download each package JSON
        ├─ get_meta_data()
        │     └─ extract_info()  ← normalise PyLadies / RLadies+ fields
        └─ write updated JSON    ← metadata/{pyladies,rladies}_packages_meta_data.json
```

`extract_info` handles the schema difference between communities: PyLadies packages carry `maintainers`, `pypi_url`, and `social_media` (Mastodon + Bluesky handles); RLadies+ packages carry `authors`, `pkdown_url`, and `last_updated`.

This bot runs weekly (Monday for PyLadies, Tuesday for RLadies+) and keeps the package list fresh.

---

### Promote Packages (`promote_package.py`)

Cycles through community-built open-source packages and shares one per run, skipping packages that have already been promoted at their current version.

**Flow:** The bot reads the package metadata, finds the next unvisited package, checks whether it has been updated since the last promotion, builds a post, and (if live) sends it. The counter and archive are committed back to the repository.

```
metadata/{pyladies,rladies}_packages_meta_data.json   ← package list
metadata/*_packages_counter_*.txt                     ← tracks current position
metadata/{pyladies,rladies}_packages_archive.json     ← promoted versions

        │
        ▼
PromotePackage.promote_package()
        │
        ├─ read_metadata_json()       ← load package list
        ├─ read_counter_name()        ← determine starting position
        ├─ process_packages()
        │     ├─ read_archive()       ← load promoted-version history
        │     ├─ get_current_version()
        │     │     ├─ [PyLadies] get_pypi_version()   ← PyPI JSON API
        │     │     └─ [RLadies+] last_updated field   ← from metadata
        │     ├─ skip if version unchanged
        │     ├─ build_post_mastodon() / build_post_bluesky()
        │     ├─ send_post()
        │     ├─ write_archive()      ← record new version
        │     └─ update_counter()     ← advance position
        └─ push changes to repo       ← commit updated counter + archive
```

**Version tracking:**

| Community | Version source | Skip condition |
|---|---|---|
| PyLadies | Latest release from PyPI JSON API | Same version already in archive |
| RLadies+ | `last_updated` field in the package JSON | Same timestamp already in archive |
| Either | No version available (no `pypi_url`, no `last_updated`) | Already in archive at any value (promote once per cycle) |

If every package in the list is already up-to-date, nothing is posted and the counter is left unchanged.

This bot runs weekly with a 3-day offset between communities (PyLadies on days 1/8/15/22/29, RLadies+ on days 4/11/18/25).

---

## Directory Structure

The repository is organised as follows: bot source code lives in `src/`, persistent state in `metadata/`, documentation in `docs/`, and scheduled triggers in `.github/workflows/`.

```
.
├── src/
│   ├── config.py                   # Shared constants (tags, API URLs, ignored servers)
│   ├── promote_anniversaries.py    # Anniversary bot
│   ├── promote_blog_post.py        # Blog-post promotion bot
│   ├── promote_package.py          # Package promotion bot
│   ├── boost_tags.py               # Hashtag boost bot
│   ├── boost_mentions.py           # Mention boost bot
│   ├── get_rss_data.py             # RSS metadata collector
│   ├── get_packages_data.py        # Package metadata collector
│   ├── debug.py                    # Dry-run / testing helper
│   └── helper/
│       ├── login_mastodon.py       # Mastodon authentication
│       ├── login_bluesky.py        # Bluesky authentication
│       └── check_length_anniversary.py  # Character-limit validation
├── metadata/
│   ├── events.json                 # Women-in-tech profiles (anniversary bot)
│   ├── pyladies_meta_data.json     # PyLadies members + RSS feeds
│   ├── rladies_meta_data.json      # RLadies+ members + RSS feeds
│   ├── *_counter_*.txt             # Rotation state for blog-post and package bots
│   ├── pyladies_packages_meta_data.json   # PyLadies packages
│   ├── rladies_packages_meta_data.json    # RLadies+ packages
│   ├── pyladies_packages_archive.json     # Promoted versions (PyLadies packages)
│   └── rladies_packages_archive.json      # Promoted versions (RLadies+ packages)
├── archive/                        # Audit copies of posted content
├── docs/                           # MkDocs documentation source
├── .github/workflows/              # Scheduled GitHub Actions (one per bot × community)
├── pyproject.toml                  # Dependencies (pdm)
└── mkdocs.yml                      # Documentation site config
```

## Scheduling

All bots are triggered by GitHub Actions cron schedules. The table below shows each workflow, its schedule, and the bot module it runs.

| Workflow | Schedule | Bot |
|---|---|---|
| `pyladies_anniversaries.yml` | Daily @ 11:00 UTC | Promote Anniversaries |
| `rladies_anniversaries.yml` | Daily @ 11:00 UTC | Promote Anniversaries |
| `pyladies_promote_blog.yml` | Every 2 days @ 07:00 UTC | Promote Blog Posts |
| `rladies_promote_blog.yml` | Every 2 days @ 07:00 UTC | Promote Blog Posts |
| `pyladies_boost_tags.yml` | Every 6 hours | Boost Tags |
| `rladies_boost_tags.yml` | Every 6 hours | Boost Tags |
| `pyladies_boost_mentions.yml` | Every 30 minutes | Boost Mentions |
| `rladies_boost_mentions.yml` | Every 30 minutes | Boost Mentions |
| `pyladies_rss_feed.yml` | Daily | RSS Data Collector |
| `rladies_rss_feed.yml` | Daily | RSS Data Collector |
| `pyladies_packages_data.yml` | Weekly (Monday @ 01:00 UTC) | Package Data Collector |
| `rladies_packages_data.yml` | Weekly (Tuesday @ 01:00 UTC) | Package Data Collector |
| `pyladies_promote_package.yml` | Weekly (days 1/8/15/22/29 @ 09:00 UTC) | Promote Packages |
| `rladies_promote_package.yml` | Weekly (days 4/11/18/25 @ 09:00 UTC) | Promote Packages |

## Configuration & Authentication

Environment variables (stored as GitHub Secrets) drive all credentials and paths. The table below lists each variable and which bot module reads it.

| Variable | Used by |
|---|---|
| `PLATFORM` | All bots — `"mastodon"` or `"bluesky"` |
| `USERNAME` / `PASSWORD` | Bluesky login |
| `ACCESS_TOKEN`, `CLIENT_ID`, `CLIENT_SECRET` | Mastodon OAuth |
| `GEMINI_API_KEY` | Blog-post bot (AI summaries) |
| `JSON_FILE`, `COUNTER` | Blog-post bot (file paths) |
| `IMAGES`, `ARCHIVE_DIRECTORY` | Image and archive storage |

Bots accept a `config_dict` constructor argument as an alternative to environment variables, which is used for local testing and the debug helper (`debug.py`).

## Dry-Run Mode

Every bot respects a `no_dry_run` flag. When `False` (the default for local runs), the bot executes all logic but skips the actual API calls to the social media platforms. Set `no_dry_run=True` in production or pass `--no-dry-run` via the workflow step.

## Key Dependencies

The table below lists the third-party libraries the project depends on and what each is used for.

| Library | Purpose |
|---|---|
| `atproto` | Bluesky / AT Protocol client |
| `Mastodon.py` | Mastodon API client |
| `feedparser` | RSS feed parsing |
| `beautifulsoup4` | HTML scraping |
| `google-generativeai` | Gemini API for post summaries |
| `requests` | HTTP downloads (images, feeds) |
