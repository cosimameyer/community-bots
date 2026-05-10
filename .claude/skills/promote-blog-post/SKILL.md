---
name: promote-blog-post
description: Deep knowledge of src/promote_blog_post.py — architecture, invariants, pitfalls, and debugging. Use when reviewing, modifying, or debugging the blog-post promotion flow.
---

# promote_blog_post.py — Reference Knowledge

## Call chain

```
promote_blog_post()
  └─ get_config()                  # sets self.config_dict + genai.configure()
  └─ process_feeds()               # production path (no_dry_run=True)
       └─ process_feed()           # per-feed wrapper, loads archive
            └─ _process_feed()     # inner loop, sends posts
  └─ [dry-run loop]                # no_dry_run=False: direct loop over feeds
```

## Posting limits

- **Max 2 posts per run** (`count_post < 2` guard in `process_feeds` and dry-run loop).
- **Max 1 post per feed** (`count >= 1: break` in `_process_feed`).
- `count_post` is threaded through all three levels and compared before/after `_process_feed` to distinguish "posted something" from "all already archived".

## Counter file

The counter file (`metadata/*_counter*.txt`) stores the **name of the last feed processed**. On the next run, `process_feeds` skips every feed until it reaches that name, then continues from there. When the last feed in the list is reached with `count_post == 0`, it wraps around: processes the last feed, then `feeds[0]`, then rolls the counter to `feeds[1]['name']` (or `feeds[0]` if only one feed exists — guard: `feeds[1] if len(feeds) > 1 else feeds[0]`).

## Archive file

Location: `archive/<archive_dir>/<domain>/file.json` (YouTube/Medium add an extra slug subdirectory).

Format: `{"link": ["https://...", ...]}`.

**Critical**: must be opened with `'w', encoding='utf-8'` — never `'wb'`. Opening in binary mode causes `json.dump` to raise `TypeError`, the archive never saves, `count_post` never increments, and the 2-post limit is bypassed → spam.

Archive append happens **only in production** (`if self.no_dry_run:`). In dry-run mode, links are never added to the archive so repeat runs show the same candidates.

Archive is saved only after a **successful** post (`result == 'success'`), wrapped in `try/except OSError`.

## genai.configure()

Must be called **regardless of config source**. The `get_config()` method calls it in two places:
1. Inside the `if (self.config_dict is None) and self.no_dry_run:` block (GitHub Actions path).
2. After the else-branch: `if self.config_dict.get('gen_ai_support'): genai.configure(...)` — this covers the debug/passed-config path.

If `genai.configure()` is only in the first block, Gemini summarization silently fails when `config_dict` is passed directly (e.g., from `debug.py`).

## build_post_mastodon

`basis_text` is a plain `str`. Append with `+=`, not `.text()` (which is a `TextBuilder` method and does not exist on str).

```python
if summarized_blog_post:
    basis_text += '\n\n '
    basis_text += summarized_blog_post
```

## Dry-run mode

`no_dry_run=False`:
- Client is `None` — no platform connection made.
- Dry-run loop in `promote_blog_post()` iterates feeds directly, calls `process_feed()`, breaks at `count_post >= 2`.
- Inside `_process_feed`, the else-branch logs `[DRY RUN] Would post: '<title>'` and increments `count` and `count_post` directly (no `send_post` call).
- Archive is **not** modified.

## count_fails

If a post fails, `count_fails` increments and the inner loop breaks with a warning:

```python
if count_fails >= 1:
    self.logger.warning("Stopping feed after post failure — skipping remaining entries.")
    break
```

## process_feed log messages

Two distinct cases after `_process_feed` returns:
- `count_post > prev_count` → `'New RSS feeds are successfully loaded and processed.'`
- `count_post == prev_count` → `'Feed has new entries but all are already in the archive — nothing to post.'`
- `number_of_entries_feed <= number_of_entries_archive` → `'Archive is up to date with the feed — no new entries since last run.'`

## Config keys (Bluesky path, debug.py)

```python
{
    "archive": "pyladies_archive_directory_bluesky",
    "counter": "metadata/pyladies_counter_bluesky.txt",
    "json_file": "metadata/pyladies_meta_data.json",
    "client_name": "pyladies_bot",
    "images": "pyladies_images",
    "api_base_url": "bluesky",
    "mastodon": None,
    "gen_ai_support": True,
    "gemini_model_name": "gemini-2.5-flash",
    "password": os.getenv("PYLADIES_BSKY_PASSWORD"),
    "username": os.getenv("PYLADIES_BSKY_USERNAME"),
    "platform": "bluesky",
}
```

## Known pylint warnings (pre-existing, not regressions)

- `E0401` import errors for `atproto`, `google.generativeai`, `feedparser`, `requests`, `bs4` — not installed in lint environment.
- `R0904` too-many-public-methods (27/20) — class is large by design.
- `W0718` broad-exception-caught in send/post methods — intentional catch-all.
- `R1723` no-else-break on line ~140 — pre-existing.
