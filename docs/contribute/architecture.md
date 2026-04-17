# Architecture

This page describes how the community bots are structured and how data flows through the system.

## Overview

The project contains four automation bots that run on Bluesky (and historically Mastodon). Each bot is a standalone Python class triggered by a scheduled GitHub Actions workflow.

```
GitHub Actions (cron)
        │
        ▼
  Bot class (src/)
        │
  ┌─────┴─────┐
  ▼           ▼
Mastodon    Bluesky
(atproto)  (Mastodon.py)
```

## Bots

### Promote Anniversaries (`promote_anniversaries.py`)

Posts a celebration message on the anniversary date of women in tech profiles.

**Flow:**

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

**Flow:**

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

**Flow:**

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

**Flow:**

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

**Flow:**

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

## Directory Structure

```
.
├── src/
│   ├── config.py                   # Shared constants (tags, API URLs, ignored servers)
│   ├── promote_anniversaries.py    # Anniversary bot
│   ├── promote_blog_post.py        # Blog-post promotion bot
│   ├── boost_tags.py               # Hashtag boost bot
│   ├── boost_mentions.py           # Mention boost bot
│   ├── get_rss_data.py             # RSS metadata collector
│   ├── debug.py                    # Dry-run / testing helper
│   └── helper/
│       ├── login_mastodon.py       # Mastodon authentication
│       ├── login_bluesky.py        # Bluesky authentication
│       └── check_length_anniversary.py  # Character-limit validation
├── metadata/
│   ├── events.json                 # Women-in-tech profiles (anniversary bot)
│   ├── pyladies_meta_data.json     # PyLadies members + RSS feeds
│   ├── rladies_meta_data.json      # R-Ladies members + RSS feeds
│   └── *_counter_*.txt             # Rotation state for blog-post bot
├── archive/                        # Audit copies of posted content
├── docs/                           # MkDocs documentation source
├── .github/workflows/              # Scheduled GitHub Actions (one per bot × community)
├── pyproject.toml                  # Dependencies (pdm)
└── mkdocs.yml                      # Documentation site config
```

## Scheduling

All bots are triggered by GitHub Actions cron schedules:

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

## Configuration & Authentication

Environment variables (stored as GitHub Secrets) drive all credentials and paths:

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

| Library | Purpose |
|---|---|
| `atproto` | Bluesky / AT Protocol client |
| `Mastodon.py` | Mastodon API client |
| `feedparser` | RSS feed parsing |
| `beautifulsoup4` | HTML scraping |
| `google-generativeai` | Gemini API for post summaries |
| `requests` | HTTP downloads (images, feeds) |
