---
name: x-autoposter
description: Post the newest /data/.openclaw/workspace/x_posts/post_*.txt to X via OAuth 1.0a and log tweet IDs.
entrypoint: x_autoposter.py
methods:
  - name: x_autoposter
    args: []
    description: Read the freshest post_*.txt file, call X POST /2/tweets with OAuth 1.0a, log the tweet ID, and return a confirmation dict.
    returns: dict with message, tweet_id, and post_file path
---

# X Autoposter

## Requirements

- Environment variables (loaded earlier): `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`.
- Newest X-ready copy saved under `/data/.openclaw/workspace/x_posts/post_YYYY_MM_DD_HHMM.txt`.

## Workflow

1. Locate the most recent `post_*.txt` in `/data/.openclaw/workspace/x_posts/`.
2. Read and trim the post text (error if empty).
3. Build an OAuth 1.0a signature (HMAC-SHA1) for `POST https://api.x.com/2/tweets` using the env credentials.
4. Send `{"text": "..."}` as JSON. On HTTP errors, raise with the API’s response body.
5. Log tweet metadata to `/data/.openclaw/workspace/x_posts/post_log.json` (append-only JSON array) with ID, timestamp, source file, and a short preview.
6. Return a dict: `{"message": "Tweet posted successfully", "tweet_id": "...", "post_file": "..."}`.

Use this skill whenever you need to push the latest generated market post to X automatically.
